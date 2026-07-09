# src/ingest/mesaxy.py
"""
Controlador de la mesa XY motorizada via serial.

Comunicación bidireccional con Arduino (AccelStepper firmware):
  Python → Arduino: HOME, SWEEP x y res, CRUZ x y, MOVE x y, ZERO, EN_OFF, CONT, ABORT
  Arduino → Python: READY, HOMED, POS x y, LASER, Fin, OK, ERR ...

Patrón de diseño: Inyección de Dependencias.
  Los generators接收 el dispositivo de medición (lockin) como parámetro
  externo, permitiendo inyectar tanto el hardware real (SR830) como un
  simulador (SR830Simulator) para debugging sin dispositivos físicos.

Protocolo de barrido XY (SWEEP):
  1. Python envía "SWEEP x_max y_max res"
  2. Arduino recorre la grilla en patrón serpentina
  3. En cada punto: envía "POS x y" → "LASER"
  4. Python mide lock-in → responde "CONT"
  5. Al terminar: Arduino envía "Fin"

Protocolo de barrido de frecuencia (CRUZ):
  1. Python envía "CRUZ x_max y_max"
  2. Arduino visita 5 puntos (esquinas + centro)
  3. En cada punto: envía "LASER"
  4. Python barre frecuencias → responde "CONT" por cada punto
"""

import sys
import time
from pathlib import Path

import numpy as np
import serial

raiz_proyecto = Path(__file__).resolve().parent.parent.parent
if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.constants.constants import TableXY, Laser


