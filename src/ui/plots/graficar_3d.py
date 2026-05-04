import os
import sys
import numpy as np

# --- COMPATIBILIDAD CRÍTICA PARA LINUX/WAYLAND ---
os.environ["QT_QPA_PLATFORM"] = "xcb"
os.environ["VTK_SILENT_ERRORS"] = "ON"
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"
# -------------------------------------------------

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import QTimer, Qt
import pyvista as pv
from pyvistaqt import QtInteractor

class Grafica3DRealTime(QWidget):
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

    sys.exit(app.exec())