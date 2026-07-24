# src/ui/orchestrator.py
"""
Orquestador de medición — coordina GUI, hardware y datos.

Hereda de MainWindowUI (layout puro) y añade toda la lógica de control:
  - Conexión a hardware (o fallback a simulación)
  - Homing de la mesa XY
  - Barridos XY (3D) y de frecuencia (2D)
  - Control de láser
  - Gestión del historial de mediciones (Parquet)
  - Parada de emergencia

Flujo típico:
  1. go_home() → intenta conectar → si falla, diálogo con opción a simulación
  2. on_home_finished() → habilita botones, ejecuta tarea pendiente
  3. start_measurement() → lanza WorkerThread → handle_new_data() por punto
  4. measurement_finished() → guarda Parquet, refresca historial
"""

from pathlib import Path

from PyQt6.QtWidgets import QMessageBox, QLabel
from PyQt6.QtCore import Qt, QTimer

from src.ingest.data_manager import DataManager
from src.ui.gui import MainWindowUI
from src.ui.workers import HomeWorker, WorkerThread, CruzWorkerThread, ConnectWorker
from src.constants.constants import TableXY, Laser, Simulation


class MeasurementOrchestrator(MainWindowUI):
    """
    Coordina la adquisición de datos, el control de hardware y la GUI.

    Hereda el layout puro de MainWindowUI y añade:
      - Estado de hardware (mesa, lockin, workers activos)
      - Instancias de DataManager para experimentos y visualización
      - Flag de modo simulación (sim_mode)
    """

    def __init__(self, sim_mode=False):
        super().__init__()

        # ── Estado del hardware ──
        self.mesa = None          # MesaXY o MesaXYSimulator
        self.lockin = None        # SR830 o SR830Simulator
        self.worker = None        # Hilo activo de barrido XY
        self.worker_cruz = None   # Hilo activo de barrido de frecuencia
        self.conn_thread = None   # Hilo de conexión
        self.home_thread = None   # Hilo de homing

        # ── Estado de la aplicación ──
        self.db = DataManager()
        self.db_viewer = DataManager()
        self.current_freq = 0.0
        self.is_homed = False
        self.pending_task = None   # Tarea a ejecutar tras homing exitoso
        self._npts = 0
        self._abort = False

        # ── Modo simulación ──
        self.sim_mode = sim_mode
        self.sim_badge = None     # Widget del badge "SIMULACIÓN"

        # ── Conectar señales de la UI ──
        self._connect_signals()
        self._refrescar_combo_mediciones()

        # Si se forzó --sim, activar directamente
        if sim_mode:
            self._activar_modo_simulacion()

    # ══════════════════════════════════════════════════════════════════════════
    #  CONEXIÓN DE SEÑALES UI → LÓGICA DE CONTROL
    # ══════════════════════════════════════════════════════════════════════════

    def _connect_signals(self):
        """Mapea clicks de la UI a funciones controladoras."""
        self.input_f_start.editingFinished.connect(self._validar_frecuencias)
        self.input_f_end.editingFinished.connect(self._validar_frecuencias)

        self.btn_home.clicked.connect(self.go_home)
        self.btn_laser.clicked.connect(self.toggle_laser)
        self.btn_measure.clicked.connect(
            lambda: self.ensure_home_then_do(self.start_measurement)
        )
        self.btn_cruz.clicked.connect(
            lambda: self.ensure_home_then_do(self.start_measurement_cruz)
        )
        self.btn_stop.clicked.connect(self.emergency_stop)

        self.combo_mediciones.currentIndexChanged.connect(self._al_cambiar_medicion_combo)
        self.btn_rename.clicked.connect(self._renombrar_medicion)
        self.btn_delete.clicked.connect(self._borrar_medicion)
        self.btn_visualizar.clicked.connect(self.visualizar_medicion_seleccionada)

    # ══════════════════════════════════════════════════════════════════════════
    #  CONEXIÓN A HARDWARE / SIMULACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def go_home(self):
        """
        Inicia la conexión al hardware y el homing.

        Si no hay mesa conectada, lanza ConnectWorker en un hilo.
        Si ya está conectada, ejecuta home directamente.
        """
        if not self.mesa:
            self._set_hw_status("pending", "Conectando…")
            self.btn_home.setText("↑  Conectando…")
            self.btn_home.setEnabled(False)

            self.conn_thread = ConnectWorker(
                port=TableXY.PORT, sim_mode=self.sim_mode
            )
            self.conn_thread.success_signal.connect(self._on_connect_and_home_success)
            self.conn_thread.error_signal.connect(self._on_connect_and_home_error)
            self.conn_thread.warning_signal.connect(self._on_connect_warning)
            self.btn_stop.setEnabled(True)
            self.conn_thread.start()
            return

        self._start_home_thread()

    def _on_connect_and_home_success(self, mesa_instancia, lockin_instancia):
        """Callback exitoso: guarda instancias y arranca homing."""
        self.mesa = mesa_instancia
        self.lockin = lockin_instancia
        self._start_home_thread()

    def _on_connect_warning(self, mensaje):
        """Muestra aviso de simulación en la barra de estado."""
        self._set_hw_status("pending", mensaje)

    def _on_connect_and_home_error(self, error):
        """
        Fallo de conexión: muestra diálogo con opciones Cerrar / Simulación.

        Siempre muestra el diálogo para permitir reintentar o cambiar de modo.
        """
        self.btn_home.setEnabled(True)
        self.btn_home.setText("\u2191  Ir a Home")
        self.set_hardware_connected(False)
        self._set_hw_status("disconnected", "Error de conexión")

        # Diálogo con dos opciones
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Error de Conexión")
        msg.setText(f"No se pudo conectar al hardware:\n\n{error}")
        msg.setInformativeText("¿Qué deseas hacer?")

        btn_sim = msg.addButton(
            "Iniciar Simulación", QMessageBox.ButtonRole.AcceptRole
        )
        btn_close = msg.addButton(
            "Cerrar", QMessageBox.ButtonRole.RejectRole
        )
        msg.setDefaultButton(btn_sim)

        msg.exec()

        if msg.clickedButton() == btn_sim:
            self._activar_modo_simulacion()
        else:
            self._set_hw_status("disconnected", "Conexión cancelada")

    def _activar_modo_simulacion(self):
        """
        Activa el modo simulación creando instancias ficticias.

        Crea MesaXYSimulator y SR830Simulator, muestra un badge
        visual en la sidebar y ejecuta el homing simulado.
        """
        from src.ingest.simulador import SR830Simulator, MesaXYSimulator

        self.mesa = MesaXYSimulator()
        self.lockin = SR830Simulator()
        self.sim_mode = True

        self._set_hw_status("pending", "MODO SIMULACIÓN — Sin hardware real")
        self._mostrar_badge_simulacion()

        # Simular home exitoso tras breve delay
        QTimer.singleShot(300, self.on_home_finished)

    def _mostrar_badge_simulacion(self):
        """Inserta un banner amarillo 'SIMULACIÓN' en la sidebar."""
        if self.sim_badge:
            return

        self.sim_badge = QLabel("⚡  MODO SIMULACIÓN")
        self.sim_badge.setStyleSheet(
            "background-color: #f59e0b; color: #000; font-weight: bold; "
            "padding: 6px; border-radius: 4px; font-size: 11px; "
            "letter-spacing: 1px;"
        )
        self.sim_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Insertar después del status_strip en la sidebar
        sidebar_layout = self.centralWidget().layout().itemAt(0).widget().layout()
        sidebar_layout.insertWidget(2, self.sim_badge)

    def _ocultar_badge_simulacion(self):
        """Elimina el banner amarillo 'SIMULACIÓN' de la sidebar."""
        if self.sim_badge:
            self.sim_badge.setParent(None)
            self.sim_badge.deleteLater()
            self.sim_badge = None

    # ══════════════════════════════════════════════════════════════════════════
    #  HOMING
    # ══════════════════════════════════════════════════════════════════════════

    def _start_home_thread(self):
        """Lanza el hilo de homing (o lo simula si estamos en modo sim)."""
        self._set_hw_status("pending", "Yendo a home…")
        self.btn_home.setEnabled(False)
        self.btn_home.setText("↑  Yendo a home…")
        self.btn_measure.setEnabled(False)
        self.btn_laser.setEnabled(False)

        # En modo simulación, homing instantáneo (300ms)
        if self.sim_mode:
            QTimer.singleShot(300, self.on_home_finished)
            return

        self.home_thread = HomeWorker(self.mesa)
        self.home_thread.finished_signal.connect(self.on_home_finished)
        self.home_thread.error_signal.connect(self.on_home_error)
        self.home_thread.start()

    def on_home_finished(self):
        """Callback de homing exitoso: habilita controles y ejecuta tarea pendiente."""
        self.is_homed = True
        self.btn_home.setEnabled(True)
        self.btn_home.setText("✓  Homed")

        if self.sim_mode:
            self._set_hw_status("connected", "SIMULACIÓN — Listo para medir")
        else:
            self._set_hw_status("connected", "SR830 conectado")

        self.set_hardware_connected(True)
        self.manual_control.set_mesa(self.mesa)
        self.manual_control.set_connected(True)

        # Ejecutar tarea pendiente (ej: barrido solicitado antes del home)
        if self.pending_task:
            task = self.pending_task
            self.pending_task = None
            task()

    def on_home_error(self, error):
        """Fallo durante el homing: restaura estado de la UI."""
        self.btn_home.setEnabled(True)
        self.btn_home.setText("↑  Ir a Home")
        self.set_hardware_connected(False)
        self._set_hw_status("disconnected", "Error en home")
        QMessageBox.warning(self, "Error en Home", f"No se pudo ir a home: {error}")

    # ══════════════════════════════════════════════════════════════════════════
    #  UTILIDADES DE UI
    # ══════════════════════════════════════════════════════════════════════════

    def _validar_frecuencias(self):
        """Valida que f_end > f_start + 10 Hz, ajusta si es necesario."""
        try:
            t_start = self.input_f_start.text().replace(",", ".")
            t_end = self.input_f_end.text().replace(",", ".")
            if not t_start or not t_end:
                return

            f_start = float(t_start)
            f_end = float(t_end)

            if f_end < (f_start + 10):
                nueva_f = int(f_start) + 10
                self.input_f_end.setText(str(nueva_f))
                self._status_bar.showMessage(
                    f"Rango ajustado: f_final debe ser > {f_start + 10} Hz", 2000
                )
        except ValueError:
            pass

    def ensure_home_then_do(self, task_function):
        """Ejecuta una tarea solo si la mesa ya hizo homing; si no, la encola."""
        if self.is_homed:
            task_function()
        else:
            self.pending_task = task_function
            self.go_home()

    def toggle_laser(self):
        """Alterna el estado del láser (ON/OFF) via lock-in AUX OUT 3."""
        if not self.lockin:
            self.btn_laser.setChecked(False)
            return
        try:
            if self.btn_laser.isChecked():
                self.lockin.set_amplitude(Laser.ON_VOLTAGE)
                self.btn_laser.setText("◉  ON")
                self._status_bar.showMessage("Laser encendido")
            else:
                self.lockin.set_amplitude(Laser.OFF_VOLTAGE)
                self.btn_laser.setText("◉  Laser")
                self._status_bar.showMessage("Laser apagado")
        except Exception as e:
            QMessageBox.warning(
                self, "Error Laser",
                f"No se pudo cambiar estado del laser: {e}"
            )
            self.btn_laser.setChecked(not self.btn_laser.isChecked())

    # ══════════════════════════════════════════════════════════════════════════
    #  ADQUISICIÓN — BARRIDO XY (3D)
    # ══════════════════════════════════════════════════════════════════════════

    def start_measurement(self):
        """Inicia un barrido XY completo (medición 3D)."""
        if not self.mesa or not self.lockin:
            return

        self._npts = 0
        self._switch_tab(1)  # Tab Medición 3D
        self._set_hw_status("measuring", "Barrido XY en curso…")

        self.db.iniciar_nuevo_experimento(tipo="XY")

        # Leer parámetros de la UI
        self.res_actual = self.slider_res.value() / 100.0
        self.current_freq = self.slider_freq.value()
        x_max = float(self.slider_x.value())
        y_max = float(self.slider_y.value())

        # Validar que el barrido quepa en los límites físicos
        ox = self.mesa.origin_offset_x
        oy = self.mesa.origin_offset_y
        if ox + x_max > TableXY.X_MAX or oy + y_max > TableXY.Y_MAX:
            QMessageBox.warning(
                self, "Límite excedido",
                f"El barrido excede los límites físicos de la mesa.\n\n"
                f"Origen: ({ox:.1f}, {oy:.1f}) mm\n"
                f"Barrido: {x_max:.0f} × {y_max:.0f} mm\n"
                f"Fin estimado: ({ox + x_max:.1f}, {oy + y_max:.1f}) mm\n"
                f"Límite mesa: {TableXY.X_MAX:.0f} × {TableXY.Y_MAX:.0f} mm\n\n"
                "Reduce el área de barrido o restablece el origen."
            )
            self.toggle_inputs(True)
            self._switch_tab(0)
            return

        # Inicializar gráficas 3D
        self.plotter_fase.inicializar_malla(x_max, y_max, self.res_actual)
        self.plotter_mag.inicializar_malla(x_max, y_max, self.res_actual)

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)

        # Lanzar hilo de barrido
        self.worker = WorkerThread(
            self.mesa, self.lockin, x_max, y_max, self.res_actual, self.current_freq
        )
        self.worker.data_signal.connect(self.handle_new_data)
        self.worker.finished_signal.connect(self.measurement_finished)
        self.worker.error_signal.connect(self.measurement_error)
        self.worker.start()

    def handle_new_data(self, x, y, data_dict):
        """Procesa cada punto medido: guarda en DB y actualiza gráficas."""
        if data_dict is None:
            return

        mag_n, phi_n = self.db.guardar_punto(x, y, data_dict, self.current_freq)
        r_raw = data_dict.get("R")

        if r_raw is not None:
            self.plotter_mag.actualizar_punto(x, y, r_raw)

        if phi_n is None:
            phi_n = data_dict.get("phi")

        if phi_n is not None:
            self.plotter_fase.actualizar_punto(x, y, phi_n)

        self._update_stats(x=x, y=y, r=r_raw, phi=phi_n)

    # ══════════════════════════════════════════════════════════════════════════
    #  ADQUISICIÓN — BARRIDO DE FRECUENCIA (2D)
    # ══════════════════════════════════════════════════════════════════════════

    def start_measurement_cruz(self):
        """Inicia un barrido de frecuencia en 5 puntos de cruce."""
        if not self.mesa or not self.lockin:
            return

        self._validar_frecuencias()

        try:
            f_start = float(self.input_f_start.text().replace(",", "."))
            f_end = float(self.input_f_end.text().replace(",", "."))
            steps = int(self.input_f_pts.text())
        except ValueError:
            QMessageBox.warning(
                self, "Error de Parámetros",
                "Por favor, ingresa valores numéricos válidos."
            )
            return

        self._npts = 0
        self._switch_tab(2)  # Tab Medición Cruz
        self._set_hw_status("measuring", f"Barrido Freq: {f_start} - {f_end} Hz")

        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()

        self.db.iniciar_nuevo_experimento(tipo="FREQ")
        self.db.cargar_referencia_calibracion("data/calibracion/calibracion.parquet")

        x_max = float(self.slider_x.value())
        y_max = float(self.slider_y.value())

        ox = self.mesa.origin_offset_x
        oy = self.mesa.origin_offset_y

        if ox + x_max > TableXY.X_MAX or oy + y_max > TableXY.Y_MAX:
            QMessageBox.warning(
                self, "Límite excedido",
                f"El barrido excede los límites físicos de la mesa.\n\n"
                f"Origen: ({ox:.1f}, {oy:.1f}) mm\n"
                f"Barrido: {x_max:.0f} × {y_max:.0f} mm\n"
                f"Fin estimado: ({ox + x_max:.1f}, {oy + y_max:.1f}) mm\n"
                f"Límite mesa: {TableXY.X_MAX:.0f} × {TableXY.Y_MAX:.0f} mm\n\n"
                "Reduce el área de barrido o restablece el origen."
            )
            self.toggle_inputs(True)
            self._switch_tab(0)
            return

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)

        self.worker_cruz = CruzWorkerThread(
            self.mesa, self.lockin, x_max, y_max, f_start, f_end, steps
        )
        self.worker_cruz.data_signal.connect(self.handle_new_cruz_data)
        self.worker_cruz.finished_signal.connect(self.measurement_finished)
        self.worker_cruz.error_signal.connect(self.measurement_error)
        self.worker_cruz.start()

    def handle_new_cruz_data(self, idx, f, data_dict):
        """Procesa cada punto del barrido de frecuencia."""
        if data_dict is None:
            return

        mag_n, phi_n = self.db.guardar_punto(float(idx), 0.0, data_dict, f)
        r_raw = data_dict.get("R")

        if r_raw is not None:
            self.plot_mag_2d.actualizar(f, r_raw, curve_idx=idx)

        if phi_n is not None:
            self.plot_fase_2d.actualizar(f, phi_n, curve_idx=idx)

        self._update_stats(r=r_raw, phi=phi_n)

    # ══════════════════════════════════════════════════════════════════════════
    #  FINALIZACIÓN Y ERRORES
    # ══════════════════════════════════════════════════════════════════════════

    def measurement_finished(self):
        """Barrido completado: guarda datos y refresca historial."""
        self.toggle_inputs(True)
        estado = "SIMULACIÓN · Barrido finalizado" if self.sim_mode else "SR830 conectado · Barrido finalizado"
        self._set_hw_status("connected", estado)
        self.db.finalizar_experimento()
        self._refrescar_combo_mediciones()
        QMessageBox.information(self, "Finalizado", "Barrido completado y datos guardados.")

    def measurement_error(self, err_msg):
        """Error durante el barrido: guarda lo que se tenga y muestra error."""
        self.toggle_inputs(True)
        self.db.finalizar_experimento()
        self._set_hw_status("connected", f"Error: {err_msg[:60]}")
        QMessageBox.critical(self, "Error", err_msg)

    def emergency_stop(self):
        """Parada de emergencia: aborta workers, apaga láser, cierra puertos."""
        print("Parada de emergencia...")
        self._abort = True

        if self.mesa:
            try:
                self.mesa.stop_current_operation()
            except Exception as e:
                print(f"Error mesa stop: {e}")

        # Detener hilo activo
        active_worker = None
        if self.worker_cruz and self.worker_cruz.isRunning():
            active_worker = self.worker_cruz
        elif self.worker and self.worker.isRunning():
            active_worker = self.worker

        if active_worker:
            active_worker.quit()
            active_worker.wait(2000)

        # Apagar láser
        if self.lockin:
            try:
                self.lockin.set_amplitude(Laser.OFF_VOLTAGE)
            except Exception as e:
                print(f"Error apagado láser: {e}")

        self.db.finalizar_experimento()

        # Cerrar conexiones hardware (si no es simulación)
        if not self.sim_mode:
            if self.mesa:
                try:
                    self.mesa.close()
                except Exception:
                    pass
                self.mesa = None

            if self.lockin:
                try:
                    self.lockin.close()
                except Exception:
                    pass
                self.lockin = None
        else:
            # En modo simulación: limpiar instancias y resetear flag
            self.mesa = None
            self.lockin = None
            self.sim_mode = False
            self._ocultar_badge_simulacion()

        self.manual_control.set_mesa(None)
        self.manual_control.set_connected(False)

        self._set_hw_status(
            "disconnected",
            "Hardware liberado" if not self.sim_mode else "Simulación finalizada",
        )
        self.set_hardware_connected(False)
        self.btn_home.setText("\u2191  Ir a Home")
        self.btn_home.setEnabled(True)
        self.btn_laser.setChecked(False)
        self.btn_laser.setText("\u25c9  Laser")
        self.toggle_inputs(True)
        self.is_homed = False
        self._switch_tab(0)  # Volver a tab Movimiento

        self._refrescar_combo_mediciones()
        QMessageBox.information(
            self, "Desconectado",
            "Se liberó el hardware. Puedes intentar conectar de nuevo.",
        )

    def closeEvent(self, event):
        """Cierra la ventana: apaga láser, aborta workers, cierra puertos."""
        self._abort = True
        if self.lockin:
            try:
                self.lockin.set_amplitude(Laser.OFF_VOLTAGE)
                self.lockin.close()
            except Exception:
                pass
        if self.mesa:
            try:
                self.mesa.stop_current_operation()
                self.mesa.close()
            except Exception:
                pass
        self.manual_control.set_mesa(None)
        self.db.finalizar_experimento()
        event.accept()

    # ══════════════════════════════════════════════════════════════════════════
    #  HISTORIAL Y ARCHIVOS PARQUET
    # ══════════════════════════════════════════════════════════════════════════

    def _refrescar_combo_mediciones(self):
        """Reconstruye la lista de mediciones desde los archivos Parquet."""
        self.combo_mediciones.blockSignals(True)
        self.combo_mediciones.clear()
        self.combo_mediciones.addItem("— Seleccionar medición —", None)

        def _texto(exp_id, fecha, n):
            alias = self.db_viewer.obtener_alias(exp_id)
            fecha_s = (
                fecha.strftime("%Y-%m-%d %H:%M")
                if hasattr(fecha, "strftime")
                else str(fecha)
            )
            base = f"{exp_id}  ·  {fecha_s}  ·  {n} pts"
            return f"{alias}  —  {base}" if alias else base

        seen = set()
        for exp_id, fecha, n in self.db_viewer.listar_mediciones():
            self.combo_mediciones.addItem(_texto(exp_id, fecha, n), exp_id)
            seen.add(exp_id)
        for exp_id, fecha, n in self.db.listar_mediciones():
            if exp_id not in seen:
                self.combo_mediciones.addItem(_texto(exp_id, fecha, n), exp_id)

        self.combo_mediciones.blockSignals(False)
        self._al_cambiar_medicion_combo()

    def _al_cambiar_medicion_combo(self):
        """Carga el alias de la medición seleccionada en el campo de texto."""
        exp_id = self.combo_mediciones.currentData()
        self.input_alias.clear()
        if exp_id:
            alias = self.db_viewer.obtener_alias(exp_id)
            self.input_alias.setText(alias or "")

    def _renombrar_medicion(self):
        """Guarda o elimina el alias de la medición seleccionada."""
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(
                self, "Renombrar", "Selecciona primero una medición."
            )
            return
        alias = self.input_alias.text().strip()
        self.db_viewer.guardar_alias(exp_id, alias)
        self._refrescar_combo_mediciones()
        idx = self.combo_mediciones.findData(exp_id)
        if idx >= 0:
            self.combo_mediciones.setCurrentIndex(idx)
        QMessageBox.information(
            self, "Renombrar",
            "Alias guardado." if alias else "Alias eliminado.",
        )

    def _borrar_medicion(self):
        """Elimina el archivo Parquet de la medición seleccionada."""
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(
                self, "Borrar", "Selecciona primero una medición."
            )
            return
        resp = QMessageBox.question(
            self,
            "Borrar medición",
            "¿Deseas borrar los datos? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if resp != QMessageBox.StandardButton.Ok:
            return
        ok = self.db_viewer.eliminar_medicion(exp_id) or self.db.eliminar_medicion(
            exp_id
        )
        if ok:
            self._refrescar_combo_mediciones()
            QMessageBox.information(self, "Borrar", "Medición eliminada.")
        else:
            QMessageBox.warning(self, "Borrar", "No se pudo eliminar la medición.")

    def visualizar_medicion_seleccionada(self):
        """Carga y muestra la medición seleccionada (2D o 3D según frecuencias)."""
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(
                self, "Visualizar", "Selecciona una medición."
            )
            return

        path_parquet = Path("data/raw") / f"{exp_id}.parquet"
        if not path_parquet.exists():
            QMessageBox.critical(
                self, "Error", f"No se encontró el archivo: {path_parquet}"
            )
            return

        try:
            query = f"SELECT COUNT(DISTINCT laser_freq) FROM '{str(path_parquet)}'"
            res = self.db_viewer.conn.execute(query).fetchone()
            if res and res[0] > 1:
                self._cargar_vista_2d(exp_id)
            else:
                self._cargar_vista_3d(exp_id)
        except Exception as e:
            QMessageBox.critical(
                self, "Error de base de datos",
                f"No se pudo leer el archivo: {e}",
            )

    def _cargar_vista_2d(self, exp_id):
        """Carga datos 2D (curvas de frecuencia) en las gráficas."""
        curves_data = self.db_viewer.cargar_medicion_2d(exp_id)
        if not curves_data:
            return
        self._switch_tab(2)  # Tab Medición Cruz
        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()

        for i, (_, data) in enumerate(curves_data.items()):
            self.plot_mag_2d.set_datos_completos(
                data["freq"], data["mag_n"], curve_idx=i
            )
            self.plot_fase_2d.set_datos_completos(
                data["freq"], data["phi_n"], curve_idx=i
            )

        QMessageBox.information(
            self, "Espectro cargado",
            f"'{exp_id}' · {len(curves_data)} curva(s).",
        )

    def _cargar_vista_3d(self, exp_id):
        """Carga datos 3D (superficie) en las gráficas."""
        data = self.db_viewer.cargar_medicion_3d(exp_id)
        if not data:
            return
        self._switch_tab(1)  # Tab Medición 3D
        self.plotter_mag.cargar_datos_completos(
            data["x_max"], data["y_max"], data["res"], data["z_mag"]
        )
        self.plotter_fase.cargar_datos_completos(
            data["x_max"], data["y_max"], data["res"], data["z_fase"]
        )
        QMessageBox.information(
            self, "Mapa cargado", f"'{exp_id}' cargado correctamente."
        )
