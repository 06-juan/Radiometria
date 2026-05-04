import os
import sys

# --- ESTO ES LO MÁS IMPORTANTE PARA WAYLAND ---
# Forzamos a Qt a usar X11 en lugar de Wayland nativo
os.environ["QT_QPA_PLATFORM"] = "xcb"
# Evita errores de memoria con drivers de video en modo compatibilidad
os.environ["VTK_SILENT_ERRORS"] = "ON"
# En algunos casos, Wayland necesita saber cuál es el display
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"
# ----------------------------------------------

import numpy as np
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt
import pyvista as pv
from pyvistaqt import QtInteractor

class Grafica3DRealTime(QWidget):
    def __init__(self, titulo_z: str = "Amplitud (µV)"):
        super().__init__()
        self.setWindowTitle("Radiometría 3D (X11 Compatibility Mode)")
        self.resize(1000, 700)
        
        # Estado de la malla
        self.x_max, self.y_max, self.res = 100.0, 100.0, 2.0
        self.nx = int(self.x_max / self.res) + 1
        self.ny = int(self.y_max / self.res) + 1
        
        self._setup_ui()
        
        # Inicialización diferida (clave para evitar el crash al arrancar)
        QTimer.singleShot(500, self.inicializar_visualizacion)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Creamos el plotter
        self.plotter = QtInteractor(self)
        self.plotter.set_background("#1e1e1e")
        layout.addWidget(self.plotter)

    def inicializar_visualizacion(self):
        # Crear datos iniciales
        self.xs = np.linspace(0, self.x_max, self.nx)
        self.ys = np.linspace(0, self.y_max, self.ny)
        self.z_raw = np.zeros((self.nx, self.ny))
        
        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        self._mesh = pv.StructuredGrid(xx, yy, self.z_raw)
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')

        self.plotter.add_mesh(
            self._mesh, 
            scalars="z_valor", 
            cmap="viridis", 
            name="malla_principal",
            show_edges=False
        )
        self.plotter.show_grid(color="gray")
        self.plotter.reset_camera()
        self.plotter.render()

    def actualizar_punto(self, x_val, y_val, z_val):
        if not hasattr(self, '_mesh'): return
        
        ix = int(np.clip(round(x_val / self.res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / self.res), 0, self.ny - 1))
        self.z_raw[ix, iy] = z_val
        
        # Actualizar geometría
        xx, yy = np.meshgrid(self.xs, self.ys, indexing='ij')
        puntos = np.column_stack([
            xx.ravel(order='F'),
            yy.ravel(order='F'),
            self.z_raw.ravel(order='F')
        ])
        self._mesh.points = puntos
        self._mesh["z_valor"] = self.z_raw.ravel(order='F')
        self.plotter.render()

    def closeEvent(self, event):
        self.plotter.close()
        event.accept()

if __name__ == "__main__":
    # Compartir contextos es vital en Linux
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    
    gui = Grafica3DRealTime()
    gui.show()

    # Simulación de tiempo real
    t = [0]
    def timer_event():
        t[0] += 0.1
        rx = np.random.uniform(0, 100)
        ry = np.random.uniform(0, 100)
        rz = np.sin(t[0] + rx/20) * 10
        gui.actualizar_punto(rx, ry, rz)

    timer = QTimer()
    timer.timeout.connect(timer_event)
    timer.start(30)

    sys.exit(app.exec())