class MesaXY:
    """
    Controlador de la mesa XY via puerto serial.

    Gestiona la conexión con Arduino, el envío de comandos
    y la recepción de respuestas. Implementa los generators
    de barrido que integran mediciones del lock-in.
    """

    def __init__(
        self,
        port=TableXY.PORT,
        baudrate=TableXY.BAUDRATE,
        timeout=TableXY.TIMEOUT_SERIAL,
    ):
        """
        Abre la conexión serial con el Arduino.

        Args:
            port: Puerto serial (ej: 'COM3', '/dev/ttyUSB0')
            baudrate: Velocidad de comunicación (9600 por defecto)
            timeout: Timeout de lectura serial (segundos)

        Raises:
            RuntimeError: Si no se puede abrir el puerto o el Arduino no responde
        """
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception as e:
            raise RuntimeError(f"Error de conexión Arduino: {e}")

        self._abort = False
        self.origin_offset_x = 0.0
        self.origin_offset_y = 0.0

        time.sleep(1)  # Tiempo de estabilización del Arduino tras reset
        self._wait_for_ready()

    def _wait_for_ready(self):
        """
        Bloquea hasta que Arduino envíe "READY" o "HOMED".

        Raises:
            RuntimeError: Si no se recibe respuesta en TIMEOUT_READY segundos
        """
        start_time = time.time()
        while True:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8").strip()
                if line in ["READY", "HOMED"]:
                    return
            if time.time() - start_time > TableXY.TIMEOUT_READY:
                raise RuntimeError("El ARDUINO no respondió READY a tiempo.")

    def _send_command(self, cmd):
        """Envía un comando al Arduino (terminado en newline)."""
        self.ser.write((cmd + "\n").encode("utf-8"))

    def _pre_start_lockin(self, lockin_device, freq):
        """
        Configura el lock-in antes de iniciar un barrido.

        Secuencia de configuración:
          1. Establecer frecuencia de referencia
          2. Encender láser (5V)
          3. Esperar estabilización térmica (10s)
          4. Activar Low Reserve
          5. Ejecutar auto-ganancia
        """
        lockin_device.set_frequency(freq, True)
        lockin_device.set_amplitude(Laser.ON_VOLTAGE)
        time.sleep(TableXY.DELAY_PRE_START)
        lockin_device.Reserve()
        lockin_device.auto_gain()

    def sweep_and_measure_generator(self, lockin_device, x_max, y_max, res, f):
        """
        Generador de barrido XY completo.

        Recorre la grilla punto a punto, esperando el trigger "LASER"
        del Arduino en cada posición. Mide el lock-in y yield los datos.

        Args:
            lockin_device: Instancia de SR830 o SR830Simulator
            x_max: Extensión máxima del eje X (mm)
            y_max: Extensión máxima del eje Y (mm)
            res: Resolución de la grilla (mm)
            f: Frecuencia de modulación del láser (Hz)

        Yields:
            tuple: (x, y, data_dict) por cada punto medido
        """
        self._abort = False
        current_x, current_y = 0.0, 0.0

        # Configurar lock-in antes del barrido
        self._pre_start_lockin(lockin_device, f)

        # Iniciar movimiento en el Arduino
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd)

        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8").strip()
                if not line:
                    continue

                if line.startswith("POS"):
                    # Arduino reporta posición actual
                    try:
                        _, x_str, y_str = line.split()
                        current_x, current_y = float(x_str), float(y_str)
                    except ValueError:
                        pass

                elif line == "LASER":
                    # Arduino listo para medir en este punto
                    if self._abort:
                        break

                    # Esperar asentamiento del lock-in
                    time.sleep(lockin_device.tiempo_espera)
                    z_data = lockin_device.get_measurements()

                    yield current_x, current_y, z_data

                    # Indicar al Arduino que continúe
                    self._send_command("CONT")

                elif line == "Fin":
                    # Barrido completado
                    break
            else:
                time.sleep(0.001)

        # Apagar láser al terminar
        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)

    def cruz_frequency_generator(self, lockin_device, x_max, y_max, f_start, f_end, steps):
        """
        Generador de barrido de frecuencia en 5 puntos de cruce.

        Visita esquinas + centro de la mesa, y en cada punto barre
        todas las frecuencias del rango especificado.

        Args:
            lockin_device: Instancia de SR830 o SR830Simulator
            x_max: Extensión del eje X (mm)
            y_max: Extensión del eje Y (mm)
            f_start: Frecuencia inicial (Hz)
            f_end: Frecuencia final (Hz)
            steps: Número de frecuencias a medir

        Yields:
            tuple: (punto_idx, frecuencia, data_dict) por cada medición
        """
        self._abort = False

        cmd = f"CRUZ {x_max} {y_max}"
        self._send_command(cmd)

        freqs = np.linspace(f_start, f_end, steps)
        punto_actual = 0

        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode("utf-8").strip()
                if not line:
                    continue

                if line == "LASER":
                    if self._abort:
                        break

                    # Configurar lock-in para la primera frecuencia
                    self._pre_start_lockin(lockin_device, freqs[0])

                    # Barrer todas las frecuencias en este punto
                    for f in freqs:
                        if self._abort:
                            break
                        lockin_device.set_frequency(f, False)
                        time.sleep(lockin_device.tiempo_espera)
                        z_data = lockin_device.get_measurements()

                        yield punto_actual, f, z_data

                    lockin_device.set_amplitude(Laser.OFF_VOLTAGE)
                    punto_actual += 1
                    self._send_command("CONT")

                elif line == "Fin":
                    break
            else:
                time.sleep(0.001)

        # Apagar láser al terminar
        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)

    def disable(self):
        """Deshabilita los motores paso a paso (EN_OFF)."""
        self._send_command("EN_OFF")

    def stop_current_operation(self):
        """Detiene la operación actual: deshabilita motores y aborta."""
        self.disable()
        self._abort = True

    def home(self):
        """Ejecuta la secuencia de homing completa (30-60 segundos)."""
        self._send_command("HOME")
        self._wait_for_ready()
        self.origin_offset_x = 0.0
        self.origin_offset_y = 0.0

    def set_origin(self, logical_x=0.0, logical_y=0.0):
        """
        Establece el origen lógico en la posición actual.

        Args:
            logical_x: Coordenada X lógica a asignar (default 0)
            logical_y: Coordenada Y lógica a asignar (default 0)
        """
        self._send_command("ZERO")
        response = self.ser.readline().decode("utf-8").strip()
        if response != "OK":
            raise RuntimeError(f"set_origin failed: {response}")
        self.origin_offset_x += logical_x
        self.origin_offset_y += logical_y

    def close(self):
        """Cierra el puerto serial si está abierto."""
        if self.ser.is_open:
            self.ser.close()
