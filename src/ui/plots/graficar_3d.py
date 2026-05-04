import os
import sys
import numpy as np

<<<<<<< HEAD
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QSizePolicy
)
from PyQt6.QtGui import QVector3D, QFont
from PyQt6.QtCore import QTimer, QEvent, Qt

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# ─────────────────────────────────────────────────────────────────────────────
#  PALETA CIENTÍFICA — cámbiala aquí si quieres otra
# ─────────────────────────────────────────────────────────────────────────────
CMAP_NOMBRE  = 'viridis'   # opciones: 'plasma', 'inferno', 'RdBu_r', 'coolwarm'
COLOR_FONDO  = (0.15, 0.15, 0.15)   # gris oscuro neutro (no negro puro)
COLOR_GRILLA = (0, 0, 0, 0.1)  # gris para la grilla de piso
=======
# --- COMPATIBILIDAD CRÍTICA PARA LINUX/WAYLAND ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["VTK_SILENT_ERRORS"] = "ON"
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"
# -------------------------------------------------
>>>>>>> 48b5e88 (botones camara y escala)

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import QTimer, Qt
import pyvista as pv
from pyvistaqt import QtInteractor

class Grafica3DRealTime(QWidget):
<<<<<<< HEAD
    """
    Superficie 3D en tiempo real:
      · colormap perceptualmente uniforme (viridis por defecto)
      · colorbar lateral con unidades reales
      · grilla de piso
      · etiquetas de ejes limpias
      · fondo gris neutro
    """

    def __init__(self, titulo_z: str = "Amplitud (µV)", titulo: str = ""):
        super().__init__()
        self.titulo_z      = titulo_z
        self.titulo_figura = titulo

        self._cmap_mpl = plt.get_cmap(CMAP_NOMBRE)  # para colores de la superficie
        self._cmap_norm = mcolors.Normalize(vmin=0, vmax=1)

        # estado interno
        self.surface_item     = None
        self.grid_item        = None
        self.axes_items       = []
        self.z_ticks_items    = []

        self.z_max_historico  = 1e-9
        self.auto_scale       = True
        self.z_scale_factor   = 1.0

        self._dragging_z      = False
        self._drag_last_y     = 0

        self.font_tick  = QFont('Arial', 8)
        self.font_label = QFont('Arial', 9, QFont.Weight.Bold)

        self._construir_ui()
        self.mostrar_vista_previa()

    # ──────────────────────────── UI ─────────────────────────────────────────

    def _construir_ui(self):
        layout_principal = QHBoxLayout(self)
        layout_principal.setContentsMargins(4, 4, 4, 4)
        layout_principal.setSpacing(0)

        # ── Viewport 3D ──
        self.view = gl.GLViewWidget()
        r, g, b = COLOR_FONDO
        self.view.setBackgroundColor((int(r*255), int(g*255), int(b*255)))
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout_principal.addWidget(self.view, stretch=9)

        # ── Colorbar (matplotlib embebida) ──
        self._fig_cb  = Figure(figsize=(0.7, 4), facecolor='none')
        self._ax_cb   = self._fig_cb.add_axes([0.05, 0.05, 0.35, 0.9])
        self._canvas_cb = FigureCanvas(self._fig_cb)
        self._canvas_cb.setFixedWidth(80)
        self._canvas_cb.setStyleSheet("background: transparent;")
        layout_principal.addWidget(self._canvas_cb, stretch=1)

        # colorbar inicial vacía
        sm = plt.cm.ScalarMappable(cmap=CMAP_NOMBRE,
                                   norm=mcolors.Normalize(vmin=0, vmax=1))
        self._cb = self._fig_cb.colorbar(sm, cax=self._ax_cb)
        self._cb.set_label(self.titulo_z, color='white', fontsize=8, labelpad=4)
        self._estilizar_colorbar(0.0, 1.0)
        self._canvas_cb.draw()

        self.view.installEventFilter(self)

    def _estilizar_colorbar(self, vmin: float, vmax: float):
        """Actualiza la colorbar con los valores reales de z."""
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        sm   = plt.cm.ScalarMappable(cmap=CMAP_NOMBRE, norm=norm)
        sm.set_array([])

        self._ax_cb.cla()
        self._cb = self._fig_cb.colorbar(sm, cax=self._ax_cb)

        # formato de ticks según unidad
        if "µV" in self.titulo_z:
            self._cb.formatter = matplotlib.ticker.FuncFormatter(
                lambda x, _: f"{x*1e6:.2f}")
            self._cb.set_label("µV", color='white', fontsize=8, labelpad=4)
        elif "°" in self.titulo_z:
            self._cb.formatter = matplotlib.ticker.FuncFormatter(
                lambda x, _: f"{x:.1f}°")
            self._cb.set_label("grados", color='white', fontsize=8, labelpad=4)
        else:
            self._cb.set_label(self.titulo_z, color='white', fontsize=8, labelpad=4)

        # estética oscura para que integre con el fondo
        self._ax_cb.tick_params(colors='white', labelsize=7)
        self._ax_cb.yaxis.label.set_color('white')
        for spine in self._ax_cb.spines.values():
            spine.set_edgecolor('#555555')
        self._fig_cb.patch.set_alpha(0)
        self._canvas_cb.draw_idle()

    # ──────────────────────── INICIALIZACIÓN DE MALLA ────────────────────────

    def mostrar_vista_previa(self):
        self.inicializar_malla(10.0, 10.0, 1.0)

    def inicializar_malla(self, x_max: float, y_max: float, res: float):
        self.x_max = x_max
        self.y_max = y_max
        self.res   = res
        self.nx    = int(x_max / res) + 1
        self.ny    = int(y_max / res) + 1
        self.xs    = np.linspace(0, x_max, self.nx)
        self.ys    = np.linspace(0, y_max, self.ny)
        self.z_raw = np.zeros((self.nx, self.ny))
        self.z_vis = np.zeros((self.nx, self.ny))
        self.z_max_historico = 1e-9

        # limpiar items previos
        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items     = []
        self.z_ticks_items  = []

        if self.surface_item:
            self.view.removeItem(self.surface_item)
        if self.grid_item:
            self.view.removeItem(self.grid_item)

        # ── Grilla de piso ──
        self.grid_item = gl.GLGridItem()
        step_x = x_max / 10
        step_y = y_max / 10
        self.grid_item.setSize(x_max, y_max)
        self.grid_item.setSpacing(step_x, step_y)
        self.grid_item.setColor(COLOR_GRILLA)
        self.grid_item.translate(x_max / 2, y_max / 2, 0)
        self.view.addItem(self.grid_item)

        # ── Superficie inicial (ceros) ──
        colores = self._z_a_colores(self.z_raw)
        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs, y=self.ys, z=self.z_vis,
            colors=colores,
            shader='shaded',
            smooth=True          # smooth=True se ve más científico
        )
        self.view.addItem(self.surface_item)

        self._dibujar_ejes()
        self._ajustar_camara()

    # ──────────────────────────── ESCALADO Z ─────────────────────────────────

    def set_auto_z_scale(self, enabled=True):
        self.auto_scale = enabled
        self._recalcular_superficie()

    def set_z_scale(self, factor: float):
        self.z_scale_factor = max(factor, 1e-12)
        self.auto_scale     = False
        self._recalcular_superficie()

    def _recalcular_superficie(self):
        if self.surface_item is None:
            return

        z_min = float(self.z_raw.min())
        z_max = float(self.z_raw.max())
        rng   = max(z_max - z_min, 1e-12)
        altura_visual = max(self.x_max, self.y_max) * 0.5

        if self.auto_scale:
            scale = altura_visual / rng
        else:
            scale = self.z_scale_factor

        # superficie desplazada a z=0 en el piso
        self.z_vis = (self.z_raw - z_min) * scale

        colores    = self._z_a_colores(self.z_raw)
        self.surface_item.setData(z=self.z_vis, colors=colores)

        # actualizar ticks z y colorbar
        self._actualizar_ticks_z(z_min, z_max)
        self._estilizar_colorbar(z_min, z_max)
        self.view.update()

    def _z_a_colores(self, z: np.ndarray) -> np.ndarray:
        """Normaliza z y mapea a RGBA usando el colormap elegido."""
        z_min = float(z.min())
        z_max = float(z.max())
        rng   = max(z_max - z_min, 1e-12)
        z_norm = (z - z_min) / rng
        return self._cmap_mpl(z_norm).reshape(-1, 4)

    # ──────────────────────────── EJES ────────────────────────────────────────

    def _dibujar_ejes(self):
        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items    = []
        self.z_ticks_items = []

        z_height = max(self.x_max, self.y_max) * 0.5
        pasos    = 5

        # eje OpenGL base (líneas X Y Z)
        axis = gl.GLAxisItem()
        axis.setSize(self.x_max * 1.05, self.y_max * 1.05, z_height)
        self.view.addItem(axis)
        self.axes_items.append(axis)

        # ── Etiqueta eje X ──
        self._add_text(
            (self.x_max * 1.2, self.y_max * 0.08 , 0),
            "X (mm)", self.font_label, (200, 200, 200, 220)
        )
        for i in range(pasos + 1):
            v = self.x_max / pasos * i
            self._add_text(
                (v, -self.y_max * 0.08, 0),
                f"{v:.0f}", self.font_tick, (180, 180, 180, 160)
            )

        # ── Etiqueta eje Y ──
        self._add_text(
            (-self.x_max * 0.08, self.y_max * 1.12, 0),
            "Y (mm)", self.font_label, (200, 200, 200, 220)
        )
        for i in range(pasos + 1):
            v = self.y_max / pasos * i
            self._add_text(
                (-self.x_max * 0.1, v, 0),
                f"{v:.0f}", self.font_tick, (180, 180, 180, 160)
            )

        # ── Ticks eje Z (dinámicos) ──
        self._add_text(
            (-self.x_max * 0.1, 0, z_height * 1.18),
            self.titulo_z, self.font_label, (220, 220, 220, 230)
        )
        for i in range(pasos + 1):
            t = gl.GLTextItem(
                pos=(0, 0, 0), text="",
                color=(180, 220, 180, 180),
                font=self.font_tick
            )
            self.view.addItem(t)
            self.axes_items.append(t)
            self.z_ticks_items.append(t)

    def _add_text(self, pos, text, font, color):
        t = gl.GLTextItem(pos=pos, text=text, color=color, font=font)
        self.view.addItem(t)
        self.axes_items.append(t)
        return t

    def _actualizar_ticks_z(self, z_min: float, z_max: float):
        if not self.z_ticks_items:
            return
        z_height = max(self.x_max, self.y_max) * 0.5
        pasos    = len(self.z_ticks_items) - 1
        for i, tick in enumerate(self.z_ticks_items):
            frac    = i / pasos
            z_real  = z_min + frac * (z_max - z_min)
            z_pos   = frac * z_height
            if "µV" in self.titulo_z:
                label = f"{z_real*1e6:.2f} µV"
            elif "°" in self.titulo_z:
                label = f"{z_real:.1f}°"
            else:
                label = f"{z_real:.3g}"
            tick.setData(pos=(-self.x_max * 0.12, 0, z_pos), text=label)

    # ──────────────────────────── CÁMARA ─────────────────────────────────────

    def _ajustar_camara(self):
        cx = self.x_max / 2
        cy = self.y_max / 2
        dist = max(self.x_max, self.y_max) * 1.8
        self.view.setCameraPosition(
            pos=QVector3D(cx, cy, 0),
            distance=dist,
            elevation=28,
            azimuth=45
        )

    # ──────────────────────── ACTUALIZACIÓN DE DATOS ─────────────────────────

    def actualizar_punto(self, x_val: float, y_val: float, z_val: float):
        ix = int(np.clip(round(x_val / self.res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / self.res), 0, self.ny - 1))
        self.z_raw[ix, iy] = z_val
        self._recalcular_superficie()

    def cargar_datos_completos(self, x_max, y_max, res, z_grid):
        self.z_raw = np.asarray(z_grid, dtype=float).copy()
        self.nx, self.ny = self.z_raw.shape
        self.x_max = x_max
        self.y_max = y_max
        self.res   = res
        self.xs    = np.linspace(0, x_max, self.nx)
        self.ys    = np.linspace(0, y_max, self.ny)

        if self.surface_item:
            self.view.removeItem(self.surface_item)
        colores = self._z_a_colores(self.z_raw)
        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs, y=self.ys,
            z=np.zeros_like(self.z_raw),
            colors=colores, shader='shaded', smooth=True
        )
        self.view.addItem(self.surface_item)

        self.z_max_historico = max(np.abs(self.z_raw).max(), 1e-9)
        self.auto_scale = True
        self._dibujar_ejes()
        self._ajustar_camara()
        self._recalcular_superficie()

    # ─────────────────────── DRAG BOTÓN DERECHO = escalar Z ──────────────────

    def eventFilter(self, obj, event):
        if obj != self.view:
            return False
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
            self._dragging_z   = True
            self._drag_last_y  = event.position().y()
            return True
        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.RightButton:
            self._dragging_z = False
            return True
        if t == QEvent.Type.MouseMove and self._dragging_z:
            if self.auto_scale:
                altura = max(self.x_max, self.y_max) * 0.5
                rng = max(float(self.z_raw.max() - self.z_raw.min()), 1e-12)
                self.z_scale_factor = altura / rng
            py = event.position().y()
            dy = self._drag_last_y - py
            self._drag_last_y = py
            factor = 1.0 + dy * 0.008
            self.z_scale_factor *= max(0.5, min(2.0, factor))
            self.z_scale_factor  = max(1e-6, min(1e12, self.z_scale_factor))
            self.auto_scale = False
            self._recalcular_superficie()
            return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import matplotlib.ticker   # necesario para el formatter de la colorbar

    app = QApplication(sys.argv)
    ventana = Grafica3DRealTime(titulo_z="Amplitud (µV)", titulo="Mapa 3D en tiempo real")
    ventana.resize(1000, 680)
    ventana.setWindowTitle("Mapa 3D — tiempo real")
    ventana.show()

    t_sim = 0.0

    def actualizar():
        global t_sim
        t_sim += 0.08
        for x in np.linspace(0, ventana.x_max, 15):
            for y in np.linspace(0, ventana.y_max, 15):
                z = 5e-6 * np.sin(0.08 * x + 0.06 * y + t_sim) * \
                    np.exp(-0.003 * ((x - 50)**2 + (y - 50)**2))
                ventana.actualizar_punto(x, y, z)

    timer = QTimer()
    timer.timeout.connect(actualizar)
    timer.start(60)   # ~16 fps
