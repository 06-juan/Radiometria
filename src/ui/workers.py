# src/ui/workers.py
from PyQt6.QtCore import QThread, pyqtSignal
from src.ingest.lockin import SR830 
from src.ingest.mesaxy import MesaXY


class HomeWorker(QThread):
    finished_signal = pyqtSignal()
    error_signal    = pyqtSignal(str)

    def __init__(self, mesa_instance):
        super().__init__()
        self.mesa = mesa_instance

    def run(self):
        try:
            if self.mesa:
                self.mesa.home()
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class WorkerThread(QThread):
    """Hilo encargado del barrido 3D (XY)"""
    data_signal = pyqtSignal(float, float, dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, mesa, lockin, x_max, y_max, res, freq):
        super().__init__()
        self.mesa = mesa
        self.lockin = lockin  
        self.x_max = x_max
        self.y_max = y_max
        self.res = res
        self.freq = freq

    def run(self):
        try:
            generator = self.mesa.sweep_and_measure_generator(
                lockin_device=self.lockin, 
                x_max=self.x_max, 
                y_max=self.y_max, 
                res=self.res, 
                f=self.freq
            )
            for x, y, data in generator:
                self.data_signal.emit(x, y, data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class CruzWorkerThread(QThread):
    """Hilo encargado del barrido 2D (Cruz de frecuencia)"""
    data_signal = pyqtSignal(int, float, dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, mesa, lockin, x_max, y_max, f_start, f_end, steps):
        super().__init__()
        self.mesa = mesa
        self.lockin = lockin  
        self.x_max = x_max
        self.y_max = y_max
        self.f_start = f_start
        self.f_end = f_end
        self.steps = steps

    def run(self):
        try:
            # CORREGIDO: Se eliminó el argumento 'lockin_device' que estaba duplicado
            generator = self.mesa.cruz_frequency_generator(
                lockin_device=self.lockin,
                x_max=self.x_max,
                y_max=self.y_max,
                f_start=self.f_start,
                f_end=self.f_end,
                steps=self.steps
            )
            for idx, f, data in generator:
                self.data_signal.emit(idx, f, data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class ConnectWorker(QThread):
    success_signal = pyqtSignal(object, object) 
    error_signal   = pyqtSignal(str)

    def __init__(self, port='COM3'):
        super().__init__()
        self.port = port

    def run(self):
        try:
            lockin_instancia = SR830()
            mesa_instancia = MesaXY(port=self.port)
            self.success_signal.emit(mesa_instancia, lockin_instancia)
        except Exception as e:
            self.error_signal.emit(str(e))