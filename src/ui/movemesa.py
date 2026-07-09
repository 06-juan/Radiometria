# src/ui/movemesa.py
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QMessageBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

raiz_proyecto = Path(__file__).resolve().parent.parent.parent
if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.ingest.mesaxy import MesaXY
from src.constants.constants import TableXY


class ConnectAndHomeWorker(QThread):
    """
    Hilo que conecta la mesa XY y ejecuta homing.

    Si sim_mode=True, usa MesaXYSimulator en lugar del Arduino real.
    """

    success_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, sim_mode=False):
        super().__init__()
        self.sim_mode = sim_mode

    def run(self):
        try:
            if self.sim_mode:
                from src.ingest.simulador import MesaXYSimulator

                mesa_instancia = MesaXYSimulator()
                mesa_instancia.home()
                self.success_signal.emit(mesa_instancia)
                return

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
            # Simulador: move_to() maneja el movimiento directamente
            if hasattr(self.mesa, 'move_to') and not hasattr(self.mesa, 'ser'):
                self.mesa.move_to(self.target_x, self.target_y)
                self.finished_signal.emit(self.target_x, self.target_y)
                return

            # Hardware real: protocolo serial con Arduino
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


class ManualControlWidget(QWidget):
    """Widget reutilizable para control manual XY. Se puede embeder o usar standalone."""

    origen_signal = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mesa = None
        self.current_x = 0.0
        self.current_y = 0.0
        self.is_homed = False
        self.sim_mode = False
        self._init_ui()

    def _init_ui(self):
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        coord_card = QFrame()
        coord_card.setStyleSheet("background-color: #111620; border: 1px solid rgba(255,255,255,0.07); border-radius: 8px;")
        coord_layout = QHBoxLayout(coord_card)
        coord_layout.setContentsMargins(14, 12, 14, 12)

        self.lbl_x = QLabel("X: \u2014 mm")
        self.lbl_x.setStyleSheet("color: #00c9a7; font-size: 16px; font-family: 'JetBrains Mono', monospace; font-weight: bold;")
        self.lbl_y = QLabel("Y: \u2014 mm")
        self.lbl_y.setStyleSheet("color: #00c9a7; font-size: 16px; font-family: 'JetBrains Mono', monospace; font-weight: bold;")

        coord_layout.addWidget(self.lbl_x)
        coord_layout.addStretch()
        coord_layout.addWidget(self.lbl_y)
        layout.addWidget(coord_card)

        self.status_strip = QFrame()
        self.status_strip.setStyleSheet("background-color: #0e1219; border-radius: 6px; padding: 4px;")
        status_layout = QHBoxLayout(self.status_strip)

        self.hw_dot = QLabel("\u25cf")
        self.hw_dot.setStyleSheet("color: #ef4444; font-size: 12px;")
        self.hw_text = QLabel("Mesa Desconectada")
        self.hw_text.setStyleSheet("color: #8892a4; font-size: 11px; font-family: 'JetBrains Mono';")

        status_layout.addWidget(self.hw_dot)
        status_layout.addWidget(self.hw_text)
        status_layout.addStretch()
        layout.addWidget(self.status_strip)

        pad_frame = QFrame()
        pad_frame.setStyleSheet("background-color: #111620; border: 1px solid rgba(255,255,255,0.07); border-radius: 10px;")
        pad_layout = QGridLayout(pad_frame)
        pad_layout.setContentsMargins(20, 20, 20, 20)
        pad_layout.setSpacing(10)

        self.btn_up = QPushButton("\u25b2")
        self.btn_down = QPushButton("\u25bc")
        self.btn_left = QPushButton("\u25c0")
        self.btn_right = QPushButton("\u25b6")

        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right]:
            btn.setFixedSize(65, 65)
            btn.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            btn.setEnabled(False)

        self.btn_up.clicked.connect(lambda: self.trigger_move(0, -1))
        self.btn_down.clicked.connect(lambda: self.trigger_move(0, 1))
        self.btn_left.clicked.connect(lambda: self.trigger_move(1, 0))
        self.btn_right.clicked.connect(lambda: self.trigger_move(-1, 0))

        pad_layout.addWidget(self.btn_up, 0, 1, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_left, 1, 0, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_right, 1, 2, Qt.AlignmentFlag.AlignCenter)
        pad_layout.addWidget(self.btn_down, 2, 1, Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(pad_frame)

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
        layout.addWidget(slider_card)

        origen_btn = QPushButton("\u2299  Origen")
        origen_btn.setObjectName("btn_origen")
        origen_btn.setEnabled(False)
        origen_btn.clicked.connect(self._on_origen_clicked)
        layout.addWidget(origen_btn)
        self.btn_origen = origen_btn

        layout.addStretch()

    # ─── API publica para el orquestador ───

    def set_mesa(self, mesa):
        self.mesa = mesa

    def set_connected(self, connected: bool):
        enabled = connected and self.mesa is not None
        self.btn_up.setEnabled(enabled)
        self.btn_down.setEnabled(enabled)
        self.btn_left.setEnabled(enabled)
        self.btn_right.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.btn_origen.setEnabled(enabled)
        self.is_homed = connected
        if connected:
            self.hw_dot.setStyleSheet("color: #22c55e; font-size: 12px;")
            self.hw_text.setText("Mesa Lista y Calibrada")
        else:
            self.hw_dot.setStyleSheet("color: #ef4444; font-size: 12px;")
            self.hw_text.setText("Mesa Desconectada")

    def set_position(self, x: float, y: float):
        self.current_x = x
        self.current_y = y
        self.lbl_x.setText(f"X: {x:.2f} mm")
        self.lbl_y.setText(f"Y: {y:.2f} mm")

    # ─── Internos ───

    def sync_slider_label(self):
        valor_mm = self.slider.value() / TableXY.STEP_FACTOR
        self.lbl_step_val.setText(f"{valor_mm:.2f} mm")

    def _on_origen_clicked(self):
        if not self.mesa or not self.is_homed:
            return
        try:
            self.mesa.set_origin(self.current_x, self.current_y)
            self.set_position(0.0, 0.0)
            self.origen_signal.emit(self.current_x, self.current_y)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo establecer origen: {e}")

    def trigger_move(self, dx, dy):
        if not self.is_homed or not self.mesa:
            return
        step_size = self.slider.value() / TableXY.STEP_FACTOR
        target_x = self.current_x + (dx * step_size)
        target_y = self.current_y + (dy * step_size)

        if not (TableXY.X_MIN <= target_x <= TableXY.X_MAX):
            QMessageBox.warning(self, "Limite Excedido",
                                f"Movimiento denegado.\nEl eje X saldria del rango seguro ({TableXY.X_MIN} - {TableXY.X_MAX} mm).\n"
                                f"Posicion calculada: {target_x:.2f} mm")
            return
        if not (TableXY.Y_MIN <= target_y <= TableXY.Y_MAX):
            QMessageBox.warning(self, "Limite Excedido",
                                f"Movimiento denegado.\nEl eje Y saldria del rango seguro ({TableXY.Y_MIN} - {TableXY.Y_MAX} mm).\n"
                                f"Posicion calculada: {target_y:.2f} mm")
            return

        self._set_controls_enabled(False)
        self.hw_text.setText(f"Moviendo a -> X: {target_x:.2f} Y: {target_y:.2f}")

        self.move_worker = MoveWorker(self.mesa, target_x, target_y)
        self.move_worker.finished_signal.connect(self._on_move_completed)
        self.move_worker.error_signal.connect(self._on_move_error)
        self.move_worker.start()

    def _on_move_completed(self, rx, ry):
        self.set_position(rx, ry)
        self.hw_text.setText("Mesa Lista")
        self._set_controls_enabled(True)

    def _on_move_error(self, err_msg):
        self.hw_text.setText("Error posicional")
        self._set_controls_enabled(True)
        QMessageBox.warning(self, "Error de Trayecto", f"La instruccion fallo en el controlador:\n{err_msg}")

    def _set_controls_enabled(self, enabled: bool):
        self.btn_up.setEnabled(enabled)
        self.btn_down.setEnabled(enabled)
        self.btn_left.setEnabled(enabled)
        self.btn_right.setEnabled(enabled)
        self.slider.setEnabled(enabled)
        self.btn_origen.setEnabled(enabled)


class ManualControlWindow(QMainWindow):
    """Standalone window for manual XY table control."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Control Manual Mesa XY \u00b7 PyQt6")
        self.setFixedSize(380, 560)
        self.widget = ManualControlWidget()
        self.setCentralWidget(self.widget)
        self.load_stylesheet()

    def load_stylesheet(self):
        mi_carpeta = Path(__file__).resolve().parent
        qss_path = mi_carpeta / "styles.qss"
        if qss_path.exists():
            try:
                self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Advertencia: No se pudo leer el archivo QSS: {e}")
        else:
            self.setStyleSheet("QMainWindow { background-color: #0a0d12; color: #e8eaf0; }")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ManualControlWindow()
    window.show()
    sys.exit(app.exec())