=======
    def __init__(self, titulo_z: str = "Amplitud (µV)"):
        super().__init__()
        self.setWindowTitle("Radiometría 3D Avanzada")
        self.resize(1000, 800)
        
        # --- Estado interno ---
        self.titulo_z = titulo_z
        self.x_max, self.y_max, self.res = 100.0, 100.0, 2.0
        self.z_scale_factor = 1.0  # Factor multiplicador visual
        self.auto_scale = True
        
        self.nx = int(self.x_max / self.res) + 1
        self.ny = int(self.y_max / self.res) + 1
        self.z_raw = np.zeros((self.nx, self.ny)) # Datos reales sin escalar
        
        self.initialized = False
        self._setup_ui()
        
        # Inicialización diferida para evitar crasheos en X11
        QTimer.singleShot(500, self.inicializar_visualizacion)

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        
        # --- Barra de herramientas superior ---
        toolbar = QHBoxLayout()
        
        btn_reset = QPushButton("Reset Cámara (Vista Auto)")
        btn_reset.clicked.connect(self.reset_view)
        toolbar.addWidget(btn_reset)
        
        btn_auto_z = QPushButton("Auto-Escala Z")
        btn_auto_z.clicked.connect(self.toggle_auto_scale)
        toolbar.addWidget(btn_auto_z)
        
        self.main_layout.addLayout(toolbar)
        
        # --- Contenedor de PyVista ---
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#1e1e1e")
        self.main_layout.addWidget(self.plotter)

    def inicializar_visualizacion(self):
        """Crea la malla inicial y configura el entorno 3D."""
        self.xs = np.linspace(0, self.x_max, self.nx)
        self.ys = np.linspace(0, self.y_max, self.ny)
        
        # Crear malla estructural
        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        # Inicializamos Z con un pequeño valor para que la malla exista
        self._mesh = pv.StructuredGrid(xx, yy, self.z_raw)
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')

        # Configuración de la barra de colores (Colorbar)
        s_args = dict(
            title=self.titulo_z,
            title_font_size=12,
            label_font_size=10,
            color="white",
            position_x=0.9,
            fmt="%.2e" if "µV" in self.titulo_z else "%.1f"
        )

        self.plotter.add_mesh(
            self._mesh, 
            scalars="z_valor", 
            cmap="turbo", # 'turbo' o 'viridis' son excelentes para ciencia
            name="malla_principal",
            show_edges=False,
            scalar_bar_args=s_args,
            lighting=True,
            smooth_shading=True
        )

        # Configurar Ejes y Grilla
        self.plotter.show_grid(
            xtitle="X (mm)",
            ytitle="Y (mm)",
            ztitle=self.titulo_z,
            color="gray",
            font_size=10,
            location='outer'
        )
        
        self.plotter.show_axes()
        self.reset_view()
        self.initialized = True

    def toggle_auto_scale(self):
        self.auto_scale = not self.auto_scale
        print(f"Auto-Escala Z: {'ON' if self.auto_scale else 'OFF'}")

    def reset_view(self):
        """Ajusta la cámara para ver todo el objeto."""
        self.plotter.reset_camera()
        self.plotter.render()

    def actualizar_punto(self, x_val, y_val, z_val):
        if not self.initialized: return
        
        # 1. Guardar dato real
        ix = int(np.clip(round(x_val / self.res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / self.res), 0, self.ny - 1))
        self.z_raw[ix, iy] = z_val
        
        # 2. Calcular factor de escala visual
        # Para que la montaña Z se vea bien aunque sean microvoltios
        visual_scale = 1.0
        if self.auto_scale:
            z_range = np.max(np.abs(self.z_raw))
            if z_range > 0:
                # El objetivo es que el pico más alto mida ~30% del ancho del mapa
                visual_scale = (self.x_max * 0.3) / z_range
        else:
            visual_scale = self.z_scale_factor

        # 3. Actualizar geometría del Mesh
        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        # Multiplicamos la coordenada Z física por el factor visual
        puntos = np.column_stack([
            xx.ravel(order='F'),
            yy.ravel(order='F'),
            (self.z_raw * visual_scale).ravel(order='F')
        ])
        
        self._mesh.points = puntos
        # Los colores (scalars) siempre usan el valor REAL (µV), no el escalado
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')
        
        self.plotter.render()

    def closeEvent(self, event):
        self.plotter.close()
        event.accept()

# --- DEMO ---
if __name__ == "__main__":
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    
    gui = Grafica3DRealTime(titulo_z="Intensidad (µV)")
    gui.show()

    # Generador de datos (Simulando ondas de radio)
    t = [0]
    def timer_event():
        t[0] += 0.1
        # Generar múltiples puntos para llenar la malla más rápido
        for _ in range(5):
            rx = np.random.uniform(0, 100)
            ry = np.random.uniform(0, 100)
            # Simular una señal de microvoltios (muy pequeña)
            dist = np.sqrt((rx-50)**2 + (ry-50)**2)
            rz = 5e-6 * np.sin(t[0] - dist/10) 
            gui.actualizar_punto(rx, ry, rz)

    timer = QTimer()
    timer.timeout.connect(timer_event)
    timer.start(30)
>>>>>>> 48b5e88 (botones camara y escala)

    sys.exit(app.exec())