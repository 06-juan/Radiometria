import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QFrame, QMessageBox, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Importar nuestros módulos
from graficar import Grafica3DRealTime
# Intentamos importar MesaXY, si falla (por falta de hardware) avisamos
try:
    from mesaxy import MesaXY
    HARDWARE_AVAILABLE = True
except Exception as e:
    print(f"Hardware no detectado o error de importación: {e}")
    HARDWARE_AVAILABLE = False
    MesaXY = None

class WorkerThread(QThread):
    """Hilo secundario que maneja el bucle de medición para no congelar la GUI"""
    data_signal = pyqtSignal(float, float, dict) # Señal: x, y, datos_dict
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, mesa_instance, x_max, y_max, res):
        super().__init__()
        self.mesa = mesa_instance
        self.x_max = x_max
        self.y_max = y_max
        self.res = res

    def run(self):
        try:
            # Iterar sobre el generador de la mesa
            for x, y, z_data in self.mesa.sweep_and_measure_generator(self.x_max, self.y_max, self.res):
                # Emitir señal para actualizar gráfica
                self.data_signal.emit(x, y, z_data)
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Radiometría Fototérmica - SR830 & Arduino")
        self.resize(1100, 700)
        
        self.mesa = None
        self.worker = None

        # Inicializar UI
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- PANEL IZQUIERDO (Controles) ---
        controls_panel = QFrame()
        controls_panel.setFrameShape(QFrame.Shape.StyledPanel)
        controls_panel.setFixedWidth(280)
        ctrl_layout = QVBoxLayout(controls_panel)

        # Título
        lbl_title = QLabel("PARÁMETROS")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #333;")
        ctrl_layout.addWidget(lbl_title)
        
        # Sliders
        # Eje X: 1.0 a 10.0 mm (Factor 10, 1 decimal)
        self.slider_x, self.input_x = self.crear_control_numerico(
            ctrl_layout, "X Max (mm)", 10, 100, 50, 10, 1
        )

        # Eje Y: 1.0 a 10.0 mm (Factor 10, 1 decimal)
        self.slider_y, self.input_y = self.crear_control_numerico(
            ctrl_layout, "Y Max (mm)", 10, 100, 50, 10, 1
        )

        # Resolución: 0.005 a 1.000 mm (Factor 1000, 3 decimales)
        self.slider_res, self.input_res = self.crear_control_numerico(
            ctrl_layout, "Resolución (mm)", 5, 1000, 500, 1000, 3
        )

        ctrl_layout.addSpacing(20) # Un pequeño respiro visual

        # Botones de Control
        self.btn_connect = QPushButton("1. CONECTAR HARDWARE")
        self.btn_connect.setStyleSheet("background: #2196F3; color: white; padding: 8px;")
        self.btn_connect.clicked.connect(self.connect_hardware)
        ctrl_layout.addWidget(self.btn_connect)

        self.btn_home = QPushButton("2. IR A HOME")
        self.btn_home.clicked.connect(self.go_home)
        self.btn_home.setEnabled(False)
        ctrl_layout.addWidget(self.btn_home)

        self.btn_measure = QPushButton("3. INICIAR MEDICIÓN")
        self.btn_measure.setStyleSheet("background: #4CAF50; color: white; padding: 12px; font-weight: bold;")
        self.btn_measure.clicked.connect(self.start_measurement)
        self.btn_measure.setEnabled(False)
        ctrl_layout.addWidget(self.btn_measure)

        # Botón de Pánico
        self.btn_stop = QPushButton("STOP / DESCONECTAR")
        self.btn_stop.setStyleSheet("background: #D32F2F; color: white; padding: 12px; font-weight: bold;")
        self.btn_stop.clicked.connect(self.emergency_stop)
        self.btn_stop.setEnabled(False)
        ctrl_layout.addWidget(self.btn_stop)

        layout.addWidget(controls_panel)

        # --- PANEL DERECHO (Gráfica 3D) ---
        self.plotter = Grafica3DRealTime()
        layout.addWidget(self.plotter)

    def crear_slider(self, min_v, max_v, init_v, func):
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(min_v, max_v)
        s.setValue(init_v)
        s.valueChanged.connect(func)
        return s

    def crear_control_numerico(self, layout, nombre, min_v, max_v, init_v, factor, decimales):
        """
        Crea un conjunto de controles sincronizados.
        factor: por cuánto multiplicar el valor real para el slider (ej. 10 para 0.1mm)
        """
        # 1. Layout horizontal para la cabecera (Nombre y Entrada)
        header_layout = QHBoxLayout()
        lbl = QLabel(f"{nombre}:")

        line_edit = QLineEdit(f"{init_v / factor:.{decimales}f}")
        line_edit.setFixedWidth(60)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignRight)

        header_layout.addWidget(lbl)
        header_layout.addStretch() # Empuja el cuadro de texto a la derecha
        header_layout.addWidget(line_edit)
        layout.addLayout(header_layout)

        # 2. El Slider
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_v)
        layout.addWidget(slider)

        # 3. Sincronización Bidireccional
        # Slider -> Texto
        def slider_a_texto():
            valor = slider.value() / factor
            line_edit.setText(f"{valor:.{decimales}f}")

        # Texto -> Slider
        def texto_a_slider():
            try:
                texto = line_edit.text().replace(',', '.')
                valor_real = float(texto)
                # Validar límites
                valor_real = max(min_v/factor, min(max_v/factor, valor_real))
                slider.setValue(int(valor_real * factor))
                line_edit.setText(f"{valor_real:.{decimales}f}")
            except ValueError:
                slider_a_texto() # Revertir si escriben algo inválido

        slider.valueChanged.connect(slider_a_texto)
        line_edit.editingFinished.connect(texto_a_slider)

        return slider, line_edit

    def connect_hardware(self):
        if not HARDWARE_AVAILABLE:
            QMessageBox.critical(self, "Error", "Módulos de hardware no encontrados.")
            return
        
        try:
            # Aquí ajusta tu puerto COM si es necesario
            self.mesa = MesaXY(port='COM3') 
            self.btn_connect.setText("CONECTADO")
            self.btn_connect.setEnabled(False)
            self.btn_home.setEnabled(True)
            self.btn_measure.setEnabled(True)
            self.btn_stop.setEnabled(True)
            QMessageBox.showinfo(self, "Info", "Hardware conectado y listo.")
        except Exception as e:
            QMessageBox.critical(self, "Error de Conexión", f"No se pudo conectar: {e}")

    def go_home(self):
        if self.mesa:
            self.mesa.home()

    def start_measurement(self):
        if not self.mesa: return
    
        # Ahora es mucho más directo:
        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0
        res = self.slider_res.value() / 1000.0
        
        # 2. Inicializar gráfica vacía
        self.plotter.inicializar_malla(x_max, y_max, res)
        
        # 3. Bloquear interfaz
        self.toggle_inputs(False)
        
        # 4. Iniciar Worker Thread
        self.worker = WorkerThread(self.mesa, x_max, y_max, res)
        self.worker.data_signal.connect(self.handle_new_data)
        self.worker.finished_signal.connect(self.measurement_finished)
        self.worker.error_signal.connect(self.measurement_error)
        self.worker.start()

    def handle_new_data(self, x, y, data_dict):
        """Recibe datos del hilo y actualiza la gráfica"""
        # data_dict tiene {'R': ..., 'phi': ...}
        # Graficamos la magnitud R
        res = self.slider_res.value() / 100.0
        if 'R' in data_dict:
            self.plotter.actualizar_punto(x, y, data_dict['R'], res)

    def emergency_stop(self):
        """Detiene todo y cierra conexión"""
        if self.worker and self.worker.isRunning():
            self.mesa.stop_current_operation() # Avisa al hardware loop
            self.worker.wait() # Espera a que el hilo muera
        
        if self.mesa:
            self.mesa.close()
            self.mesa = None
        
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("1. CONECTAR HARDWARE")
        self.toggle_inputs(False)
        self.btn_home.setEnabled(False)
        self.btn_measure.setEnabled(False)
        self.btn_stop.setEnabled(False)
        
        QMessageBox.warning(self, "STOP", "Parada de emergencia ejecutada. Puerto cerrado.")

    def measurement_finished(self):
        self.toggle_inputs(True)
        QMessageBox.showinfo(self, "Fin", "Barrido completado.")

    def measurement_error(self, err_msg):
        self.toggle_inputs(True)
        QMessageBox.critical(self, "Error en Medición", err_msg)

    def toggle_inputs(self, enable):
        self.slider_x.setEnabled(enable)
        self.slider_y.setEnabled(enable)
        self.slider_res.setEnabled(enable)
        self.btn_home.setEnabled(enable)
        self.btn_measure.setEnabled(enable)

    def closeEvent(self, event):
        self.emergency_stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())