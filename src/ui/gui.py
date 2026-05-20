import os
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QMessageBox, QLineEdit,
    QComboBox, QStackedWidget, QSizePolicy, QStatusBar, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor,QDoubleValidator, QIntValidator

from src.ui.plots.graficar_3d import Grafica3DRealTime
from src.ui.plots.grafica_2d import Grafica2DRealTime
from src.ingest.mesaxy import MesaXY, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
from src.ingest.data_manager import DataManager


# ─────────────────────────────────────────────
#  STYLESHEET GLOBAL
# ─────────────────────────────────────────────
QSS = """
QMainWindow, QWidget#root {
    background-color: #0a0d12;
    color: #e8eaf0;
}

/* ── Sidebar ── */
QFrame#sidebar {
    background-color: #111620;
    border-right: 1px solid rgba(255,255,255,0.07);
}

/* ── Sección labels ── */
QLabel#section_label {
    color: #5a6479;
    font-size: 9px;
    letter-spacing: 2px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    padding: 10px 0px 4px 0px;
    text-transform: uppercase;
}

QLabel#logo_tag {
    color: #00c9a7;
    font-size: 9px;
    letter-spacing: 2px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QLabel#logo_title {
    color: #e8eaf0;
    font-size: 13px;
    font-weight: 600;
}

QLabel#logo_sub {
    color: #5a6479;
    font-size: 10px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* ── Status bar ── */
QFrame#status_strip {
    background-color: #0e1219;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    border-top: 1px solid rgba(255,255,255,0.07);
}

QLabel#hw_status {
    color: #8892a4;
    font-size: 10px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* ── Param labels ── */
QLabel#param_name {
    color: #8892a4;
    font-size: 11px;
}

QLineEdit#param_value {
    color: #00c9a7;
    background-color: rgba(0,201,167,0.08);
    border: 1px solid rgba(0,201,167,0.2);
    border-radius: 4px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 11px;
    padding: 1px 6px;
    max-width: 65px;
}

QLineEdit#param_value:focus {
    border: 1px solid #00c9a7;
    background-color: rgba(0,201,167,0.14);
}

/* ── Sliders ── */
QSlider::groove:horizontal {
    height: 3px;
    background: rgba(255,255,255,0.1);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #00c9a7;
    border: 2px solid #0a0d12;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #00e5c0;
}

QSlider::sub-page:horizontal {
    background: rgba(0,201,167,0.35);
    border-radius: 2px;
}

/* ── Botones generales ── */
QPushButton {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    border-radius: 7px;
    padding: 9px 12px;
    border: 1px solid rgba(255,255,255,0.1);
    background-color: #161c28;
    color: #8892a4;
    text-transform: uppercase;
}

QPushButton:hover {
    background-color: #1e2535;
    color: #e8eaf0;
}

QPushButton:disabled {
    color: #3a4155;
    border-color: rgba(255,255,255,0.04);
    background-color: #0e1118;
}

/* Home → azul */
QPushButton#btn_home {
    border-color: rgba(59,130,246,0.3);
    color: #7ba7e8;
}
QPushButton#btn_home:hover {
    background-color: rgba(59,130,246,0.1);
    border-color: rgba(59,130,246,0.6);
    color: #93c5fd;
}

/* Barrido XY → cian */
QPushButton#btn_measure {
    border-color: rgba(0,201,167,0.3);
    color: #5ecfb8;
}
QPushButton#btn_measure:hover {
    background-color: rgba(0,201,167,0.08);
    border-color: rgba(0,201,167,0.6);
    color: #00c9a7;
}

/* Barrido Freq → ámbar */
QPushButton#btn_cruz {
    border-color: rgba(245,158,11,0.3);
    color: #c9975a;
}
QPushButton#btn_cruz:hover {
    background-color: rgba(245,158,11,0.08);
    border-color: rgba(245,158,11,0.6);
    color: #f59e0b;
}

/* Stop → rojo */
QPushButton#btn_stop {
    border-color: rgba(239,68,68,0.3);
    color: #c46b6b;
}
QPushButton#btn_stop:hover {
    background-color: rgba(239,68,68,0.08);
    border-color: rgba(239,68,68,0.6);
    color: #fca5a5;
}

/* Cargar → púrpura */
QPushButton#btn_visualizar {
    border-color: rgba(139,92,246,0.3);
    color: #a48ee8;
    padding: 8px 12px;
}
QPushButton#btn_visualizar:hover {
    background-color: rgba(139,92,246,0.1);
    border-color: rgba(139,92,246,0.6);
    color: #c4b5fd;
}

/* Botones pequeños */
QPushButton#btn_rename, QPushButton#btn_delete {
    font-size: 10px;
    padding: 5px 8px;
    border-radius: 5px;
}
QPushButton#btn_delete:hover {
    background-color: rgba(239,68,68,0.08);
    border-color: rgba(239,68,68,0.5);
    color: #fca5a5;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #161c28;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    color: #8892a4;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 10px;
    padding: 6px 10px;
}

QComboBox:hover {
    border-color: rgba(255,255,255,0.18);
    color: #e8eaf0;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #161c28;
    border: 1px solid rgba(255,255,255,0.12);
    color: #8892a4;
    selection-background-color: rgba(0,201,167,0.15);
    selection-color: #00c9a7;
    font-size: 10px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* ── Alias input ── */
QLineEdit#alias_input {
    background-color: #161c28;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    color: #8892a4;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 10px;
    padding: 5px 8px;
}

QLineEdit#alias_input:focus {
    border-color: rgba(255,255,255,0.2);
    color: #e8eaf0;
}

/* ── Panel gráficas ── */
QWidget#main_panel {
    background-color: #0a0d12;
}

QFrame#plot_card {
    background-color: #111620;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
}

QLabel#plot_title {
    color: #8892a4;
    font-size: 10px;
    letter-spacing: 1px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    text-transform: uppercase;
}

QLabel#plot_meta {
    color: #5a6479;
    font-size: 9px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* ── Topbar tabs ── */
QFrame#topbar {
    background-color: #0e1219;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}

QPushButton#tab_btn {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    border-radius: 0px;
    padding: 10px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    background-color: transparent;
    color: #5a6479;
    text-transform: uppercase;
}

QPushButton#tab_btn:hover {
    color: #8892a4;
    background-color: transparent;
}

QPushButton#tab_btn[active="true"] {
    color: #00c9a7;
    border-bottom: 2px solid #00c9a7;
}

/* ── Stats bar inferior ── */
QFrame#stats_bar {
    background-color: #0e1219;
    border-top: 1px solid rgba(255,255,255,0.07);
}

QLabel#stat_lbl {
    color: #5a6479;
    font-size: 9px;
    letter-spacing: 2px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QLabel#stat_val {
    color: #8892a4;
    font-size: 11px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QLabel#stat_val_hi {
    color: #00c9a7;
    font-size: 11px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QLabel#live_chip {
    color: #00c9a7;
    background-color: rgba(0,201,167,0.08);
    border: 1px solid rgba(0,201,167,0.25);
    border-radius: 10px;
    font-size: 9px;
    letter-spacing: 2px;
    padding: 2px 8px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QLabel#freq_chip {
    color: #5a6479;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    font-size: 9px;
    letter-spacing: 1px;
    padding: 2px 8px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

QStatusBar {
    background-color: #0a0d12;
    color: #5a6479;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 9px;
    border-top: 1px solid rgba(255,255,255,0.05);
}

/* Laser — apagado */
QPushButton#btn_laser {
    border-color: rgba(34,197,94,0.3);
    color: #5a8a6a;
}
QPushButton#btn_laser:hover {
    background-color: rgba(34,197,94,0.08);
    border-color: rgba(34,197,94,0.6);
    color: #22c55e;
}
/* Laser — encendido (checked) */
QPushButton#btn_laser:checked {
    background-color: rgba(34,197,94,0.12);
    border-color: rgba(34,197,94,0.7);
    color: #22c55e;
}
QPushButton#btn_laser:checked:hover {
    background-color: rgba(239,68,68,0.08);
    border-color: rgba(239,68,68,0.5);
    color: #fca5a5;
}
QPushButton#btn_laser:disabled {
    color: #3a4155;
    border-color: rgba(255,255,255,0.04);
    background-color: #0e1118;
}
"""


