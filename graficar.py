import sys
import numpy as np
if not hasattr(np, 'product'):
    np.product = np.prod

import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt6.QtGui import QVector3D, QFont
from PyQt6.QtCore import QTimer
import matplotlib.pyplot as plt


class Grafica3DRealTime(QWidget):
    def __init__(self, titulo_z="R (µV)"): # <--- Añadimos el título por defecto
        super().__init__()
        self.titulo_z_texto = titulo_z # Guardamos el nombre del eje
        
        # Definimos una fuente pequeña para los ejes
        self.font_ejes = QFont('Arial', 8) 
        # Definimos una fuente un poco más grande para el título del eje
        self.font_titulo = QFont('Arial', 10, QFont.Weight.Bold)

        self.layout = QVBoxLayout()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Vista 3D
        self.view = gl.GLViewWidget()
        self.view.setBackgroundColor('k')
        self.layout.addWidget(self.view)

        # Estado interno
        self.surface_item = None
        self.axes_items = []
        self.cmap = plt.get_cmap('gist_rainbow')

        self.z_max_historico = 1e-9
        self.z_scale_factor = 1.0
        self.auto_scale = True

        self.mostrar_vista_previa()

    # ---------------------------------------------------------
    # CONFIGURACIÓN GENERAL
    # ---------------------------------------------------------

    def ajustar_camara(self, x_max, y_max):
        centro_x = x_max / 2
        centro_y = y_max / 2
        distancia_optima = max(x_max, y_max) * 1.8

        self.view.setCameraPosition(
            pos=QVector3D(centro_x, centro_y, 0),
            distance=distancia_optima,
            elevation=30,
            azimuth=45
        )

    def mostrar_vista_previa(self):
        self.inicializar_malla(100.0, 100.0, 2.0)

    def inicializar_malla(self, x_max, y_max, res):
        self.x_max = x_max
        self.y_max = y_max
        self.res = res

        self.nx = int(x_max / res) + 1
        self.ny = int(y_max / res) + 1

        self.xs = np.linspace(0, x_max, self.nx)
        self.ys = np.linspace(0, y_max, self.ny)

        self.z_raw = np.zeros((self.ny, self.nx))
        self.z_grid = np.zeros((self.ny, self.nx))

        self.z_max_historico = 1e-9

        if self.surface_item:
            self.view.removeItem(self.surface_item)

        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items = []

        colores = self.cmap(np.zeros_like(self.z_grid)).reshape(-1, 4)

        self.surface_item = gl.GLSurfacePlotItem(
            x=self.xs,
            y=self.ys,
            z=self.z_grid,
            colors=colores,
            shader='shaded',
            smooth=False
        )

        self.view.addItem(self.surface_item)

        self._dibujar_ejes_enumerados()
        self.ajustar_camara(x_max, y_max)

    # ---------------------------------------------------------
    # ESCALADO Z
    # ---------------------------------------------------------

    def set_z_scale(self, factor):
        self.z_scale_factor = max(factor, 1e-12)
        self.auto_scale = False
        self._recalcular_superficie()

    def set_auto_z_scale(self, enabled=True):
        self.auto_scale = enabled
        self._recalcular_superficie()

    def _recalcular_superficie(self):
        if self.surface_item is None:
            return

        visual_height_target = max(self.x_max, self.y_max) * 0.4

        if self.auto_scale:
            scale = visual_height_target / max(self.z_max_historico, 1e-9)
        else:
            scale = self.z_scale_factor

        self.z_grid = self.z_raw * scale

        # Normalización color
        z_min = self.z_raw.min()
        z_max = self.z_raw.max()
        rng = z_max - z_min

        if rng > 1e-12:
            z_norm = (self.z_raw - z_min) / rng
        else:
            z_norm = np.zeros_like(self.z_raw)

        colores = self.cmap(z_norm).reshape(-1, 4)
        self.surface_item.setData(z=self.z_grid, colors=colores)

        self._actualizar_eje_z_visual(z_min, z_max)

    # ---------------------------------------------------------
    # EJE Z CON MAGNITUD REAL
    # ---------------------------------------------------------

    def _dibujar_ejes_enumerados(self):
        # Limpiar items previos de ejes si existen
        for item in self.axes_items:
            self.view.removeItem(item)
        self.axes_items = []

        axis = gl.GLAxisItem()
        z_height = max(self.x_max, self.y_max) * 0.4
        axis.setSize(self.x_max, self.y_max, z_height)
        self.view.addItem(axis)
        self.axes_items.append(axis)

        pasos = 5

        # --- ETIQUETA Z PRINCIPAL (Pasamos la fuente aquí mismo) ---
        self.z_label = gl.GLTextItem(
            pos=(0, 0, z_height * 1.2),
            text=self.titulo_z_texto,
            color=(255, 255, 255, 200),
            font=self.font_titulo  # <--- SE PASA COMO ARGUMENTO
        )
        self.view.addItem(self.z_label)
        self.axes_items.append(self.z_label)

        # --- MARCAS Z DINÁMICAS ---
        self.z_ticks = []
        for i in range(pasos + 1):
            tick = gl.GLTextItem(
                pos=(0, 0, 0), 
                text="", 
                color=(255, 255, 255, 120),
                font=self.font_ejes  # <--- FUENTE PEQUEÑA AQUÍ
            )
            self.view.addItem(tick)
            self.axes_items.append(tick)
            self.z_ticks.append(tick)

        # --- EJE X ---
        t_x = gl.GLTextItem(
            pos=(self.x_max*1.1, -self.y_max*0.1, 0), 
            text="X mm", 
            color=(255,255,255,150),
            font=self.font_ejes
        )
        self.view.addItem(t_x)
        self.axes_items.append(t_x)

        for i in range(pasos + 1):
            val = (self.x_max / pasos) * i
            t = gl.GLTextItem(
                pos=(val, -self.y_max*0.1, 0), 
                text=f"{val:.1f}", 
                color=(255,255,255,100),
                font=self.font_ejes
            )
            self.view.addItem(t)
            self.axes_items.append(t)

        # --- EJE Y ---
        t_y = gl.GLTextItem(
            pos=(-self.x_max*0.1, self.y_max * 1.1, 0), 
            text="Y mm", 
            color=(255,255,255,150),
            font=self.font_ejes
        )
        self.view.addItem(t_y)
        self.axes_items.append(t_y)

        for i in range(pasos + 1):
            val = (self.y_max / pasos) * i
            t = gl.GLTextItem(
                pos=(-self.x_max*0.1, val, 0), 
                text=f"{val:.1f}", 
                color=(255,255,255,100),
                font=self.font_ejes
            )
            self.view.addItem(t)
            self.axes_items.append(t)

    def _actualizar_eje_z_visual(self, z_min, z_max):
        visual_height_target = max(self.x_max, self.y_max) * 0.4
        pasos = len(self.z_ticks) - 1

        for i in range(pasos + 1):
            frac = i / pasos
            z_real = z_min + frac * (z_max - z_min)
            z_visual = frac * visual_height_target

            # Formateo dinámico según el título
            if "µV" in self.titulo_z_texto:
                texto_tick = f"{z_real*1e6:.2f} µV"
            else:
                texto_tick = f"{z_real:.1f}°"

            self.z_ticks[i].setData(pos=(0, 0, z_visual), text=texto_tick)

    # ---------------------------------------------------------
    # ACTUALIZACIÓN DE DATOS
    # ---------------------------------------------------------

    def actualizar_punto(self, x_val, y_val, z_val):
        ix = int(np.clip(round(x_val / self.res), 0, self.nx - 1))
        iy = int(np.clip(round(y_val / self.res), 0, self.ny - 1))

        self.z_raw[iy, ix] = z_val

        abs_z = abs(z_val)
        if abs_z > self.z_max_historico:
            self.z_max_historico = abs_z

        self._recalcular_superficie()


# ---------------------------------------------------------
# PRUEBA AUTOMÁTICA
# ---------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = Grafica3DRealTime()
    ventana.resize(900, 700)
    ventana.show()

    # Generador de señal tipo onda viajera en microvoltios
    t = 0

    def actualizar():
        global t
        t += 0.1
        for x in np.linspace(0, ventana.x_max, 10):
            for y in np.linspace(0, ventana.y_max, 10):
                z = 5e-6 * np.sin(0.1*x + 0.1*y + t)
                ventana.actualizar_punto(x, y, z)

    timer = QTimer()
    timer.timeout.connect(actualizar)
    timer.start(50)

    sys.exit(app.exec())
