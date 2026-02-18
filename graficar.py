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
        self.cmap = plt.get_cmap('gist_rainbow')
        self.z_max_historico = 1.0 

        # Al crear la clase, llamamos inmediatamente a la vista previa
        self.mostrar_vista_previa()

    def ajustar_camara(self, x_max, y_max):
        """Calcula el centro y la distancia óptima dinámicamente."""
        centro_x = x_max / 2
        centro_y = y_max / 2
        # Usamos el lado más largo para determinar la distancia y que nada quede fuera
        distancia_optima = max(x_max, y_max) * 1.8 
        
        self.view.setCameraPosition(
            pos=QVector3D(centro_x, centro_y, 0), 
            distance=distancia_optima, 
            elevation=30, 
            azimuth=45
        )

    def mostrar_vista_previa(self):
        """Escenario inicial de 100x100."""
        print("Generando vista previa del escenario...")
        self.inicializar_malla(100.0, 100.0, 1.0)

    def inicializar_malla(self, x_max, y_max, res):
        self.x_max = x_max
        self.y_max = y_max
        self.nx = int(x_max / res) + 1
        self.ny = int(y_max / res) + 1
        
        # Generar coordenadas
        self.xs = np.linspace(0, x_max, self.nx)
        self.ys = np.linspace(0, y_max, self.ny)
        
        # Matriz Z inicial (Plana)
        # 1. Matriz para valores REALES (sin escalar)
        self.z_raw = np.zeros((self.ny, self.nx))
        # 2. Matriz para valores VISUALES (escalados para el eje Z)
        self.z_grid = np.zeros((self.ny, self.nx))
        
        self.z_max_historico = 1e-9 # Evitar división por cero

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
        
        # Ajustamos la cámara a las nuevas dimensiones (ya sea 100x100 o 10x10)
        self.ajustar_camara(x_max, y_max)

    def _dibujar_ejes_enumerados(self, x_max, y_max):
        # Ejes base
        axis = gl.GLAxisItem()
        # Hacemos que el eje Z visualmente tenga una altura similar a X/Y para referencia
        z_height = max(x_max, y_max) * 0.5 
        axis.setSize(x_max, y_max, z_height)
        self.view.addItem(axis)
        self.axes_items.append(axis)

        # Etiquetas (Grilla de texto)
        pasos = 5
        # X
        t_x = gl.GLTextItem(pos=(x_max*1.2, -y_max*0.2, 0), text="X mm", color=(255,255,255,100))
        self.view.addItem(t_x)
        self.axes_items.append(t_x)

        for i in range(pasos + 1):
            val = (x_max / pasos) * i
            t = gl.GLTextItem(pos=(val, -y_max*0.2, 0), text=f"{val:.1f}", color=(255,255,255,100))
            self.view.addItem(t)
            self.axes_items.append(t)
        # Y
        t_y = gl.GLTextItem(pos=(-x_max*0.15, y_max * 1.2, 0), text="Y mm", color=(255,255,255,100))
        self.view.addItem(t_y)
        self.axes_items.append(t_y)

        for i in range(pasos + 1):
            val = (y_max / pasos) * i
            t = gl.GLTextItem(pos=(-x_max*0.15, val, 0), text=f"{val:.1f}", color=(255,255,255,100))
            self.view.addItem(t)
            self.axes_items.append(t)
            
        # Etiqueta Z (flotando)
        t_z = gl.GLTextItem(pos=(0, 0, z_height), text="R µV", color=(255,255,255,100))
        self.view.addItem(t_z)
        self.axes_items.append(t_z)

    def actualizar_punto(self, x_val, y_val, z_val, res):
        if self.surface_item is None: return

        # 1. Buscar índices
        ix = int(np.clip(round(x_val / res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / res), 0, self.ny - 1))

        # 2. Guardar el valor REAL
        self.z_raw[iy, ix] = z_val
        
        # 3. Actualizar el máximo histórico con el valor real
        abs_z = abs(z_val)
        if abs_z > self.z_max_historico:
            self.z_max_historico = abs_z

        # 4. RE-ESCALAR TODA LA MATRIZ VISUAL
        # Queremos que el punto más alto siempre mida, por ejemplo, el 40% de la base
        visual_height_target = max(self.x_max, self.y_max) * 0.4
        scale = visual_height_target / self.z_max_historico
        
        # Aplicamos la escala a todos los puntos para que la montaña sea proporcional
        self.z_grid = self.z_raw * scale

        # 5. Coloreado (usando los datos reales para el color)
        z_min, z_max = self.z_raw.min(), self.z_raw.max()
        rng = z_max - z_min
        
        if rng > 1e-9:
            z_norm = (self.z_raw - z_min) / rng
        else:
            z_norm = np.zeros_like(self.z_raw)

        # 6. Actualizar el ítem 3D
        colores = self.cmap(z_norm).reshape(-1, 4)
        # IMPORTANTE: pyqtgraph a veces espera (nx, ny). 
        # Si ves la gráfica rotada, usa self.z_grid.T
        self.surface_item.setData(z=self.z_grid, colors=colores)