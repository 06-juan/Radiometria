import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class Grafica2DRealTime(QWidget):
    def __init__(self, titulo="Respuesta en Frecuencia"):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Configuración del PlotWidget
        self.plot_widget = pg.PlotWidget(title=titulo)
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Eje X Logarítmico (esencial para PTR)
        self.plot_widget.setLogMode(x=True, y=False)
        
        # Curva de datos
        self.curve = self.plot_widget.plot(pen=pg.mkPen(color='#00FF00', width=2), symbol='o', symbolSize=5)
        
        self.f_data = []
        self.z_data = []
        layout.addWidget(self.plot_widget)

    def limpiar(self):
        self.f_data = []
        self.z_data = []
        self.curve.setData([], [])

    def actualizar(self, f, z):
        self.f_data.append(f)
        self.z_data.append(z)
        self.curve.setData(self.f_data, self.z_data)