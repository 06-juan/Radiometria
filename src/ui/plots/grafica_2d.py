import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

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
        # Colores extraídos de la escala Viridis (6 niveles uniformes)
        self.colors = [
            '#440154', # Morado oscuro (inicio)
            '#414487', # Azul violáceo
            '#2a788e', # Azul verdoso
            '#22a884', # Verde esmeralda
            '#7ad151', # Verde lima
            '#fde725'  # Amarillo (final)
        ]
        layout.addWidget(self.plot_widget)

    def _on_clicked(self, event):
        "Muestra coordenadas al hacer click, o pantalla completa al hacer doble clic"""
        if event.double() and event.button() == Qt.MouseButton.LeftButton:
            self.toggle_fullscreen()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            if self.plot_widget.sceneBoundingRect().contains(pos):
                mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
                x, y = mouse_point.x(), mouse_point.y()
                
                # Si el eje es logarítmico, el valor real es 10^v
                real_x = 10**x if self.log_x else x
                real_y = 10**y if self.log_y else y
                
                self.label.setText(f"Freq: {real_x:.1f} Hz\nVal: {real_y:.1f}")
                self.label.setPos(x, y)
                self.label.show()
                # Ocultar después de 3 segundos
                QTimer.singleShot(2000, self.label.hide)

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
    
    def toggle_fullscreen(self):
        """Mueve el widget a un diálogo a pantalla completa y permite regresar con Esc."""
        if hasattr(self, 'dialogo_fs') and self.dialogo_fs.isVisible():
            return

        self.layout_original = self.parentWidget().layout() if self.parentWidget() else None
        if not self.layout_original:
            return

        self.dialogo_fs = QDialog(self.window())
        self.dialogo_fs.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        layout_fs = QVBoxLayout(self.dialogo_fs)
        layout_fs.setContentsMargins(0, 0, 0, 0)
        
        layout_fs.addWidget(self)
        
        def al_cerrar(event):
            self.layout_original.addWidget(self)
            event.accept()
            
        self.dialogo_fs.closeEvent = al_cerrar
        
        atajo = QShortcut(QKeySequence("Esc"), self.dialogo_fs)
        atajo.activated.connect(self.dialogo_fs.close)
        
        self.dialogo_fs.showFullScreen()