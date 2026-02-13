import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

class Grafica3DRealTime(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        
        # Widget de vista OpenGL
        self.view = gl.GLViewWidget()
        self.view.opts['distance'] = 20  # Distancia inicial de la cámara
        self.view.setWindowTitle('Superficie Fototérmica en Vivo')
        self.layout.addWidget(self.view)

        # Crear una rejilla de suelo para referencia
        gz = gl.GLGridItem()
        gz.translate(0, 0, 0)
        self.view.addItem(gz)
        
        self.surface_item = None
        self.x_grid = None
        self.y_grid = None
        self.z_grid = None

    def inicializar_malla(self, x_max, y_max, res):
        """Prepara la 'sábana' vacía basada en las dimensiones del barrido"""
        # Calcular vectores de coordenadas
        xs = np.arange(0, x_max + res, res)
        ys = np.arange(0, y_max + res, res)
        
        self.nx = len(xs)
        self.ny = len(ys)
        
        # Crear mallas 2D
        self.x_grid, self.y_grid = np.meshgrid(xs, ys)
        
        # Inicializar Z con ceros (o un valor base)
        self.z_grid = np.zeros((self.ny, self.nx))

        # Eliminar superficie anterior si existe
        if self.surface_item:
            self.view.removeItem(self.surface_item)

        # Crear el objeto de superficie OpenGL
        # shader='shaded' da el aspecto sólido con iluminación
        self.surface_item = gl.GLSurfacePlotItem(x=xs, y=ys, z=self.z_grid, shader='shaded')
        
        # Configurar colores (mapa de calor básico)
        self.surface_item.shader()['colorMap'] = np.array([0.2, 2, 0.5, 0.2, 1, 1, 0.2, 0, 2])
        
        self.view.addItem(self.surface_item)

    def actualizar_punto(self, x_val, y_val, z_val, res):
        """Actualiza un solo punto en la malla y refresca la vista"""
        if self.surface_item is None:
            return

        # Encontrar los índices correspondientes en la matriz
        ix = int(round(x_val / res))
        iy = int(round(y_val / res))

        # Protección contra índices fuera de rango
        if 0 <= ix < self.nx and 0 <= iy < self.ny:
            self.z_grid[iy, ix] = z_val
            
            # Actualizar la data en el objeto OpenGL
            self.surface_item.setData(z=self.z_grid)