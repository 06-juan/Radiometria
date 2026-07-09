# src/ui/workers.py
"""
Hilos de ejecución (QThread) para operaciones de hardware bloqueantes.

Cada worker ejecuta una tarea pesada en segundo plano y comunica
el resultado al hilo principal mediante señales Qt. Esto mantiene
la GUI responsiva durante barridos, homing y conexiones.

Workers:
  - HomeWorker:        Ejecuta la secuencia de homing de la mesa
  - WorkerThread:      Barrido XY (3D) punto a punto
  - CruzWorkerThread:  Barrido de frecuencia (2D) en puntos de cruce
  - ConnectWorker:     Conexión a Arduino + SR830 (o fallback a simulación)
"""

from PyQt6.QtCore import QThread, pyqtSignal


class HomeWorker(QThread):
    """
    Ejecuta la secuencia de homing de la mesa XY en un hilo separado.

    Señales:
      - finished_signal: Homing completado exitosamente
      - error_signal(str): Fallo durante el homing (mensaje de error)
    """

    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

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
    """
    Hilo de barrido XY (medición 3D).

    Recorre una grilla de puntos (x, y) usando el generador
    sweep_and_measure_generator de la mesa. En cada punto,
    emite la posición y los datos del lock-in.

    Señales:
      - data_signal(float, float, dict): Punto medido (x, y, {X,Y,R,phi})
      - finished_signal: Barrido completado
      - error_signal(str): Error durante el barrido
    """

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
                f=self.freq,
            )
            for x, y, data in generator:
                self.data_signal.emit(x, y, data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class CruzWorkerThread(QThread):
    """
    Hilo de barrido de frecuencia (medición 2D).

    Visita 5 puntos de cruce (esquinas + centro) y en cada uno
    barre un rango de frecuencias. Emite el índice del punto,
    la frecuencia y los datos del lock-in.

    Señales:
      - data_signal(int, float, dict): Dato (índice punto, frecuencia, {X,Y,R,phi})
      - finished_signal: Barrido completado
      - error_signal(str): Error durante el barrido
    """

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
            generator = self.mesa.cruz_frequency_generator(
                lockin_device=self.lockin,
                x_max=self.x_max,
                y_max=self.y_max,
                f_start=self.f_start,
                f_end=self.f_end,
                steps=self.steps,
            )
            for idx, f, data in generator:
                self.data_signal.emit(idx, f, data)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))


class ConnectWorker(QThread):
    """
    Hilo de conexión al hardware (Arduino + SR830).

    Intenta conectarse al SR830 (GPIB) y al Arduino (serial).
    Si alguno falla y sim_mode=False, emite error_signal con el
    motivo. El orquestador puede luego ofrecer activar simulación.

    Señales:
      - success_signal(object, object): (mesa, lockin) conectados
      - error_signal(str): Fallo de conexión (descripción del error)
      - warning_signal(str): Aviso de modo simulación activo
    """

    success_signal = pyqtSignal(object, object)
    error_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)

    def __init__(self, port="COM3", sim_mode=False):
        super().__init__()
        self.port = port
        self.sim_mode = sim_mode

    def run(self):
        # ── Modo simulación forzado por CLI ──
        if self.sim_mode:
            from src.ingest.simulador import SR830Simulator, MesaXYSimulator

            self.warning_signal.emit(
                "Modo simulación: hardware ficticio activo (--sim)"
            )
            self.success_signal.emit(MesaXYSimulator(), SR830Simulator())
            return

        # ── Intento de conexión a hardware real ──
        lockin_inst = None
        mesa_inst = None
        errores = []

        # 1. Conectar SR830 (lock-in) por GPIB
        try:
            from src.ingest.lockin import SR830

            lockin_inst = SR830()
        except Exception as e:
            errores.append(f"SR830 (GPIB): {e}")

        # 2. Conectar Arduino (mesa XY) por serial
        try:
            from src.ingest.mesaxy import MesaXY

            mesa_inst = MesaXY(port=self.port)
        except Exception as e:
            errores.append(f"Arduino (Serial): {e}")

        # 3. Evaluar resultado
        if lockin_inst and mesa_inst:
            # Ambos conectados correctamente
            self.success_signal.emit(mesa_inst, lockin_inst)

        elif lockin_inst or mesa_inst:
            # Conexión parcial: uno funciona, el otro falló
            conectado = "SR830" if lockin_inst else "Arduino"
            fallo = "Arduino" if lockin_inst else "SR830"
            self.error_signal.emit(
                f"Conexión parcial: {conectado} conectado, "
                f"{fallo} falló.\n"
                f"Detalles: {'; '.join(errores)}\n\n"
                f"¿Deseas continuar en modo simulación?"
            )

        else:
            # Ninguno conectado
            self.error_signal.emit(
                f"No se pudo conectar al hardware:\n"
                + "\n".join(errores)
                + "\n\n¿Deseas iniciar modo simulación?"
            )
