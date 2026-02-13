import numpy as np
# Parche para compatibilidad con NumPy 2.0
if not hasattr(np, 'product'):
    np.product = np.prod

import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt

class Grafica3DRealTime(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Configuración de la vista 3D
        self.view = gl.GLViewWidget()
        self.view.opts['distance'] = 40
        self.view.opts['elevation'] = 30
        self.view.opts['azimuth'] = 45
        self.view.setBackgroundColor('k') # Fondo negro para que resalte el arcoíris
        self.layout.addWidget(self.view)

        # Grillas de referencia
        self.crear_grillas()

        self.surface_item = None
        self.z_grid = None
        # Cambiado a 'jet' para el efecto Rainbow (arcoíris)
        self.cmap = plt.get_cmap('jet') 

        # FACTOR DE ESCALA VISUAL
        self.z_scale_factor = 100000.0 

    def crear_grillas(self):
        gz = gl.GLGridItem()
        gz.translate(0, 0, 0)
        self.view.addItem(gz)

    def inicializar_malla(self, x_max, y_max, res):
        # Asegurar que el rango incluya el punto final
        self.xs = np.arange(0, x_max + res, res)
        self.ys = np.arange(0, y_max + res, res)
        
        self.nx = len(self.xs)
        self.ny = len(self.ys)
        
        self.z_grid = np.zeros((self.ny, self.nx))

        if self.surface_item:
            self.view.removeItem(self.surface_item)

        # Inicializamos la superficie
        # Usamos shader=None para que los colores que mandamos manualmente se vean puros
        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs, 
            y=self.ys, 
            z=self.z_grid, 
            shader='shaded', # 'shaded' permite ver relieve con los colores
            smooth=False
        )
        self.view.addItem(self.surface_item)
        print(f"Malla inicializada: {self.nx}x{self.ny} puntos.")

    def actualizar_punto(self, x_val, y_val, z_val, res):
        if self.surface_item is None:
            return

        # 1. Calcular índices
        ix = int(round(x_val / res))
        iy = int(round(y_val / res))

        if 0 <= ix < self.nx and 0 <= iy < self.ny:
            # Aplicar escala visual
            z_visual = z_val * self.z_scale_factor
            self.z_grid[iy, ix] = z_visual
            
            # --- CÁLCULO DE COLORES (RAINBOW) ---
            z_min = self.z_grid.min()
            z_max = self.z_grid.max()
            diff = z_max - z_min
            
            # Normalizamos Z entre 0 y 1 para el mapa de colores
            if diff > 1e-15:
                z_norm = (self.z_grid - z_min) / diff
            else:
                z_norm = np.zeros_like(self.z_grid)

            # Obtenemos los colores RGBA usando el colormap 'jet' (Arcoíris)
            # colores_grid tendrá forma (11, 11, 4)
            colores_grid = self.cmap(z_norm) 

            # ¡AQUÍ ESTÁ EL TRUCO! 
            # Aplanamos los colores a (121, 4) para evitar que pyqtgraph se confunda con los índices
            colores_flat = colores_grid.reshape(-1, 4)

            # 2. ACTUALIZAR GRÁFICA
            # Pasamos la matriz Z normal y los colores aplanados
            self.surface_item.setData(z=self.z_grid, colors=colores_flat)
            
            # Debug opcional
            print(f"Punto graficado: {ix}, {iy} - Color calculado")