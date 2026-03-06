import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class Grafica2DRealTime(QWidget):
    def __init__(self, titulo="Gráfica 2D", log_x=True, log_y=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Aprovechar mejor el espacio
        
        # El PlotWidget es nuestro lienzo
        self.plot_widget = pg.PlotWidget(title=titulo)
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # --- LA CLAVE DEL CAMBIO ---
        # Configuramos los ejes según la necesidad (Bode pide X log)
        # Para Magnitud: log_y=True. Para Fase: log_y=False.
        self.plot_widget.setLogMode(x=log_x, y=log_y)
        
        # Curva de datos: Verde neón para que resalte
        self.curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#00FF00', width=2), 
            symbol='o', 
            symbolSize=4
        )
        
        self.f_data = []
        self.z_data = []
        layout.addWidget(self.plot_widget)

    def limpiar(self):
        """Reinicia los buffers de datos y limpia la curva"""
        self.f_data = []
        self.z_data = []
        self.curve.setData([], [])

    def actualizar(self, f, z):
        """
        Añade un punto y refresca.
        OJO: Si log_y es True, pyqtgraph aplicará log10(z) automáticamente.
        Asegúrate de que 'z' NUNCA sea <= 0 si el eje Y es logarítmico.
        """
        if f <= 0: return # Evitar que pyqtgraph colapse con log(0) en X
        
        self.f_data.append(f)
        self.z_data.append(z)
        self.curve.setData(self.f_data, self.z_data)