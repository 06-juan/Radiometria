# src/ui/orchestrator.py
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QLabel
from PyQt6.QtCore import Qt

from src.ingest.data_manager import DataManager
from src.ui.gui import MainWindowUI
from src.ui.workers import HomeWorker, WorkerThread, CruzWorkerThread, ConnectWorker

# Asegúrate de importar tus constantes del láser si cambian de ubicación
# Nota: En tu archivo original no aparecía el import de 'Laser' pero sí se usaba Laser.OFF_VOLTAGE.
# Asumo que están en src.ingest.mesaxy o en constantes.
try:
    from src.ingest.mesaxy import LASER_ON_VOLTAGE as ON_VOLTAGE, LASER_OFF_VOLTAGE as OFF_VOLTAGE
except ImportError:
    ON_VOLTAGE, OFF_VOLTAGE = 5.0, 0.0  # Valores de resguardo si no se encuentran


class MeasurementOrchestrator(MainWindowUI):
    def __init__(self):
        super().__init__()
        
        # Estado del Hardware y Datos
        self.mesa         = None
        self.lockin       = None
        self.worker       = None
        self.worker_cruz  = None
        self.conn_thread  = None
        self.home_thread  = None
        
        self.db           = DataManager()
        self.db_viewer    = DataManager()
        self.current_freq = 0.0
        self.is_homed     = False
        self.pending_task = None
        self._npts        = 0
        self._abort       = False

        # Conectar las interacciones de los botones con la lógica
        self._connect_signals()
        self._refrescar_combo_mediciones()

    def _connect_signals(self):
        """Mapea los clicks de la UI pura hacia las funciones controladoras de este archivo"""
        self.input_f_start.editingFinished.connect(self._validar_frecuencias)
        self.input_f_end.editingFinished.connect(self._validar_frecuencias)
        
        self.btn_home.clicked.connect(self.go_home)
        self.btn_laser.clicked.connect(self.toggle_laser)
        self.btn_measure.clicked.connect(lambda: self.ensure_home_then_do(self.start_measurement))
        self.btn_cruz.clicked.connect(lambda: self.ensure_home_then_do(self.start_measurement_cruz))
        self.btn_stop.clicked.connect(self.emergency_stop)
        
        self.combo_mediciones.currentIndexChanged.connect(self._al_cambiar_medicion_combo)
        self.btn_rename.clicked.connect(self._renombrar_medicion)
        self.btn_delete.clicked.connect(self._borrar_medicion)
        self.btn_visualizar.clicked.connect(self.visualizar_medicion_seleccionada)

    # ──────────────────────────────────────────
    #  LÓGICA DE CONTROL Y HARDWARE
    # ──────────────────────────────────────────
    def _validar_frecuencias(self):
        try:
            t_start = self.input_f_start.text().replace(',', '.')
            t_end   = self.input_f_end.text().replace(',', '.')
            if not t_start or not t_end: return

            f_start = float(t_start)
            f_end   = float(t_end)
            
            if f_end < (f_start + 10):
                nueva_f = int(f_start) + 10
                self.input_f_end.setText(str(nueva_f))
                self._status_bar.showMessage(f"Rango ajustado: f_final debe ser > {f_start + 10} Hz", 2000)
        except ValueError:
            pass

    def ensure_home_then_do(self, task_function):
        if self.is_homed:
            task_function()
        else:
            self.pending_task = task_function
            self.go_home()

    def toggle_laser(self):
        if not self.lockin:
            self.btn_laser.setChecked(False)
            return
        try:
            if self.btn_laser.isChecked():
                self.lockin.set_amplitude(ON_VOLTAGE)
                self.btn_laser.setText("◉  ON")
                self._status_bar.showMessage("Laser encendido")
            else:
                self.lockin.set_amplitude(OFF_VOLTAGE)
                self.btn_laser.setText("◉  Laser")
                self._status_bar.showMessage("Laser apagado")
        except Exception as e:
            QMessageBox.warning(self, "Error Laser", f"No se pudo cambiar estado del laser: {e}")
            self.btn_laser.setChecked(not self.btn_laser.isChecked())

    def go_home(self):
        if not self.mesa:
            self._set_hw_status("pending", "Conectando…")
            self.btn_home.setText("↑  Conectando…")
            self.btn_home.setEnabled(False)

            # Usamos el puerto por defecto, puedes parametrizarlo si es necesario
            self.conn_thread = ConnectWorker(port='COM3')
            self.conn_thread.success_signal.connect(self._on_connect_and_home_success)
            self.conn_thread.error_signal.connect(self._on_connect_and_home_error)
            self.btn_stop.setEnabled(True)
            self.conn_thread.start()
            return
        self._start_home_thread()

    def _on_connect_and_home_success(self, mesa_instancia, lockin_instancia):
        self.mesa = mesa_instancia
        self.lockin = lockin_instancia 
        self._start_home_thread()

    def _start_home_thread(self):
        self._set_hw_status("pending", "Yendo a home…")
        self.btn_home.setEnabled(False)
        self.btn_home.setText("↑  Yendo a home…")
        self.btn_measure.setEnabled(False)
        self.btn_laser.setEnabled(False)

        self.home_thread = HomeWorker(self.mesa)
        self.home_thread.finished_signal.connect(self.on_home_finished)
        self.home_thread.error_signal.connect(self.on_home_error)
        self.home_thread.start()

    def _on_connect_and_home_error(self, error):
        self.btn_home.setEnabled(True)
        self.btn_laser.setEnabled(False)
        self.btn_home.setText("↑  Ir a Home")
        self._set_hw_status("disconnected", "Error de conexión")
        QMessageBox.critical(self, "Error de Conexión", f"Falló: {error}")

    def on_home_finished(self):
        self.is_homed = True
        self.btn_home.setEnabled(True)
        self.btn_home.setText("✓  Homed")
        self._set_hw_status("connected", "SR830 conectado")
        self.btn_measure.setEnabled(True)
        self.btn_cruz.setEnabled(True)
        self.btn_laser.setEnabled(True)

        if self.pending_task:
            task = self.pending_task
            self.pending_task = None
            task()

    def on_home_error(self, error):
        self.btn_home.setEnabled(True)
        self.btn_home.setText("↑  Ir a Home")
        self.btn_laser.setEnabled(False)
        self._set_hw_status("disconnected", "Error en home")
        QMessageBox.warning(self, "Error en Home", f"No se pudo ir a home: {error}")

    # ──────────────────────────────────────────
    #  ADQUISICIÓN Y BARRIDOS
    # ──────────────────────────────────────────
    def start_measurement(self):
        if not self.mesa or not self.lockin:
            return
        self._npts = 0
        self._switch_tab(0)
        self._set_hw_status("measuring", "Barrido XY en curso…")

        self.db.iniciar_nuevo_experimento(tipo="XY")

        self.res_actual = self.slider_res.value() / 1000.0
        self.current_freq = self.slider_freq.value()
        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0

        self.plotter_fase.inicializar_malla(x_max, y_max, self.res_actual)
        self.plotter_mag.inicializar_malla(x_max, y_max, self.res_actual)

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)
        
        self.worker = WorkerThread(self.mesa, self.lockin, x_max, y_max, self.res_actual, self.current_freq)
        self.worker.data_signal.connect(self.handle_new_data)
        self.worker.finished_signal.connect(self.measurement_finished)
        self.worker.error_signal.connect(self.measurement_error)
        self.worker.start()

    def handle_new_data(self, x, y, data_dict):
        mag_n, phi_n = self.db.guardar_punto(x, y, data_dict, self.current_freq)
        r_raw = data_dict.get('R')

        if r_raw is not None: 
            self.plotter_mag.actualizar_punto(x, y, r_raw)
        
        if phi_n is None:
            phi_n = data_dict.get('phi')

        if phi_n is not None: 
            self.plotter_fase.actualizar_punto(x, y, phi_n)
        
        self._update_stats(x=x, y=y, r=r_raw, phi=phi_n)

    def start_measurement_cruz(self):
        if not self.mesa or not self.lockin:
            return
        
        self._validar_frecuencias()
        
        try:
            f_start = float(self.input_f_start.text().replace(',', '.'))
            f_end   = float(self.input_f_end.text().replace(',', '.'))
            steps   = int(self.input_f_pts.text())
        except ValueError:
            QMessageBox.warning(self, "Error de Parámetros", "Por favor, ingresa valores numéricos válidos.")
            return

        self._npts = 0
        self._switch_tab(1)
        self._set_hw_status("measuring", f"Barrido Freq: {f_start} - {f_end} Hz")

        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()

        self.db.iniciar_nuevo_experimento(tipo="FREQ")
        self.db.cargar_referencia_calibracion("data/calibracion/calibracion.parquet")

        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)

        self.worker_cruz = CruzWorkerThread(self.mesa, self.lockin, x_max, y_max, f_start, f_end, steps)
        self.worker_cruz.data_signal.connect(self.handle_new_cruz_data)
        self.worker_cruz.finished_signal.connect(self.measurement_finished)
        self.worker_cruz.error_signal.connect(self.measurement_error)
        self.worker_cruz.start()

    def handle_new_cruz_data(self, idx, f, data_dict):
        mag_n, phi_n = self.db.guardar_punto(float(idx), 0.0, data_dict, f)
        r_raw = data_dict.get('R')

        if r_raw is not None: 
            self.plot_mag_2d.actualizar(f, r_raw, curve_idx=idx)
        
        if phi_n is not None: 
            self.plot_fase_2d.actualizar(f, phi_n, curve_idx=idx)
        
        self._update_stats(r=r_raw, phi=phi_n)

    def emergency_stop(self):
        print("🛑 Iniciando parada de emergencia...")
        self._abort = True
        
        if self.mesa:
            try: self.mesa.stop_current_operation()
            except Exception as e: print(f"Error mesa stop: {e}")

        active_worker = None
        if hasattr(self, 'worker_cruz') and self.worker_cruz and self.worker_cruz.isRunning():
            active_worker = self.worker_cruz
        elif hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            active_worker = self.worker

        if active_worker:
            active_worker.quit()
            active_worker.wait(2000)

        if self.lockin:
            try: self.lockin.set_amplitude(OFF_VOLTAGE)
            except Exception as e: print(f"Error apagado láser: {e}")

        self.db.finalizar_experimento()

        if self.mesa:
            try: self.mesa.close()
            except: pass
            self.mesa = None
            
        if self.lockin:
            try: self.lockin.close()
            except: pass
            self.lockin = None

        self._set_hw_status("disconnected", "⚠️ Medición Abortada - Hardware Liberado")
        self.btn_home.setText("↑  Ir a Home")
        self.btn_laser.setEnabled(False)
        self.btn_laser.setChecked(False)
        self.btn_laser.setText("◉  Laser")
        self.btn_stop.setEnabled(False)
        self.btn_measure.setEnabled(False)
        self.btn_cruz.setEnabled(False)
        self.toggle_inputs(True)
        self.is_homed = False
        
        self._refrescar_combo_mediciones()
        QMessageBox.warning(self, "Abortado", "La medición se detuvo y los puertos se cerraron.")

    def measurement_finished(self):
        self.toggle_inputs(True)
        self._set_hw_status("connected", "SR830 conectado · Barrido finalizado")
        self.db.finalizar_experimento()
        self._refrescar_combo_mediciones()
        QMessageBox.information(self, "Finalizado", "Barrido completado y datos guardados.")

    def measurement_error(self, err_msg):
        self.toggle_inputs(True)
        self.db.finalizar_experimento()
        self._set_hw_status("connected", f"Error: {err_msg[:60]}")
        QMessageBox.critical(self, "Error", err_msg)

    def closeEvent(self, event):
        self._abort = True
        if self.lockin:
            try: 
                self.lockin.set_amplitude(OFF_VOLTAGE)
                self.lockin.close()
            except: pass
        if self.mesa:
            try: 
                self.mesa.stop_current_operation()
                self.mesa.close()
            except: pass
        self.db.finalizar_experimento()
        event.accept()

    # ──────────────────────────────────────────
    #  HISTORIAL Y ARCHIVOS PARQUET
    # ──────────────────────────────────────────
    def _refrescar_combo_mediciones(self):
        self.combo_mediciones.blockSignals(True)
        self.combo_mediciones.clear()
        self.combo_mediciones.addItem("— Seleccionar medición —", None)

        def _texto(exp_id, fecha, n):
            alias    = self.db_viewer.obtener_alias(exp_id)
            fecha_s  = fecha.strftime("%Y-%m-%d %H:%M") if hasattr(fecha, 'strftime') else str(fecha)
            base     = f"{exp_id}  ·  {fecha_s}  ·  {n} pts"
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
        exp_id = self.combo_mediciones.currentData()
        self.input_alias.clear()
        if exp_id:
            alias = self.db_viewer.obtener_alias(exp_id)
            self.input_alias.setText(alias or "")

    def _renombrar_medicion(self):
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(self, "Renombrar", "Selecciona primero una medición.")
            return
        alias = self.input_alias.text().strip()
        self.db_viewer.guardar_alias(exp_id, alias)
        self._refrescar_combo_mediciones()
        idx = self.combo_mediciones.findData(exp_id)
        if idx >= 0:
            self.combo_mediciones.setCurrentIndex(idx)
        QMessageBox.information(self, "Renombrar", "Alias guardado." if alias else "Alias eliminado.")

    def _borrar_medicion(self):
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(self, "Borrar", "Selecciona primero una medición.")
            return
        resp = QMessageBox.question(
            self, "Borrar medición",
            "¿Deseas borrar los datos? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if resp != QMessageBox.StandardButton.Ok:
            return
        ok = self.db_viewer.eliminar_medicion(exp_id) or self.db.eliminar_medicion(exp_id)
        if ok:
            self._refrescar_combo_mediciones()
            QMessageBox.information(self, "Borrar", "Medición eliminada.")
        else:
            QMessageBox.warning(self, "Borrar", "No se pudo eliminar la medición.")

    def visualizar_medicion_seleccionada(self):
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(self, "Visualizar", "Selecciona una medición.")
            return

        path_parquet = Path("data/raw") / f"{exp_id}.parquet"
        if not path_parquet.exists():
            QMessageBox.critical(self, "Error", f"No se encontró el archivo: {path_parquet}")
            return

        try:
            query = f"SELECT COUNT(DISTINCT laser_freq) FROM '{str(path_parquet)}'"
            res = self.db_viewer.conn.execute(query).fetchone()
            if res and res[0] > 1:
                self._cargar_vista_2d(exp_id)
            else:
                self._cargar_vista_3d(exp_id)
        except Exception as e:
            QMessageBox.critical(self, "Error de base de datos", f"No se pudo leer el archivo: {e}")

    def _cargar_vista_2d(self, exp_id):
        curves_data = self.db_viewer.cargar_medicion_2d(exp_id)
        if not curves_data: return
        self._switch_tab(1)
        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()

        for i, (_, data) in enumerate(curves_data.items()):
            self.plot_mag_2d.set_datos_completos(data["freq"], data["mag_n"], curve_idx=i)
            self.plot_fase_2d.set_datos_completos(data["freq"], data["phi_n"], curve_idx=i)

        QMessageBox.information(self, "Espectro cargado", f"'{exp_id}' · {len(curves_data)} curva(s).")

    def _cargar_vista_3d(self, exp_id):
        data = self.db_viewer.cargar_medicion(exp_id)
        if not data: return
        self._switch_tab(0)
        self.plotter_mag.cargar_datos_completos(data["x_max"], data["y_max"], data["res"], data["z_mag"])
        self.plotter_fase.cargar_datos_completos(data["x_max"], data["y_max"], data["res"], data["z_fase"])
        QMessageBox.information(self, "Mapa cargado", f"'{exp_id}' cargado correctamente.")