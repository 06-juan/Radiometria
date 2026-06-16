# src/utils/movemesa.py
import sys
import time
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QMessageBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

# Detectar la raíz del proyecto
raiz_proyecto = Path(__file__).resolve().parent.parent.parent
if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.ingest.mesaxy import MesaXY
from src.constants.constants import TableXY  # ◄ Importación limpia de la clase de la mesa


class ConnectAndHomeWorker(QThread):
    success_signal = pyqtSignal(object)
    error_signal   = pyqtSignal(str)

    def run(self):
        try:
            # Usamos constantes estructuradas
            mesa_instancia = MesaXY(port=TableXY.PORT, baudrate=TableXY.BAUDRATE)
            mesa_instancia.home()
            self.success_signal.emit(mesa_instancia)
        except Exception as e:
            self.error_signal.emit(str(e))


class MoveWorker(QThread):
    finished_signal = pyqtSignal(float, float)
    error_signal    = pyqtSignal(str)

    def __init__(self, mesa, target_x, target_y):
        super().__init__()
        self.mesa = mesa
        self.target_x = target_x
        self.target_y = target_y

    def run(self):
        try:
            self.mesa._send_command(f"MOVE {self.target_x:.3f} {self.target_y:.3f}")
            while True:
                if self.mesa.ser.in_waiting:
                    line = self.mesa.ser.readline().decode('utf-8').strip()
                    if line == "OK":
                        self.finished_signal.emit(self.target_x, self.target_y)
                        break
                    elif line.startswith("ERR"):
                        raise RuntimeError(f"Arduino reportó error: {line}")
                self.msleep(10)
        except Exception as e:
            self.error_signal.emit(str(e))


class ManualControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Manual Mesa XY · PyQt6")
        self.setFixedSize(380, 560)
        
        self.mesa = None
        self.current_x = 0.0
        self.current_y = 0.0
        self.is_homed = False

        self.load_stylesheet()
        self.init_ui()

    def load_stylesheet(self):
        mi_carpeta = Path(__file__).resolve().parent
        qss_path = mi_carpeta.parent / "ui" / "styles.qss"
        
        if qss_path.exists():
            try:
                self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
                print(f"[QSS] Estilos cargados desde: {qss_path}")
            except Exception as e:
                print(f"Advertencia: No se pudo leer el archivo QSS: {e}")
        else:
            print(f"Advertencia: No se encontró el archivo de estilos en: {qss_path}")
            self.setStyleSheet("QMainWindow { background-color: #0a0d12; color: #e8eaf0; }")
            
    def init_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        # ─── HEADER DE COORDENADAS ───
        coord_card = QFrame()
        coord_card.setStyleSheet("background-color: #111620; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px;")
        coord_layout = QHBoxLayout(coord_card)
        coord_layout.setContentsMargins(14, 12, 14, 12)
        
        self.lbl_x = QLabel("X: — mm")
        self.lbl_x.setStyleSheet("color: #00c9a7; font-size: 16px; font-family: 'JetBrains Mono', monospace; font-weight: bold;")
        self.lbl_y = QLabel("Y: — mm")
        self.lbl_y.setStyleSheet("color: #00c9a7; font-size: 16px; font-family: 'JetBrains Mono', monospace; font-weight: bold;")
        
        coord_layout.addWidget(self.lbl_x)
        coord_layout.addStretch()
        coord_layout.addWidget(self.lbl_y)
        main_layout.addWidget(coord_card)

        # ─── PANEL CENTRAL DE ESTADO ───
        self.status_strip = QFrame()
        self.status_strip.setStyleSheet("background-color: #0e1219; border-radius: 6px; padding: 4px;")
        status_layout = QHBoxLayout(self.status_strip)
        
        self.hw_dot = QLabel("●")
        self.hw_dot.setStyleSheet("color: #ef4444; font-size: 12px;")
        self.hw_text = QLabel("Mesa Desconectada")
        self.hw_text.setStyleSheet("color: #8892a4; font-size: 11px; font-family: 'JetBrains Mono';")
        
        status_layout.addWidget(self.hw_dot)
        status_layout.addWidget(self.hw_text)
        status_layout.addStretch()
        main_layout.addWidget(self.status_strip)

        # ─── CONTROL EN CRUZ (PAD DIRECCIONAL) ───
        pad_frame = QFrame()
        pad_frame.setStyleSheet("background-color: #111620; border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;")
        pad_layout = QGridLayout(pad_frame)
        pad_layout.setContentsMargins(20, 20, 20, 20)
        pad_layout.setSpacing(10)

        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        self.btn_left = QPushButton("◀")
        self.btn_right = QPushButton("▶")

        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(65, 65)
            btn.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            btn.setEnabled(False)

        self.btn_up.clicked.connect(lambda: self.trigger_move(0, 1))
        self.btn_down.clicked.connect(lambda: self.trigger_move(0, -1))
        self.btn_left.clicked.connect(lambda: self.trigger_move(-1, 0))
        self.btn_right.clicked.connect(lambda: self.trigger_move(1, 0))

        pad_layout.addWidget(self.btn_up, 0, 1, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_left, 1, 0, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_right, 1, 2, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_down, 2, 1, Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(pad_frame)

        # ─── DESLIZADOR DE PASO (JOG) ───
        slider_card = QFrame()
        slider_card.setStyleSheet("background-color: #111620; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px;")
        slider_layout = QVBoxLayout(slider_card)
        slider_layout.setContentsMargins(12, 10, 12, 12)

        info_row = QHBoxLayout()
        lbl_step_title = QLabel("DISTANCIA DE PASO:")
        lbl_step_title.setStyleSheet("color: #8892a4; font-size: 10px; font-weight: bold; font-family: 'JetBrains Mono';")
        self.lbl_step_val = QLabel(f"{TableXY.DEFAULT_STEP:.2f} mm")
        self.lbl_step_val.setStyleSheet("color: #00c9a7; font-size: 12px; font-weight: bold; font-family: 'JetBrains Mono';")
        info_row.addWidget(lbl_step_title)
        info_row.addStretch()
        info_row.addWidget(self.lbl_step_val)
        slider_layout.addLayout(info_row)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(TableXY.STEP_MIN, TableXY.STEP_MAX)
        self.slider.setValue(int(TableXY.DEFAULT_STEP * TableXY.STEP_FACTOR))
        self.slider.valueChanged.connect(self.sync_slider_label)
        self.slider.setEnabled(False)
        slider_layout.addWidget(self.slider)
        
        main_layout.addWidget(slider_card)

        # ─── ACCIONES DE CONEXIÓN Y HOME ───
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        
        self.btn_connect = QPushButton("⚡ Conectar y Home")
        self.btn_connect.setObjectName("btn_home")  
        self.btn_connect.clicked.connect(self.start_connection_process)
        
        self.btn_stop = QPushButton("■ Emergency Stop")
        self.btn_stop.setObjectName("btn_stop")      
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.emergency_shutdown)

        actions_layout.addWidget(self.btn_connect, 1)
        actions_layout.addWidget(self.btn_stop, 1)
        main_layout.addLayout(actions_layout)

    def sync_slider_label(self):
        valor_mm = self.slider.value() / TableXY.STEP_FACTOR
        self.lbl_step_val.setText(f"{valor_mm:.2f} mm")

    def set_ui_controls_enabled(self, enabled: bool):
        self.btn_up.setEnabled(enabled)
        self.btn_down.setEnabled(enabled)
        self.btn_left.setEnabled(enabled)
        self.btn_right.setEnabled(enabled)
        self.slider.setEnabled(enabled)

    def start_connection_process(self):
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Estableciendo...")
        self.hw_dot.setStyleSheet("color: #f59e0b;")
        self.hw_text.setText("Buscando hardware y alineando Home...")

        self.conn_worker = ConnectAndHomeWorker()
        self.conn_worker.success_signal.connect(self.on_connection_success)
        self.conn_worker.error_signal.connect(self.on_connection_error)
        self.conn_worker.start()
        self.btn_stop.setEnabled(True)

    def on_connection_success(self, mesa_instancia):
        self.mesa = mesa_instancia
        self.is_homed = True
        self.current_x = 0.0
        self.current_y = 0.0
        
        self.lbl_x.setText(f"X: {self.current_x:.2f} mm")
        self.lbl_y.setText(f"Y: {self.current_y:.2f} mm")
        self.hw_dot.setStyleSheet("color: #22c55e;")
        self.hw_text.setText("Mesa Lista y Calibrada")
        self.btn_connect.setText("✓ Conectado")
        self.set_ui_controls_enabled(True)

    def on_connection_error(self, err_msg):
        self.hw_dot.setStyleSheet("color: #ef4444;")
        self.hw_text.setText("Fallo de conexión")
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("⚡ Conectar y Home")
        QMessageBox.critical(self, "Error de Inicialización", f"No se pudo enlazar el hardware:\n{err_msg}")

    def trigger_move(self, dx, dy):
        if not self.is_homed or not self.mesa:
            return

        step_size = self.slider.value() / TableXY.STEP_FACTOR
        target_x = self.current_x + (dx * step_size)
        target_y = self.current_y + (dy * step_size)

        # Validación de límites usando las constantes de la clase TableXY
        if not (TableXY.X_MIN <= target_x <= TableXY.X_MAX):
            QMessageBox.warning(self, "Límite Excedido", 
                                 f"Movimiento denegado.\nEl eje X saldría del rango seguro ({TableXY.X_MIN} - {TableXY.X_MAX} mm).\n"
                                 f"Posición calculada: {target_x:.2f} mm")
            return

        if not (TableXY.Y_MIN <= target_y <= TableXY.Y_MAX):
            QMessageBox.warning(self, "Límite Excedido", 
                                 f"Movimiento denegado.\nEl eje Y saldría del rango seguro ({TableXY.Y_MIN} - {TableXY.Y_MAX} mm).\n"
                                 f"Posición calculada: {target_y:.2f} mm")
            return

        self.set_ui_controls_enabled(False)
        self.hw_text.setText(f"Moviendo a -> X: {target_x:.2f} Y: {target_y:.2f}")

        self.move_worker = MoveWorker(self.mesa, target_x, target_y)
        self.move_worker.finished_signal.connect(self.on_move_completed)
        self.move_worker.error_signal.connect(self.on_move_error)
        self.move_worker.start()

    def on_move_completed(self, rx, ry):
        self.current_x = rx
        self.current_y = ry
        self.lbl_x.setText(f"X: {self.current_x:.2f} mm")
        self.lbl_y.setText(f"Y: {self.current_y:.2f} mm")
        self.hw_text.setText("Mesa Lista")
        self.set_ui_controls_enabled(True)

    def on_move_error(self, err_msg):
        self.hw_text.setText("Error posicional")
        self.set_ui_controls_enabled(True)
        QMessageBox.warning(self, "Error de Trayecto", f"La instrucción falló en el controlador:\n{err_msg}")

    def emergency_shutdown(self):
        try:
            if self.mesa:
                self.mesa.stop_current_operation()
        except:
            pass
        self.set_ui_controls_enabled(False)
        self.is_homed = False
        self.btn_connect.setEnabled(True)
        self.btn_connect.setText("⚡ Conectar y Home")
        self.hw_dot.setStyleSheet("color: #ef4444;")
        self.hw_text.setText("Parada de Emergencia activada.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ManualControlWindow()
    window.show()
    sys.exit(app.exec())