import numpy as np
if not hasattr(np, 'product'):
    np.product = np.prod

import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QVector3D
import matplotlib.pyplot as plt

class Grafica3DRealTime(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Configuración de la vista 3D
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor('k') 
        self.layout.addWidget(self.view)

        # Estado interno
        self.surface_item = None
        self.axes_items = [] 
        self.cmap = plt.get_cmap('jet')
        self.z_max_historico = 1.0 

        # --- AQUÍ ESTÁ EL CAMBIO CLAVE ---
        # Al crear la clase, llamamos inmediatamente a la vista previa
        self.mostrar_vista_previa()

    def mostrar_vista_previa(self):
        """Dibuja un escenario 'dummy' de 10x10 para que no se vea negro al inicio."""
        # Simulamos un área de trabajo de 10x10 mm con resolución baja para visualización
        print("Generando vista previa del escenario...")
        self.inicializar_malla(x_max=10.0, y_max=10.0, res=1.0)
        
        # Forzamos una vista de cámara agradable
        self.view.setCameraPosition(pos=QVector3D(5, 5, 0), distance=30, elevation=30, azimuth=45)

    def inicializar_malla(self, x_max, y_max, res):
        self.x_max = x_max
        self.y_max = y_max
        self.nx = int(x_max / res) + 1
        self.ny = int(y_max / res) + 1
        
        # Generar coordenadas
        self.xs = np.linspace(0, x_max, self.nx)
        self.ys = np.linspace(0, y_max, self.ny)
        
        # Matriz Z inicial (Plana)
        self.z_grid = np.zeros((self.ny, self.nx))

        # Limpieza de objetos anteriores
        if self.surface_item:
            self.view.removeItem(self.surface_item)
            self.surface_item = None # Aseguramos referencia nula
            
        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items = []

        # 1. Crear Superficie (Inicialmente plana y azul oscuro o con el colormap en 0)
        # Para que se vea algo, aunque sea plano, usaremos el colormap en el valor min
        colores = self.cmap(np.zeros_like(self.z_grid))
        colores_flat = colores.reshape(-1, 4)

        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs, y=self.ys, z=self.z_grid, 
            colors=colores_flat, shader='shaded', smooth=False
        )
        self.view.addItem(self.surface_item)

        # 2. Dibujar Ejes y Números
        self._dibujar_ejes_enumerados(x_max, y_max)
        
        # NOTA: No forzamos la cámara aquí si ya estamos en modo interactivo, 
        # pero para el inicio sí sirve.

    def _dibujar_ejes_enumerados(self, x_max, y_max):
        # 1. Ejes base (Las líneas de colores: Rojo=X, Verde=Y, Azul=Z)
        axis = gl.GLAxisItem()
        z_height = max(x_max, y_max) * 0.5 
        axis.setSize(x_max, y_max, z_height)
        self.view.addItem(axis)
        self.axes_items.append(axis)
    
        # 2. Etiquetas de texto
        pasos = 5
        color_texto = (255, 255, 255, 255) # Blanco sólido
        
        # Elevación mínima para que el plano azul no tape el texto
        offset_z = 0.1 
    
        # EJE X
        for i in range(pasos + 1):
            val = (x_max / pasos) * i
            # Colocamos el texto un poco desplazado en Y para que no choque con la línea
            t = gl.GLTextItem(pos=(val, -y_max*0.1, offset_z), text=f"{val:.1f}", color=color_texto)
            # Probamos a escalar el texto si se ve muy pequeño (opcional)
            # t.scale(0.1, 0.1, 0.1) 
            self.view.addItem(t)
            self.axes_items.append(t)
    
        # EJE Y
        for i in range(pasos + 1):
            val = (y_max / pasos) * i
            t = gl.GLTextItem(pos=(-x_max*0.1, val, offset_z), text=f"{val:.1f}", color=color_texto)
            self.view.addItem(t)
            self.axes_items.append(t)
            
        # Etiqueta indicativa para Z
        t_z = gl.GLTextItem(pos=(0, 0, z_height + 1), text="Z (mm)", color=color_texto)
        self.view.addItem(t_z)
        self.axes_items.append(t_z)

    def actualizar_punto(self, x_val, y_val, z_val, res):
        if self.surface_item is None: return

        # Cálculo de índices más robusto
        ix = int(np.clip(round(x_val / res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / res), 0, self.ny - 1))

        # --- AUTO-ESCALA VISUAL ---
        if abs(z_val) > self.z_max_historico:
            self.z_max_historico = abs(z_val)
        
        # Queremos que la altura visual máxima sea proporcional al área XY
        visual_height_target = (self.x_max + self.y_max) / 2
        scale = visual_height_target / self.z_max_historico if self.z_max_historico > 1e-9 else 1.0

        self.z_grid[iy, ix] = z_val * scale

        # Coloreado
        z_min, z_max = self.z_grid.min(), self.z_grid.max()
        rng = z_max - z_min
        if rng > 1e-9:
            z_norm = (self.z_grid - z_min) / rng
        else:
            z_norm = np.zeros_like(self.z_grid)

        colores = self.cmap(z_norm).reshape(-1, 4)
        self.surface_item.setData(z=self.z_grid, colors=colores)