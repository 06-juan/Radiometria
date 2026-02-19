import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QFrame, QMessageBox, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Importar nuestros módulos
from graficar import Grafica3DRealTime
from mesaxy import MesaXY
from data_manager import DataManager
from lockin import get_measurements, set_frequency

class HomeWorker(QThread):
    """Hilo para que la mesa busque el origen sin bloquear la GUI"""
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, mesa_instance):
        super().__init__()
        self.mesa = mesa_instance

    def run(self):
        try:
            if self.mesa:
                self.mesa.home()
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

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
            # 3. Iniciar el generador
            # Pasamos un parámetro extra para saber que es un inicio real
            for x, y, z_data in self.mesa.sweep_and_measure_generator(self.x_max, self.y_max, self.res):
                self.data_signal.emit(x, y, z_data)
            self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(str(e))
            
class ConnectWorker(QThread):
    """El mensajero que irá al puerto COM mientras la GUI sigue libre"""
    success_signal = pyqtSignal(object) # Enviará el objeto 'mesa' si todo sale bien
    error_signal = pyqtSignal(str)     # Enviará el mensaje de error si falla

    def __init__(self, port):
        super().__init__()
        self.port = port

    def run(self):
        try:
            # Aquí invocamos a la clase pesada de tu otro archivo
            # El bloqueo de 'time.sleep' y 'while' ocurrirá AQUÍ, no en la GUI
            nueva_mesa = MesaXY(port=self.port) 
            self.success_signal.emit(nueva_mesa)
        except Exception as e:
            self.error_signal.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Radiometría Fototérmica - SR830 & Arduino")
        self.resize(1100, 700)
        
        self.mesa = None
        self.worker = None
        
        # Inicializamos la Base de Datos
        self.db = DataManager() # <--- NUEVO: El archivista está listo
        self.current_freq = 0.0 # Variable para recordar la frecuencia actual

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
        lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; color: #999;")
        ctrl_layout.addWidget(lbl_title)
        
        # Sliders
        # Eje X: 1.0 a 10.0 mm (Factor 10, 0 decimal)
        self.slider_x, self.input_x = self.crear_control_numerico(
            ctrl_layout, "X Max (mm)", 10, 100, 50, 10, 0
        )

        # Eje Y: 1.0 a 10.0 mm (Factor 10, 0 decimal)
        self.slider_y, self.input_y = self.crear_control_numerico(
            ctrl_layout, "Y Max (mm)", 10, 100, 50, 10, 0
        )

        # Resolución: 0.005 a 1.000 mm (Factor 1000, 3 decimales)
        self.slider_res, self.input_res = self.crear_control_numerico(
            ctrl_layout, "Resolución (mm)", 5, 1000, 1000, 1000, 3
        )

        # frecuencia
        self.slider_freq, self.input_freq = self.crear_control_numerico(
            ctrl_layout, "frecuencia (Hz)", 1, 1000, 1000, 1, 0
        )

        ctrl_layout.addSpacing(20) # Un pequeño respiro visual

        # Botones de Control
        self.btn_connect = QPushButton("1. CONECTAR HARDWARE")
        self.btn_connect.setStyleSheet("background: #2196F3; color: white; padding: 8px;")
        self.btn_connect.clicked.connect(self.connect_hardware)
        ctrl_layout.addWidget(self.btn_connect)

        self.btn_home = QPushButton("2. IR A HOME")
        self.btn_home.setStyleSheet("background: #2196F3; color: white; padding: 8px; font-weight: bold;")
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
        # Instanciamos ambas gráficas. Al agregarlas al QHBoxLayout, 
        # la primera que agreguemos quedará a la izquierda de la segunda.
        
        self.plotter_fase = Grafica3DRealTime(titulo_z="Fase °")  # Gráfica para la Fase
        self.plotter_mag = Grafica3DRealTime(titulo_z="R (µV)")   # Gráfica para la Magnitud R

        # Agregamos primero la fase (queda a la izquierda) y luego magnitud (a la derecha)
        layout.addWidget(self.plotter_fase)
        layout.addWidget(self.plotter_mag)

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
        # 1. Bloqueamos el botón para evitar clics dobles ansiosos
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("CONECTANDO...")
        self.btn_connect.setStyleSheet("background: #FF6900; color: white; padding: 8px;")
        
        # 2. Creamos al trabajador y conectamos sus "avisos"
        self.conn_thread = ConnectWorker(port='COM3')
        self.conn_thread.success_signal.connect(self.on_connection_success)
        self.conn_thread.error_signal.connect(self.on_connection_error)

        self.btn_stop.setStyleSheet("background: #D32F2F; color: white; padding: 12px; font-weight: bold;")
        
        # 3. ¡A trabajar! (Esto lanza el método run() en paralelo)
        self.conn_thread.start()

    def on_connection_success(self, mesa_instancia):
        self.mesa = mesa_instancia # Ya tenemos la estafeta
        self.btn_connect.setText("CONECTADO")
        self.btn_home.setEnabled(True)
        self.btn_measure.setEnabled(True)
        self.btn_stop.setEnabled(True)

    def on_connection_error(self, error):
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("1. REINTENTAR CONEXIÓN")
        QMessageBox.critical(self, "Error de Conexión", f"Falló: {error}")

    def go_home(self):
        """Inicia el proceso de home en segundo plano"""
        if not self.mesa: return

        # 1. Bloqueamos controles para no mandar comandos contradictorios
        self.btn_home.setEnabled(False)
        self.btn_home.setText("YENDO A HOME...")
        self.btn_home.setStyleSheet("background: #FF6900; color: white; padding: 8px; font-weight: bold;")
        self.btn_measure.setEnabled(False) # No medir mientras se mueve a home

        # 2. Creamos y lanzamos el hilo
        self.home_thread = HomeWorker(self.mesa)
        self.home_thread.finished_signal.connect(self.on_home_finished)
        self.home_thread.error_signal.connect(self.on_home_error)
        self.home_thread.start()

    def on_home_finished(self):
        """Se ejecuta cuando la mesa ya está en (0,0)"""
        self.btn_home.setEnabled(True)
        self.btn_home.setText("HOMED")
        self.btn_measure.setEnabled(True)
        print("Mesa en posición de origen.")

    def on_home_error(self, error):
        """Si algo falla durante el movimiento"""
        self.btn_home.setEnabled(True)
        self.btn_home.setText("2. IR A HOME")
        QMessageBox.warning(self, "Error en Home", f"No se pudo ir a home: {error}")

    def start_measurement(self):
        self.btn_measure.setStyleSheet("background: #2196F3; color: white; padding: 12px; font-weight: bold;")
        if not self.mesa: return

        # 1. Configurar Hardware
        # CORRECCIÓN: Llamamos a lockin.set_frequency, no a mesa.ajustar...
        self.current_freq = self.slider_freq.value()
        print(f"Configurando Lock-in a {self.current_freq} Hz...")
        set_frequency(self.current_freq) 
        
        # 2. Preparar Base de Datos
        exp_id = self.db.iniciar_nuevo_experimento()
        print(f"Iniciando guardado de datos en ID: {exp_id}")

        # 3. Preparar Gráficas
        self.res_actual = self.slider_res.value() / 1000.0
        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0
        
        # Inicializamos ambas mallas
        self.plotter_fase.inicializar_malla(x_max, y_max, self.res_actual)
        self.plotter_mag.inicializar_malla(x_max, y_max, self.res_actual)

        # 4. Iniciar Worker
        self.toggle_inputs(False)
        self.worker = WorkerThread(self.mesa, x_max, y_max, self.res_actual)
        self.worker.data_signal.connect(self.handle_new_data) # <--- Aquí recibimos el dato
        self.worker.finished_signal.connect(self.measurement_finished)
        self.worker.error_signal.connect(self.measurement_error)
        self.worker.start()

    def handle_new_data(self, x, y, data_dict):
        """
        Este método se ejecuta cada vez que el Arduino/Lockin escupen un dato.
        Aquí graficamos Y GUARDAMOS.
        """
        # 1. Actualizar Gráficas
        if 'R' in data_dict:
            self.plotter_mag.actualizar_punto(x, y, data_dict['R'])
            
        # Reemplaza 'Theta' por la clave exacta que uses en tu diccionario para la fase
        if 'phi' in data_dict: 
            self.plotter_fase.actualizar_punto(x, y, data_dict['phi'])
        
        # 2. Guardar en DuckDB
        # Pasamos x, y, el diccionario completo y la frecuencia actual
        self.db.guardar_punto(x, y, data_dict, self.current_freq)

    def emergency_stop(self):
        if self.worker and self.worker.isRunning():
            self.mesa.stop_current_operation()
            self.worker.wait()
        if self.mesa:
            self.mesa.close()
            self.mesa = None
        self.btn_connect.setEnabled(True)
        self.toggle_inputs(False)
        self.btn_stop.setStyleSheet("background: #474B4E; color: white; padding: 12px; font-weight: bold;")
        self.btn_connect.setText("1. CONECTAR HARDWARE")
        self.btn_connect.setStyleSheet("background: #2196F3; color: white; padding: 8px;")
        self.btn_home.setText("2. IR A HOME")
        self.btn_home.setStyleSheet("background: #2196F3; color: white; padding: 8px; font-weight: bold;")

        self.btn_measure.setStyleSheet("background: #4CAF50; color: white; padding: 12px; font-weight: bold;")

        self.toggle_inputs(True)


    def measurement_finished(self):
        self.toggle_inputs(True)
        QMessageBox.information(self, "Fin", "Barrido completado y datos guardados.")

    def measurement_error(self, err_msg):
        self.toggle_inputs(True)
        QMessageBox.critical(self, "Error", err_msg)

    def toggle_inputs(self, enable):
        self.slider_x.setEnabled(enable)
        self.slider_y.setEnabled(enable)
        self.slider_res.setEnabled(enable)
        self.slider_freq.setEnabled(enable) # Bloqueamos frecuencia también
        self.btn_home.setEnabled(enable)
        self.btn_measure.setEnabled(enable)

    def closeEvent(self, event):
        self.emergency_stop()
        self.db.cerrar() # Cerramos la BD al salir
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
