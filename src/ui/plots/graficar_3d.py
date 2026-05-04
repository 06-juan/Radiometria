"""
Grafica3D — motor PyVista + pyvistaqt
======================================
· Colorbar nativa con unidades reales
· Cámara auto-ajustable (reset_camera())
· Ejes con labels correctos (set_axes_labels)
· Rotación / zoom / pan con mouse sin configuración extra
· Grilla incluida
· Colormap científico (viridis por defecto)
·
Uso idéntico al código anterior:
    g = Grafica3DCientifica(titulo_z="Amplitud (µV)")
    g.inicializar_malla(100.0, 100.0, 2.0)
    g.actualizar_punto(x, y, z)
    g.cargar_datos_completos(x_max, y_max, res, z_grid_2d)
"""

import sys
import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer
import pyvista as pv
from pyvistaqt import QtInteractor

CMAP        = "viridis"   # plasma | RdBu_r | inferno | coolwarm
FONDO       = "#1e1e1e"   # gris oscuro neutro


class Grafica3DRealTime(QWidget):
    def __init__(self, titulo_z: str = "Amplitud (µV)"):
        super().__init__()
        self.titulo_z = titulo_z

        # estado interno
        self.x_max = 10.0
        self.y_max = 10.0
        self.res   = 1.0
        self.nx = self.ny = 0
        self.xs = self.ys = None
        self.z_raw = None
        self._mesh  = None
        self._actor = None

        self._construir_ui()
        self.mostrar_vista_previa()

    # ─────────────────────────── UI ──────────────────────────────────────────

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plotter = QtInteractor(self)
        self.plotter.set_background(FONDO)
        layout.addWidget(self.plotter)

        # ejes con labels
        self.plotter.show_axes()

    # ─────────────────────────── MALLA ───────────────────────────────────────

    def mostrar_vista_previa(self):
        self.inicializar_malla(100.0, 100.0, 2.0)

    def inicializar_malla(self, x_max: float, y_max: float, res: float):
        self.x_max = x_max
        self.y_max = y_max
        self.res   = res
        self.nx    = int(x_max / res) + 1
        self.ny    = int(y_max / res) + 1
        self.xs    = np.linspace(0, x_max, self.nx)
        self.ys    = np.linspace(0, y_max, self.ny)
        self.z_raw = np.zeros((self.nx, self.ny))

        self._reconstruir_mesh()

    def _reconstruir_mesh(self):
        """Crea (o recrea) el mesh PyVista a partir de xs, ys, z_raw."""
        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        self._mesh = pv.StructuredGrid(xx, yy, self.z_raw)
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')

        self.plotter.clear()

        scalar_bar_args = dict(
            title=self.titulo_z,
            title_font_size=12,
            label_font_size=10,
            shadow=False,
            italic=False,
            fmt="%.3g",
            vertical=True,
            position_x=0.88,
            position_y=0.1,
            width=0.08,
            height=0.7,
            color="white",
        )

        self._actor = self.plotter.add_mesh(
            self._mesh,
            scalars="z_valor",
            cmap=CMAP,
            show_edges=False,
            smooth_shading=True,
            scalar_bar_args=scalar_bar_args,
        )

        # Ejes con labels
        self.plotter.show_grid(
            xtitle="X (mm)",
            ytitle="Y (mm)",
            ztitle=self.titulo_z,
            font_size=10,
            color="white",
        )

        self.plotter.reset_camera()

    # ─────────────────────────── ACTUALIZACIÓN ───────────────────────────────

    def actualizar_punto(self, x_val: float, y_val: float, z_val: float):
        ix = int(np.clip(round(x_val / self.res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / self.res), 0, self.ny - 1))
        self.z_raw[ix, iy] = z_val
        self._actualizar_surface()

    def _actualizar_surface(self):
        if self._mesh is None:
            return

        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        # Actualizar coordenadas Z del mesh y scalar
        puntos = np.column_stack([xx.ravel(order='F'),
                                   yy.ravel(order='F'),
                                   self.z_raw.ravel(order='F')])
        self._mesh.points = puntos
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')

        self.plotter.render()

    def cargar_datos_completos(self, x_max: float, y_max: float,
                                res: float, z_grid: np.ndarray):
        self.x_max = x_max
        self.y_max = y_max
        self.res   = res
        self.z_raw = np.asarray(z_grid, dtype=float).copy()
        self.nx, self.ny = self.z_raw.shape
        self.xs = np.linspace(0, x_max, self.nx)
        self.ys = np.linspace(0, y_max, self.ny)
        self._reconstruir_mesh()


# ─────────────────────────────────────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)

    ventana = Grafica3DRealTime(titulo_z="Amplitud (µV)")
    ventana.resize(1000, 700)
    ventana.setWindowTitle("Mapa 3D — tiempo real (PyVista)")
    ventana.show()

    t_sim = 0.0

    def actualizar():
        global t_sim
        t_sim += 0.08
        for x in np.linspace(0, ventana.x_max, 20):
            for y in np.linspace(0, ventana.y_max, 20):
                z = 5e-6 * np.sin(0.08*x + 0.06*y + t_sim) * \
                    np.exp(-0.003 * ((x - 50)**2 + (y - 50)**2))
                ventana.actualizar_punto(x, y, z)

    timer = QTimer()
    timer.timeout.connect(actualizar)
    timer.start(60)

    sys.exit(app.exec())