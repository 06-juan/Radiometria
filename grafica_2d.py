import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

class Grafica2DRealTime(QWidget):
    def __init__(self, titulo="Gráfica 2D", log_x=False, log_y=False):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Aprovechar mejor el espacio
        
        # Guardamos el estado
        self.log_x = log_x
        self.log_y = log_y

        # El PlotWidget es nuestro lienzo
        self.plot_widget = pg.PlotWidget(title=titulo)
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Seteamos el log mode.
        self.plot_widget.setLogMode(x=log_x, y=log_y)

        # Si es logarítmico, forzamos un formateador de etiquetas más robusto
        if log_x:
            ay = self.plot_widget.getAxis('bottom')
            # Intentar que pyqtgraph no oculte los ticks menores/mayores tan agresivamente
            ay.setTickSpacing(major=1.0, minor=1.0) 
        
        # Etiqueta para mostrar coordenadas
        self.label = pg.TextItem(anchor=(0, 1), color='w', fill=(0, 0, 0, 150))
        self.plot_widget.addItem(self.label)
        self.label.hide()

        # Conectar evento de click
        self.plot_widget.scene().sigMouseClicked.connect(self._on_clicked)
        
        # Guardaremos múltiples curvas
        self.curves = []
        self.f_data_list = []
        self.z_data_list = []
        
        # Colores para múltiples curvas
        self.colors = ['#00FF00', '#FF0000', '#00FFFF', '#FFFF00', '#FF00FF', '#0000FF']
        
        layout.addWidget(self.plot_widget)

    def _on_clicked(self, event):
        """Muestra coordenadas al hacer click"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if self.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
                x, y = mouse_point.x(), mouse_point.y()
                
                # Si el eje es logarítmico, el valor real es 10^v
                real_x = 10**x if self.log_x else x
                real_y = 10**y if self.log_y else y
                
                self.label.setText(f"Freq: {real_x:.2f} Hz\nVal: {real_y:.2f}")
                self.label.setPos(x, y)
                self.label.show()
                # Ocultar después de 3 segundos
                QTimer.singleShot(3000, self.label.hide)

    def _ensure_curve(self, curve_idx):
        """Asegura que exista la curva para el índice dado."""
        while len(self.curves) <= curve_idx:
            color = self.colors[len(self.curves) % len(self.colors)]
            new_curve = self.plot_widget.plot(
                pen=pg.mkPen(color=color, width=2), 
                symbol='o', 
                symbolSize=1,
                name=f"Punto {len(self.curves)+1}"
            )
            self.curves.append(new_curve)
            self.f_data_list.append([])
            self.z_data_list.append([])

    def set_datos_completos(self, x_data, y_data, curve_idx=0):
        """Renderizado instantáneo para datos históricos."""
        self._ensure_curve(curve_idx)
        self.f_data_list[curve_idx] = list(x_data)
        self.z_data_list[curve_idx] = list(y_data)
        self.curves[curve_idx].setData(self.f_data_list[curve_idx], self.z_data_list[curve_idx])
        
    def limpiar(self):
        """Limpia los buffers de la gráfica y elimina curvas."""
        for curve in self.curves:
            self.plot_widget.removeItem(curve)
        self.curves = []
        self.f_data_list = []
        self.z_data_list = []

    def actualizar(self, f, z, curve_idx=0):
        """
        Añade un punto y refresca en la curva especificada por curve_idx.
        OJO: Si log_y es True, pyqtgraph aplicará log10(z) automáticamente.
        Asegúrate de que 'z' NUNCA sea <= 0 si el eje Y es logarítmico.
        """
        if f <= 0: return # Evitar que pyqtgraph colapse con log(0) en X
        
        self._ensure_curve(curve_idx)
        
        self.f_data_list[curve_idx].append(f)
        self.z_data_list[curve_idx].append(z)
        self.curves[curve_idx].setData(self.f_data_list[curve_idx], self.z_data_list[curve_idx])