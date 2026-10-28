# src/ui/plots/graficar_3d.py
import sys
import numpy as np

import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtGui import QVector3D, QFont
from PyQt6.QtCore import QEvent, Qt
import matplotlib.pyplot as plt

CMAP_NOMBRE  = 'viridis'
COLOR_FONDO  = (0.08, 0.10, 0.13)   # Gris oscuro azulado moderno
COLOR_GRILLA = (0.25, 0.35, 0.45, 0.25)


class Grafica3DRealTime(QWidget):
    """
    Superficie 3D en tiempo real:
      · Aprovechamiento del 100% del canvas (sin barra lateral redundante)
      · Marcadores Z sincronizados dinámicamente con la deformación visual
      · Botón flotante 'A' para auto-escalado
    """

    def __init__(self, titulo_z: str = "Amplitud (µV)", titulo: str = ""):
        super().__init__()
        self.titulo_z      = titulo_z
        self.titulo_figura = titulo

        self._cmap_mpl = plt.get_cmap(CMAP_NOMBRE)

        # Estado interno
        self.surface_item     = None
        self.grid_item        = None
        self.axes_items       = []
        self.z_ticks_items    = []

        self.auto_scale       = True
        self.z_scale_factor   = 1.0

        self._dragging_z      = False
        self._drag_last_y     = 0

        self.font_tick  = QFont('Segoe UI', 8)
        self.font_label = QFont('Segoe UI', 9, QFont.Weight.Bold)

        self._construir_ui()
        self.mostrar_vista_previa()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Viewport 3D
        self.view = gl.GLViewWidget()
        r, g, b = COLOR_FONDO
        self.view.setBackgroundColor((int(r*255), int(g*255), int(b*255)))
        layout.addWidget(self.view)

        # Botón Flotante 'A' (Auto-Scale)
        self.btn_autoscale = QPushButton("A", self.view)
        self.btn_autoscale.setToolTip("Restablecer Escala Z Automática")
        self.btn_autoscale.setFixedSize(28, 28)
        self.btn_autoscale.setStyleSheet("""
            QPushButton {
                background-color: rgba(18, 24, 34, 220);
                color: #00E6C3;
                border: 1px solid rgba(0, 230, 195, 0.4);
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QPushButton:hover {
                background-color: rgba(0, 230, 195, 0.3);
                color: #FFFFFF;
                border: 1px solid #00E6C3;
            }
            QPushButton:pressed {
                background-color: rgba(0, 230, 195, 0.6);
            }
        """)
        self.btn_autoscale.clicked.connect(lambda: self.set_auto_z_scale(True))
        self.view.installEventFilter(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'btn_autoscale'):
            self.btn_autoscale.move(10, self.view.height() - 38)

    def mostrar_vista_previa(self):
        self.inicializar_malla(10.0, 10.0, 1.0)

    def inicializar_malla(self, x_max: float, y_max: float, res: float):
        self.x_max = max(float(x_max), 0.1)
        self.y_max = max(float(y_max), 0.1)
        self.res   = max(float(res), 0.001)

        self.nx    = int(self.x_max / self.res) + 1
        self.ny    = int(self.y_max / self.res) + 1
        self.xs    = np.linspace(0, self.x_max, self.nx)
        self.ys    = np.linspace(0, self.y_max, self.ny)
        self.z_raw = np.zeros((self.nx, self.ny))
        self.z_vis = np.zeros((self.nx, self.ny))

        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items    = []
        self.z_ticks_items = []

        if self.surface_item:
            self.view.removeItem(self.surface_item)
        if self.grid_item:
            self.view.removeItem(self.grid_item)

        # Grilla de piso
        self.grid_item = gl.GLGridItem()
        step_x = max(self.x_max / 10, 0.1)
        step_y = max(self.y_max / 10, 0.1)
        self.grid_item.setSize(self.x_max, self.y_max)
        self.grid_item.setSpacing(step_x, step_y)
        self.grid_item.setColor(COLOR_GRILLA)
        self.grid_item.translate(self.x_max / 2, self.y_max / 2, 0)
        self.view.addItem(self.grid_item)

        # Superficie 3D
        colores = self._z_a_colores(self.z_raw)
        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs, y=self.ys, z=self.z_vis,
            colors=colores, shader='shaded', smooth=True
        )
        self.view.addItem(self.surface_item)

        self._dibujar_ejes()
        self._ajustar_camara()

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
        altura_ref = max(self.x_max, self.y_max) * 0.4

        if self.auto_scale:
            scale = altura_ref / rng
            self.z_scale_factor = scale
        else:
            scale = self.z_scale_factor

        self.z_vis = (self.z_raw - z_min) * scale
        colores    = self._z_a_colores(self.z_raw)
        self.surface_item.setData(z=self.z_vis, colors=colores)

        altura_vis_actual = rng * scale
        self._actualizar_ticks_z(z_min, z_max, altura_vis_actual)
        self.view.update()

    def _z_a_colores(self, z: np.ndarray) -> np.ndarray:
        z_min = float(z.min())
        z_max = float(z.max())
        rng   = max(z_max - z_min, 1e-12)
        z_norm = (z - z_min) / rng
        return self._cmap_mpl(z_norm).reshape(-1, 4)

    def _dibujar_ejes(self):
        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items    = []
        self.z_ticks_items = []

        pasos = 5
        axis = gl.GLAxisItem()
        axis.setSize(self.x_max * 1.02, self.y_max * 1.02, max(self.x_max, self.y_max) * 0.4)
        self.view.addItem(axis)
        self.axes_items.append(axis)

        # X
        self._add_text((self.x_max * 1.08, -self.y_max * 0.05, 0), "X (mm)", self.font_label, (0, 230, 195, 230))
        for i in range(pasos + 1):
            v = self.x_max / pasos * i
            self._add_text((v, -self.y_max * 0.06, 0), f"{v:.1f}", self.font_tick, (160, 170, 180, 180))

        # Y
        self._add_text((-self.x_max * 0.05, self.y_max * 1.08, 0), "Y (mm)", self.font_label, (0, 230, 195, 230))
        for i in range(pasos + 1):
            v = self.y_max / pasos * i
            self._add_text((-self.x_max * 0.08, v, 0), f"{v:.1f}", self.font_tick, (160, 170, 180, 180))

        # Z (Ticks dinámicos en 3D)
        self.z_header_text = self._add_text((-self.x_max * 0.12, -self.y_max * 0.05, 1.0), self.titulo_z, self.font_label, (230, 230, 230, 240))
        for i in range(pasos + 1):
            t = gl.GLTextItem(pos=(0, 0, 0), text="", color=(0, 230, 195, 200), font=self.font_tick)
            self.view.addItem(t)
            self.axes_items.append(t)
            self.z_ticks_items.append(t)

    def _add_text(self, pos, text, font, color):
        t = gl.GLTextItem(pos=pos, text=text, color=color, font=font)
        self.view.addItem(t)
        self.axes_items.append(t)
        return t

    def _actualizar_ticks_z(self, z_min: float, z_max: float, altura_vis_actual: float):
        if not self.z_ticks_items:
            return

        pasos = len(self.z_ticks_items) - 1
        h_efectiva = max(altura_vis_actual, 0.01)

        self.z_header_text.setData(pos=(-self.x_max * 0.12, -self.y_max * 0.05, h_efectiva * 1.08))

        for i, tick in enumerate(self.z_ticks_items):
            frac   = i / pasos
            z_real = z_min + frac * (z_max - z_min)
            z_pos  = frac * h_efectiva

            if "µV" in self.titulo_z:
                label = f"{z_real*1e6:.2f} µV"
            elif "°" in self.titulo_z:
                label = f"{z_real:.1f}°"
            else:
                label = f"{z_real:.3g}"

            tick.setData(pos=(-self.x_max * 0.12, -self.y_max * 0.05, z_pos), text=label)

    def _ajustar_camara(self):
        cx, cy = self.x_max / 2, self.y_max / 2
        dist = max(self.x_max, self.y_max) * 1.8
        self.view.setCameraPosition(pos=QVector3D(cx, cy, 0), distance=dist, elevation=28, azimuth=45)

    def obtener_rango_z(self):
        """Retorna (min, max) de los datos Z crudos."""
        return float(self.z_raw.min()), float(self.z_raw.max())

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
            x=self.xs, y=self.ys, z=np.zeros_like(self.z_raw),
            colors=colores, shader='shaded', smooth=True
        )
        self.view.addItem(self.surface_item)

        self.auto_scale = True
        self._dibujar_ejes()
        self._ajustar_camara()
        self._recalcular_superficie()

    def eventFilter(self, obj, event):
        if obj != self.view:
            return False
        t = event.type()

        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
            self._dragging_z  = True
            self._drag_last_y = event.position().y()
            return True

        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.RightButton:
            self._dragging_z = False
            return True

        if t == QEvent.Type.MouseMove and self._dragging_z:
            py = event.position().y()
            dy = self._drag_last_y - py
            self._drag_last_y = py

            factor = 1.0 + dy * 0.008
            self.z_scale_factor *= max(0.2, min(5.0, factor))
            self.auto_scale = False
            self._recalcular_superficie()
            return True

        return False