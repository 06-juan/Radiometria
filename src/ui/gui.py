# src/ui/gui.py
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSlider, QFrame, QLineEdit, QComboBox, 
    QStackedWidget, QStatusBar, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QIntValidator

from src.ui.plots.graficar_3d import Grafica3DRealTime
from src.ui.plots.grafica_2d import Grafica2DRealTime


# ─────────────────────────────────────────────
#  HELPERS UI (Estáticos puros)
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
#  VENTANA PRINCIPAL ESTRUCTURAL
# ─────────────────────────────────────────────
class MainWindowUI(QMainWindow):
    """Clase base visual pura. No contiene métodos de control o hardware."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Radiometría Fototérmica · SR830 & Arduino")
        self.resize(1200, 720)
        self.load_stylesheet()
        self.init_ui()

    def load_stylesheet(self):
        current_dir = Path(__file__).resolve().parent
        qss_path = current_dir / "styles.qss"
        if qss_path.exists():
            try:
                with open(qss_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                print(f"[QSS] Error al leer el archivo de estilos: {e}")
        else:
            self.setStyleSheet("QMainWindow { background-color: #0a0d12; color: #e8eaf0; }")

    def init_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_sidebar())
        main_layout.addWidget(self._build_main_panel())

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Listo · Sin conexión")

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

        # Parámetros básicos
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

        # Matriz de frecuencias mini-inputs
        freq_grid = QGridLayout()
        freq_grid.setSpacing(6)
        freq_grid.setContentsMargins(0, 0, 0, 4)

        def _mini_input(label_text, default_val, is_int=False):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 8px; color: #5a6479; font-weight: bold; letter-spacing: 1px;")
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

        layout.addWidget(h_separator())

        # Botones de interacción
        actions_frame = QFrame()
        act_layout = QVBoxLayout(actions_frame)
        act_layout.setContentsMargins(14, 4, 14, 6)
        act_layout.setSpacing(6)

        home_laser_row = QHBoxLayout()
        home_laser_row.setSpacing(6)

        self.btn_home = QPushButton("↑  Home")
        self.btn_home.setObjectName("btn_home")
        self.btn_laser = QPushButton("◉  Laser")
        self.btn_laser.setObjectName("btn_laser")
        self.btn_laser.setCheckable(True)
        self.btn_laser.setEnabled(False)

        home_laser_row.addWidget(self.btn_home)
        home_laser_row.addWidget(self.btn_laser)
        act_layout.addLayout(home_laser_row)

        self.btn_measure = QPushButton("▦  Barrido XY")
        self.btn_measure.setObjectName("btn_measure")
        self.btn_cruz = QPushButton("∿  Barrido Frecuencia (5 pts)")
        self.btn_cruz.setObjectName("btn_cruz")
        self.btn_stop = QPushButton("■  Stop / Desconectar")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)

        act_layout.addWidget(self.btn_measure)
        act_layout.addWidget(self.btn_cruz)
        act_layout.addWidget(self.btn_stop)
        layout.addWidget(actions_frame)

        layout.addWidget(h_separator())

        # Módulo Historial
        hist_frame = QFrame()
        hist_layout = QVBoxLayout(hist_frame)
        hist_layout.setContentsMargins(14, 4, 14, 10)
        hist_layout.setSpacing(6)
        hist_layout.addWidget(make_label("HISTORIAL DE MEDICIONES", "section_label"))

        self.combo_mediciones = QComboBox()
        self.combo_mediciones.addItem("— Seleccionar medición —", None)
        hist_layout.addWidget(self.combo_mediciones)

        alias_row = QHBoxLayout()
        alias_row.setSpacing(5)
        self.input_alias = QLineEdit()
        self.input_alias.setObjectName("alias_input")
        self.input_alias.setPlaceholderText("Alias para esta medición…")
        alias_row.addWidget(self.input_alias, 1)

        self.btn_rename = QPushButton("Guardar")
        self.btn_rename.setObjectName("btn_rename")
        alias_row.addWidget(self.btn_rename)

        self.btn_delete = QPushButton("Borrar")
        self.btn_delete.setObjectName("btn_delete")
        alias_row.addWidget(self.btn_delete)
        hist_layout.addLayout(alias_row)

        self.btn_visualizar = QPushButton("Cargar y Visualizar")
        self.btn_visualizar.setObjectName("btn_visualizar")
        hist_layout.addWidget(self.btn_visualizar)

        layout.addWidget(hist_frame)
        layout.addStretch()
        return sidebar

    def _build_main_panel(self):
        panel = QWidget()
        panel.setObjectName("main_panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Pestañas Superiores
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(44)
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(8, 0, 16, 0)
        tb_layout.setSpacing(0)

        self.tab_3d = QPushButton("Mapa XY — 3D")
        self.tab_3d.setObjectName("tab_btn")
        self.tab_3d.setProperty("active", "true")
        self.tab_2d = QPushButton("Espectro Frecuencia")
        self.tab_2d.setObjectName("tab_btn")
        self.tab_2d.setProperty("active", "false")

        self.tab_3d.clicked.connect(lambda: self._switch_tab(0))
        self.tab_2d.clicked.connect(lambda: self._switch_tab(1))

        tb_layout.addWidget(self.tab_3d)
        tb_layout.addWidget(self.tab_2d)
        tb_layout.addStretch()

        self.lbl_freq_chip = QLabel("f = 1000 Hz")
        self.lbl_freq_chip.setObjectName("freq_chip")
        self.lbl_live_chip = QLabel("EN ESPERA")
        self.lbl_live_chip.setObjectName("live_chip")
        tb_layout.addWidget(self.lbl_freq_chip)
        tb_layout.addWidget(self.lbl_live_chip)
        layout.addWidget(topbar)

        # Contenedor de Gráficos (Stack)
        self.stack_graficas = QStackedWidget()
        self.stack_graficas.setContentsMargins(16, 16, 16, 8)

        # Panel 3D RealTime
        widget_3d = QWidget()
        layout_3d = QHBoxLayout(widget_3d)
        layout_3d.setSpacing(12)
        self.plotter_fase = Grafica3DRealTime(titulo_z="Fase °")
        self.plotter_mag  = Grafica3DRealTime(titulo_z="R (µV)")
        layout_3d.addWidget(self._wrap_plot_card(self.plotter_fase, "FASE  φ (°)",    "fase_meta"))
        layout_3d.addWidget(self._wrap_plot_card(self.plotter_mag,  "AMPLITUD  R (µV)", "mag_meta"))
        self.stack_graficas.addWidget(widget_3d)

        # Panel 2D RealTime
        widget_2d = QWidget()
        layout_2d = QHBoxLayout(widget_2d)
        layout_2d.setSpacing(12)
        self.plot_mag_2d  = Grafica2DRealTime("Amplitud R (V) vs Freq",  log_x=True, log_y=True)
        self.plot_fase_2d = Grafica2DRealTime("Fase (°) vs Freq",         log_x=True, log_y=False)
        layout_2d.addWidget(self._wrap_plot_card(self.plot_mag_2d,  "AMPLITUD  R (V)",    "mag2d_meta"))
        layout_2d.addWidget(self._wrap_plot_card(self.plot_fase_2d, "FASE  φ (°)",         "fase2d_meta"))
        self.stack_graficas.addWidget(widget_2d)

        layout.addWidget(self.stack_graficas, 1)
        layout.addWidget(self._build_stats_bar())
        return panel

    def _wrap_plot_card(self, plot_widget, title, meta_obj_name):
        card = QFrame()
        card.setObjectName("plot_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet("background: transparent; border-bottom: 1px solid rgba(255,255,255,0.06);")
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

    def _switch_tab(self, idx):
        self.stack_graficas.setCurrentIndex(idx)
        self.tab_3d.setProperty("active", "true" if idx == 0 else "false")
        self.tab_2d.setProperty("active", "true" if idx == 1 else "false")
        self.tab_3d.style().unpolish(self.tab_3d)
        self.tab_3d.style().polish(self.tab_3d)
        self.tab_2d.style().unpolish(self.tab_2d)
        self.tab_2d.style().polish(self.tab_2d)

    def _set_hw_status(self, state: str, msg: str = ""):
        colors = {"disconnected": "#ef4444", "pending": "#f59e0b", "connected": "#22c55e", "measuring": "#00c9a7"}
        self.hw_dot.setStyleSheet(f"color: {colors.get(state, '#ef4444')}; font-size: 10px;")
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
        if r   is not None: self.stat_r.setText(f"{r:.2f} µV")
        if phi is not None: self.stat_phi.setText(f"{phi:.2f}°")
        self._npts += 1
        self.stat_npts.setText(str(self._npts))

        fase_m = self.findChild(QLabel, "fase_meta")
        mag_m = self.findChild(QLabel, "mag_meta")
        if fase_m: fase_m.setText(f"{self._npts} puntos")
        if mag_m: mag_m.setText(f"{self._npts} puntos")

    def toggle_inputs(self, enable: bool):
        for w in (self.slider_x, self.slider_y, self.slider_res, self.slider_freq,
                  self.btn_home, self.btn_measure, self.btn_cruz, self.btn_stop):
            w.setEnabled(enable)
        self.btn_stop.setEnabled(not enable)