# ─────────────────────────────────────────────
#  HILOS
# ─────────────────────────────────────────────
class HomeWorker(QThread):
    finished_signal = pyqtSignal()
    error_signal    = pyqtSignal(str)

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
    data_signal     = pyqtSignal(float, float, dict)
    finished_signal = pyqtSignal()
    error_signal    = pyqtSignal(str)

    def __init__(self, mesa_instance, x_max, y_max, res, f):
        super().__init__()
        self.mesa  = mesa_instance
        self.x_max = x_max
        self.y_max = y_max
        self.res   = res
        self.f     = f

    def run(self):
        try:
            for x, y, z_data in self.mesa.sweep_and_measure_generator(self.x_max, self.y_max, self.res, self.f):
                self.data_signal.emit(x, y, z_data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class ConnectWorker(QThread):
    success_signal = pyqtSignal(object)
    error_signal   = pyqtSignal(str)

    def __init__(self, port):
        super().__init__()
        self.port = port

    def run(self):
        try:
            nueva_mesa = MesaXY(port=self.port)
            self.success_signal.emit(nueva_mesa)
        except Exception as e:
            self.error_signal.emit(str(e))


class CruzWorkerThread(QThread):
    data_signal     = pyqtSignal(int, float, dict)
    finished_signal = pyqtSignal()
    error_signal    = pyqtSignal(str)

    def __init__(self, mesa, x_max, y_max, f_start, f_end, steps):
        super().__init__()
        self.mesa    = mesa
        self.x_max   = x_max
        self.y_max   = y_max
        self.f_start = f_start
        self.f_end   = f_end
        self.steps   = steps

    def run(self):
        try:
            for pt_idx, f, z_data in self.mesa.cruz_frequency_generator(
                    self.x_max, self.y_max, self.f_start, self.f_end, self.steps):
                self.data_signal.emit(pt_idx, f, z_data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


# ─────────────────────────────────────────────
#  HELPERS UI
# ─────────────────────────────────────────────
def make_label(text, obj_name, alignment=Qt.AlignmentFlag.AlignLeft):
    lbl = QLabel(text)
    lbl.setObjectName(obj_name)
    lbl.setAlignment(alignment)
    return lbl


def h_separator():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: rgba(255,255,255,0.07); margin: 4px 0;")
    return line


# ─────────────────────────────────────────────
#  VENTANA PRINCIPAL
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Radiometría Fototérmica · SR830 & Arduino")
        self.resize(1200, 720)

        self.mesa         = None
        self.worker       = None
        self.db           = DataManager()
        self.db_viewer    = DataManager()
        self.current_freq = 0.0
        self.is_homed     = False
        self.pending_task = None
        self._npts        = 0

        self.setStyleSheet(QSS)
        self.init_ui()

    # ──────────────────────────────────────────
    #  CONSTRUCCIÓN DE LA UI
    # ──────────────────────────────────────────
    def init_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_sidebar())
        main_layout.addWidget(self._build_main_panel())

        # Status bar de Qt (pie de ventana)
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Listo · Sin conexión")

    # ── Sidebar ──────────────────────────────
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(285)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo_frame = QFrame()
        logo_layout = QVBoxLayout(logo_frame)
        logo_layout.setContentsMargins(18, 16, 18, 14)
        logo_layout.setSpacing(2)
        #logo_layout.addWidget(make_label("SR830 · ARDUINO", "logo_tag"))
        logo_layout.addWidget(make_label("Radiometría Fototérmica", "logo_title"))
        logo_layout.addWidget(make_label("SR830 · ARDUINO JuanGC", "logo_sub"))
        layout.addWidget(logo_frame)

        # Estado hardware
        status_strip = QFrame()
        status_strip.setObjectName("status_strip")
        ss_layout = QHBoxLayout(status_strip)
        ss_layout.setContentsMargins(14, 8, 14, 8)
        ss_layout.setSpacing(8)

        self.hw_dot = QLabel("●")
        self.hw_dot.setStyleSheet("color: #ef4444; font-size: 10px;")
        self.hw_dot.setFixedWidth(14)
        ss_layout.addWidget(self.hw_dot)

        self.hw_text = QLabel("Sin conexión")
        self.hw_text.setObjectName("hw_status")
        ss_layout.addWidget(self.hw_text)
        ss_layout.addStretch()

        self.freq_chip = QLabel("COM3")
        self.freq_chip.setObjectName("freq_chip")
        ss_layout.addWidget(self.freq_chip)
        layout.addWidget(status_strip)

        # ── Parámetros ──
        params_frame = QFrame()
        params_layout = QVBoxLayout(params_frame)
        params_layout.setContentsMargins(14, 0, 14, 6)
        params_layout.setSpacing(1)

        self.slider_x,   self.input_x    = self._param_control(params_layout, "Eje X máx (mm)",    10, 100,  50, 10,   0)
        self.slider_y,   self.input_y    = self._param_control(params_layout, "Eje Y máx (mm)",    10, 100,  50, 10,   0)
        self.slider_res, self.input_res  = self._param_control(params_layout, "Resolución (mm)",    10, 1000, 1000, 1000, 3)
        self.slider_freq, self.input_freq = self._param_control(params_layout, "Frecuencia (Hz)",   1, 5000, 1000, 1,    0)
        layout.addWidget(params_frame)
        params_layout.addSpacing(4)

        freq_grid = QGridLayout()
        freq_grid.setSpacing(6)
        freq_grid.setContentsMargins(0, 0, 0, 4)

        def _mini_input(label_text, default_val, is_int=False):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                "font-size: 8px; color: #5a6479; font-weight: bold; letter-spacing: 1px;"
            )
            edit = QLineEdit(str(default_val))
            edit.setObjectName("param_value")
            edit.setFixedHeight(24)
            edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_int:
                edit.setValidator(QIntValidator(1, 100000))
            else:
                v = QDoubleValidator(0.1, 100000.0, 2)
                v.setNotation(QDoubleValidator.Notation.StandardNotation)
                edit.setValidator(v)
            return lbl, edit

        lbl_s, self.input_f_start = _mini_input("F INICIO (Hz)", 100, is_int=True)
        lbl_e, self.input_f_end   = _mini_input("F FINAL (Hz)",  5000, is_int=True)
        lbl_p, self.input_f_pts   = _mini_input("PASOS",         100, is_int=True)

        freq_grid.addWidget(lbl_s, 0, 0)
        freq_grid.addWidget(lbl_e, 0, 1)
        freq_grid.addWidget(lbl_p, 0, 2)
        freq_grid.addWidget(self.input_f_start, 1, 0)
        freq_grid.addWidget(self.input_f_end,   1, 1)
        freq_grid.addWidget(self.input_f_pts,   1, 2)

        params_layout.addLayout(freq_grid)

        self.input_f_start.editingFinished.connect(self._validar_frecuencias)
        self.input_f_end.editingFinished.connect(self._validar_frecuencias)

        layout.addWidget(h_separator())

        # ── Botones de acción ──
        actions_frame = QFrame()
        act_layout = QVBoxLayout(actions_frame)
        act_layout.setContentsMargins(14, 4, 14, 6)
        act_layout.setSpacing(6)

        home_laser_row = QHBoxLayout()
        home_laser_row.setSpacing(6)

        self.btn_home = QPushButton("↑  Home")
        self.btn_home.setObjectName("btn_home")
        self.btn_home.clicked.connect(self.go_home)

        self.btn_laser = QPushButton("◉  Laser")
        self.btn_laser.setObjectName("btn_laser")
        self.btn_laser.setCheckable(True)
        self.btn_laser.setEnabled(False)
        self.btn_laser.clicked.connect(self.toggle_laser)

        home_laser_row.addWidget(self.btn_home)
        home_laser_row.addWidget(self.btn_laser)
        act_layout.addLayout(home_laser_row)

        self.btn_measure = QPushButton("▦  Barrido XY")
        self.btn_measure.setObjectName("btn_measure")
        self.btn_measure.clicked.connect(lambda: self.ensure_home_then_do(self.start_measurement))
        act_layout.addWidget(self.btn_measure)

        self.btn_cruz = QPushButton("∿  Barrido Frecuencia (5 pts)")
        self.btn_cruz.setObjectName("btn_cruz")
        self.btn_cruz.clicked.connect(lambda: self.ensure_home_then_do(self.start_measurement_cruz))
        act_layout.addWidget(self.btn_cruz)

        self.btn_stop = QPushButton("■  Stop / Desconectar")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.clicked.connect(self.emergency_stop)
        self.btn_stop.setEnabled(False)
        act_layout.addWidget(self.btn_stop)

        layout.addWidget(actions_frame)
        layout.addWidget(h_separator())

        # ── Historial ──
        hist_frame = QFrame()
        hist_layout = QVBoxLayout(hist_frame)
        hist_layout.setContentsMargins(14, 4, 14, 10)
        hist_layout.setSpacing(6)

        hist_layout.addWidget(make_label("HISTORIAL DE MEDICIONES", "section_label"))

        self.combo_mediciones = QComboBox()
        self.combo_mediciones.addItem("— Seleccionar medición —", None)
        self.combo_mediciones.currentIndexChanged.connect(self._al_cambiar_medicion_combo)
        hist_layout.addWidget(self.combo_mediciones)

        alias_row = QHBoxLayout()
        alias_row.setSpacing(5)
        self.input_alias = QLineEdit()
        self.input_alias.setObjectName("alias_input")
        self.input_alias.setPlaceholderText("Alias para esta medición…")
        alias_row.addWidget(self.input_alias, 1)

        self.btn_rename = QPushButton("Guardar")
        self.btn_rename.setObjectName("btn_rename")
        self.btn_rename.clicked.connect(self._renombrar_medicion)
        alias_row.addWidget(self.btn_rename)

        self.btn_delete = QPushButton("Borrar")
        self.btn_delete.setObjectName("btn_delete")
        self.btn_delete.clicked.connect(self._borrar_medicion)
        alias_row.addWidget(self.btn_delete)
        hist_layout.addLayout(alias_row)

        self.btn_visualizar = QPushButton("Cargar y Visualizar")
        self.btn_visualizar.setObjectName("btn_visualizar")
        self.btn_visualizar.clicked.connect(self.visualizar_medicion_seleccionada)
        hist_layout.addWidget(self.btn_visualizar)

        layout.addWidget(hist_frame)
        layout.addStretch()
        self._refrescar_combo_mediciones()
        return sidebar

    # ── Panel principal ───────────────────────
    def _build_main_panel(self):
        panel = QWidget()
        panel.setObjectName("main_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Topbar con tabs
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(44)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(8, 0, 16, 0)
        tb_layout.setSpacing(0)

        self.tab_3d = QPushButton("Mapa XY — 3D")
        self.tab_3d.setObjectName("tab_btn")
        self.tab_3d.setProperty("active", "true")
        self.tab_3d.clicked.connect(lambda: self._switch_tab(0))

        self.tab_2d = QPushButton("Espectro Frecuencia")
        self.tab_2d.setObjectName("tab_btn")
        self.tab_2d.setProperty("active", "false")
        self.tab_2d.clicked.connect(lambda: self._switch_tab(1))

        tb_layout.addWidget(self.tab_3d)
        tb_layout.addWidget(self.tab_2d)
        tb_layout.addStretch()

        self.lbl_freq_chip = QLabel("f = 1000 Hz")
        self.lbl_freq_chip.setObjectName("freq_chip")
        tb_layout.addWidget(self.lbl_freq_chip)

        self.lbl_live_chip = QLabel("EN ESPERA")
        self.lbl_live_chip.setObjectName("live_chip")
        tb_layout.addWidget(self.lbl_live_chip)

        layout.addWidget(topbar)

        # Stack de gráficas
        self.stack_graficas = QStackedWidget()
        self.stack_graficas.setContentsMargins(16, 16, 16, 8)

        # Página 0 — 3D
        widget_3d = QWidget()
        layout_3d = QHBoxLayout(widget_3d)
        layout_3d.setSpacing(12)
        self.plotter_fase = Grafica3DRealTime(titulo_z="Fase °")
        self.plotter_mag  = Grafica3DRealTime(titulo_z="R Normalizada")
        layout_3d.addWidget(self._wrap_plot_card(self.plotter_fase, "FASE  φ (°)",    "fase_meta"))
        layout_3d.addWidget(self._wrap_plot_card(self.plotter_mag,  "AMPLITUD  R Normalizada", "mag_meta"))
        self.stack_graficas.addWidget(widget_3d)

        # Página 1 — 2D
        widget_2d = QWidget()
        layout_2d = QHBoxLayout(widget_2d)
        layout_2d.setSpacing(12)
        self.plot_mag_2d  = Grafica2DRealTime("Amplitud R (V) vs Freq",  log_x=True, log_y=True)
        self.plot_fase_2d = Grafica2DRealTime("Fase (°) vs Freq",         log_x=True, log_y=False)
        self.plot_quad_2d = Grafica2DRealTime("Cuadratura Y (V) vs Freq", log_x=True, log_y=True)
        layout_2d.addWidget(self._wrap_plot_card(self.plot_mag_2d,  "AMPLITUD  R (V)",    "mag2d_meta"))
        layout_2d.addWidget(self._wrap_plot_card(self.plot_fase_2d, "FASE  φ (°)",         "fase2d_meta"))
        layout_2d.addWidget(self._wrap_plot_card(self.plot_quad_2d, "CUADRATURA  Y (V)",  "quad2d_meta"))
        self.stack_graficas.addWidget(widget_2d)

        layout.addWidget(self.stack_graficas, 1)

        # Stats bar inferior
        layout.addWidget(self._build_stats_bar())
        return panel

    def _wrap_plot_card(self, plot_widget, title, meta_obj_name):
        """Envuelve una gráfica en un QFrame con header estilizado."""
        card = QFrame()
        card.setObjectName("plot_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header de la tarjeta
        header = QFrame()
        header.setStyleSheet(
            "background: transparent; border-bottom: 1px solid rgba(255,255,255,0.06);"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 8, 14, 8)

        lbl_title = make_label(title, "plot_title")
        lbl_meta  = make_label("0 puntos", "plot_meta")
        lbl_meta.setObjectName(meta_obj_name)
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        h_layout.addWidget(lbl_meta)
        card_layout.addWidget(header)

        card_layout.addWidget(plot_widget, 1)
        return card

    def _build_stats_bar(self):
        bar = QFrame()
        bar.setObjectName("stats_bar")
        bar.setFixedHeight(38)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(24)

        def stat(lbl_text, obj="stat_val"):
            layout.addWidget(make_label(lbl_text, "stat_lbl"))
            val = make_label("—", obj)
            layout.addWidget(val)
            return val

        self.stat_x     = stat("X POS",  "stat_val_hi")
        self.stat_y     = stat("Y POS",  "stat_val_hi")
        self.stat_r     = stat("R")
        self.stat_phi   = stat("φ")
        layout.addStretch()
        self.stat_npts  = stat("PUNTOS")
        self.stat_estado = stat("ESTADO")
        return bar

    # ──────────────────────────────────────────
    #  CONTROL NUMÉRICO (slider + input)
    # ──────────────────────────────────────────
    def _param_control(self, layout, nombre, min_v, max_v, init_v, factor, decimales):
        header = QHBoxLayout()
        header.setSpacing(6)
        lbl = make_label(nombre, "param_name")
        header.addWidget(lbl)
        header.addStretch()

        line_edit = QLineEdit(f"{init_v / factor:.{decimales}f}")
        line_edit.setObjectName("param_value")
        line_edit.setFixedWidth(65)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(line_edit)
        layout.addLayout(header)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_v)
        slider.setFixedHeight(22)
        layout.addWidget(slider)
        layout.addSpacing(2)

        def slider_a_texto():
            line_edit.setText(f"{slider.value() / factor:.{decimales}f}")
            if nombre.startswith("Frecuencia"):
                self.lbl_freq_chip.setText(f"f = {slider.value()} Hz")

        def texto_a_slider():
            try:
                v = max(min_v / factor, min(max_v / factor, float(line_edit.text().replace(',', '.'))))
                slider.setValue(int(v * factor))
                line_edit.setText(f"{v:.{decimales}f}")
            except ValueError:
                slider_a_texto()

        slider.valueChanged.connect(slider_a_texto)
        line_edit.editingFinished.connect(texto_a_slider)
        return slider, line_edit

    # ──────────────────────────────────────────
    #  NAVEGACIÓN TABS
    # ──────────────────────────────────────────
    def _switch_tab(self, idx):
        self.stack_graficas.setCurrentIndex(idx)
        self.tab_3d.setProperty("active", "true" if idx == 0 else "false")
        self.tab_2d.setProperty("active", "true" if idx == 1 else "false")
        # Forzar refresco del estilo para que la propiedad CSS se aplique
        self.tab_3d.style().unpolish(self.tab_3d)
        self.tab_3d.style().polish(self.tab_3d)
        self.tab_2d.style().unpolish(self.tab_2d)
        self.tab_2d.style().polish(self.tab_2d)

    # ──────────────────────────────────────────
    #  ESTADO VISUAL DEL HARDWARE
    # ──────────────────────────────────────────
    def _set_hw_status(self, state: str, msg: str = ""):
        colors = {
            "disconnected": "#ef4444",
            "pending":      "#f59e0b",
            "connected":    "#22c55e",
            "measuring":    "#00c9a7",
        }
        self.hw_dot.setStyleSheet(
            f"color: {colors.get(state, '#ef4444')}; font-size: 10px;"
        )
        self.hw_text.setText(msg or state)

        if state == "measuring":
            self.lbl_live_chip.setText("MIDIENDO")
            self.stat_estado.setText("Midiendo")
        elif state == "connected":
            self.lbl_live_chip.setText("LISTO")
            self.stat_estado.setText("En espera")
        elif state == "pending":
            self.lbl_live_chip.setText("HOMING…")
            self.stat_estado.setText("Home…")
        else:
            self.lbl_live_chip.setText("EN ESPERA")
            self.stat_estado.setText("Inactivo")

        self._status_bar.showMessage(msg or state)

    def _update_stats(self, x=None, y=None, r=None, phi=None):
        if x   is not None: self.stat_x.setText(f"{x:.3f} mm")
        if y   is not None: self.stat_y.setText(f"{y:.3f} mm")
        if r   is not None: self.stat_r.setText(f"{r:.2f}")
        if phi is not None: self.stat_phi.setText(f"{phi:.2f}°")
        self._npts += 1
        self.stat_npts.setText(str(self._npts))

        # Actualizar metas en headers
        self.findChild(QLabel, "fase_meta") and \
            self.findChild(QLabel, "fase_meta").setText(f"{self._npts} puntos")
        self.findChild(QLabel, "mag_meta") and \
            self.findChild(QLabel, "mag_meta").setText(f"{self._npts} puntos")

    # ──────────────────────────────────────────
    #  LÓGICA DE CONTROL
    # ──────────────────────────────────────────
    def _validar_frecuencias(self):
        """Corrige automáticamente si f_final no es mayor a f_inicio + 10"""
        try:
            # Reemplazamos coma por punto por si acaso
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

    def toggle_laser(self):
        if not self.mesa:
            self.btn_laser.setChecked(False)
            return
        try:
            if self.btn_laser.isChecked():
                self.mesa.lockin.set_amplitude(LASER_ON_VOLTAGE)
                self.btn_laser.setText("◉  ON")
                self._status_bar.showMessage("Laser encendido")
            else:
                self.mesa.lockin.set_amplitude(LASER_OFF_VOLTAGE)
                self.btn_laser.setText("◉  Laser")
                self._status_bar.showMessage("Laser apagado")
        except Exception as e:
            QMessageBox.warning(self, "Error Laser", f"No se pudo cambiar estado del laser: {e}")
            self.btn_laser.setChecked(not self.btn_laser.isChecked())  # revertir

    def ensure_home_then_do(self, task_function):
        if self.is_homed:
            task_function()
        else:
            self.pending_task = task_function
            self.go_home()

    def go_home(self):
        if not self.mesa:
            self._set_hw_status("pending", "Conectando…")
            self.btn_home.setText("↑  Conectando…")
            self.btn_home.setEnabled(False)

            self.conn_thread = ConnectWorker(port='COM3')
            self.conn_thread.success_signal.connect(self._on_connect_and_home_success)
            self.conn_thread.error_signal.connect(self._on_connect_and_home_error)
            self.btn_stop.setEnabled(True)
            self.conn_thread.start()
            return
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

    def _on_connect_and_home_success(self, mesa_instancia):
        self.mesa = mesa_instancia
        self._start_home_thread()

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

    def start_measurement(self):
        if not self.mesa:
            return
        self._npts = 0
        self._switch_tab(0)
        self._set_hw_status("measuring", "Barrido XY en curso…")

        exp_id = self.db.iniciar_nuevo_experimento(tipo="XY")
        print(f"Experimento ID: {exp_id}")

        self.res_actual = self.slider_res.value() / 1000.0
        self.current_freq = self.slider_freq.value()
        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0

        self.plotter_fase.inicializar_malla(x_max, y_max, self.res_actual)
        self.plotter_mag.inicializar_malla(x_max, y_max, self.res_actual)

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)
        self.worker = WorkerThread(self.mesa, x_max, y_max, self.res_actual, self.current_freq)
        self.worker.data_signal.connect(self.handle_new_data)
        self.worker.finished_signal.connect(self.measurement_finished)
        self.worker.error_signal.connect(self.measurement_error)
        self.worker.start()

    def handle_new_data(self, x, y, data_dict):
        """Para 3D Guardamos Data Procesa Data (Normaliza phi) y Grafica Data"""
        # 1. Primero enviamos los datos a la DB para que realice los cálculos.
        # guardar_punto devuelve: (mag_normalizada, fase_normalizada)
        mag_n, phi_n = self.db.guardar_punto(x, y, data_dict, self.current_freq)
        
        # 2. Extraemos la magnitud cruda (R) directamente del diccionario
        r_raw = data_dict.get('R')

        # 3. Actualizamos los plotters:
        # Graficamos la Magnitud CRUDA (R)
        if r_raw is not None: 
            self.plotter_mag.actualizar_punto(x, y, r_raw)
        
        # Graficamos la Fase NORMALIZADA (la que devolvió la DB)
        if phi_n is None:
            phi_n = data_dict.get('phi')

        if phi_n is not None: 
            self.plotter_fase.actualizar_punto(x, y, phi_n)
        
        # 4. Actualizamos estadísticas con los valores que prefieras (usaremos r crudo y phi normalizada)
        self._update_stats(x=x, y=y, r=r_raw, phi=phi_n)

    def start_measurement_cruz(self):
        if not self.mesa:
            return
        
        # Validar antes de lanzar el hilo
        self._validar_frecuencias()
        
        try:
            f_start = float(self.input_f_start.text().replace(',', '.'))
            f_end   = float(self.input_f_end.text().replace(',', '.'))
            steps   = int(self.input_f_pts.text())
        except ValueError:
            QMessageBox.warning(self, "Error de Parámetros", "Por favor, ingresa valores numéricos válidos en las frecuencias y pasos.")
            return

        self._npts = 0
        self._switch_tab(1)
        self._set_hw_status("measuring", f"Barrido Freq: {f_start} - {f_end} Hz")

        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()
        self.plot_quad_2d.limpiar()

        exp_id = self.db.iniciar_nuevo_experimento(tipo="FREQ")
        self.db.cargar_referencia_calibracion("data\calibracion\calibracion.parquet")

        x_max = self.slider_x.value() / 10.0
        y_max = self.slider_y.value() / 10.0

        self.toggle_inputs(False)
        self.btn_laser.setEnabled(False)
        # Usamos los valores capturados de los QLineEdit
        self.worker_cruz = CruzWorkerThread(self.mesa, x_max, y_max, f_start, f_end, steps)
        self.worker_cruz.data_signal.connect(self.handle_new_cruz_data)
        self.worker_cruz.finished_signal.connect(self.measurement_finished)
        self.worker_cruz.error_signal.connect(self.measurement_error)
        self.worker_cruz.start()

    def handle_new_cruz_data(self, idx, f, data_dict):
        """Para 2D Guardamos Data Procesa Data (Normaliza phi) y Grafica Data"""
        # 1. Procesar en la DB primero para obtener cálculos de tiempo real
        # Enviamos float(idx) como X y 0.0 como Y según tu estructura
        mag_n, phi_n = self.db.guardar_punto(float(idx), 0.0, data_dict, f)
        
        # 2. Extraer valores para graficar
        r_raw = data_dict.get('R')
        y_quad = data_dict.get('Y')

        # 3. Actualizar Gráficos 2D
        # Graficamos R (Magnitud Cruda)
        if r_raw is not None: 
            self.plot_mag_2d.actualizar(f, r_raw, curve_idx=idx)
        
        # Graficamos phi_n (Fase Normalizada)
        #if phi_n is None:
            #phi_n = data_dict.get('phi')

        if phi_n is not None: 
            self.plot_fase_2d.actualizar(f, phi_n, curve_idx=idx)
        
        # Graficamos Cuadratura (Y) normal
        if y_quad is not None: 
            self.plot_quad_2d.actualizar(f, y_quad, curve_idx=idx)

        # 4. Estadísticas (usando r crudo y fase normalizada para ser consistentes)
        self._update_stats(r=r_raw, phi=phi_n)

    def emergency_stop(self):
        """Detiene todo de forma segura y salva lo que se haya medido."""
        print("🛑 Iniciando parada de emergencia...")
        
        # 1. Identificar qué worker está activo
        active_worker = None
        if hasattr(self, 'worker_cruz') and self.worker_cruz and self.worker_cruz.isRunning():
            active_worker = self.worker_cruz
        elif hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            active_worker = self.worker

        # 2. Detener el hardware y el hilo ANTES de cerrar la DB
        if active_worker:
            print("Deteniendo hilo de medición...")
            # Si tu worker tiene un método para detenerse suavemente, úsalo
            if hasattr(self.mesa, 'stop_current_operation'):
                self.mesa.stop_current_operation()
            
            active_worker.terminate() # Forzamos la parada del hilo
            active_worker.wait()      # Esperamos a que el hilo muera realmente

        # 3. Ahora que el hilo no enviará más datos, cerramos el experimento
        self.db.finalizar_experimento()

        # 4. Limpieza de UI (Tu código original)
        if self.mesa:
            try:
                self.mesa.close()
            except:
                pass
            self.mesa = None

        self._set_hw_status("disconnected", "⚠️ Medición Abortada - Datos Salvados")
        self.btn_home.setText("↑  Ir a Home")
        self.btn_laser.setEnabled(False)
        self.btn_laser.setChecked(False)
        self.btn_laser.setText("◉  Laser")
        self.btn_stop.setEnabled(False)
        self.btn_measure.setEnabled(False)
        self.btn_cruz.setEnabled(False)
        self.toggle_inputs(True)
        self.is_homed = False
        
        # Actualizar la lista de mediciones para que aparezca el archivo _ABORTADO
        self._refrescar_combo_mediciones()
        
        QMessageBox.warning(self, "Abortado", "La medición se detuvo. Los puntos capturados han sido guardados.")

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

    def toggle_inputs(self, enable: bool):
        for w in (self.slider_x, self.slider_y, self.slider_res, self.slider_freq,
                  self.btn_home, self.btn_measure, self.btn_cruz, self.btn_stop):
            w.setEnabled(enable)
        self.btn_stop.setEnabled(not enable)

    # ──────────────────────────────────────────
    #  HISTORIAL
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
        QMessageBox.information(self, "Renombrar",
                                "Alias guardado." if alias else "Alias eliminado.")

    def _borrar_medicion(self):
        exp_id = self.combo_mediciones.currentData()
        if not exp_id:
            QMessageBox.information(self, "Borrar", "Selecciona primero una medición.")
            return
        resp = QMessageBox.question(
            self, "Borrar medición",
            "¿Deseas borrar los datos de esta medición? Esta acción no se puede deshacer.",
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

        path_parquet = os.path.join("data/raw", f"{exp_id}.parquet")

        if not os.path.exists(path_parquet):
            QMessageBox.critical(self, "Error", f"No se encontró el archivo: {path_parquet}")
            return

        try:
            # Consultamos directamente el archivo Parquet usando la ruta entre comillas simples
            # Esto evita el error de "Table with name mediciones does not exist"
            query = f"SELECT COUNT(DISTINCT laser_freq) FROM '{path_parquet}'"
            res = self.db_viewer.conn.execute(query).fetchone()

            if res and res[0] > 1:
                self._cargar_vista_2d(exp_id)
            else:
                self._cargar_vista_3d(exp_id)
                
        except Exception as e:
            QMessageBox.critical(self, "Error de base de datos", f"No se pudo leer el archivo: {e}")

    def _cargar_vista_2d(self, exp_id):
        curves_data = self.db_viewer.cargar_medicion_2d(exp_id)
        if not curves_data:
            return
        self._switch_tab(1)
        self.plot_mag_2d.limpiar()
        self.plot_fase_2d.limpiar()
        self.plot_quad_2d.limpiar()

        for i, (_, data) in enumerate(curves_data.items()):
            self.plot_mag_2d.set_datos_completos(data["freq"], data["mag_n"],  curve_idx=i)
            self.plot_fase_2d.set_datos_completos(data["freq"], data["phi_n"],  curve_idx=i)
            self.plot_quad_2d.set_datos_completos(data["freq"], data["quad"], curve_idx=i)

        QMessageBox.information(self, "Espectro cargado",
                                f"'{exp_id}' · {len(curves_data)} curva(s).")

    def _cargar_vista_3d(self, exp_id):
        data = self.db_viewer.cargar_medicion(exp_id)
        if not data:
            return
        self._switch_tab(0)
        self.plotter_mag.cargar_datos_completos(
            data["x_max"], data["y_max"], data["res"], data["z_mag"])
        self.plotter_fase.cargar_datos_completos(
            data["x_max"], data["y_max"], data["res"], data["z_fase"])
        QMessageBox.information(self, "Mapa cargado", f"'{exp_id}' cargado correctamente.")