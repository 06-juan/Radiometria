# src/ingest/mesaxy.py
import sys
import time
from pathlib import Path
import serial
import numpy as np

raiz_proyecto = Path(__file__).resolve().parent.parent.parent
if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.constants.constants import TableXY, Laser


class MesaXY:
    def __init__(self, port=TableXY.PORT, baudrate=TableXY.BAUDRATE, timeout=TableXY.TIMEOUT_SERIAL):
        try:
            # Conexión exclusiva del Arduino
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception as e:
            raise RuntimeError(f"Error de conexión Arduino: {e}")
        
        self._abort = False
        time.sleep(1) 
        self._wait_for_ready()

    def _wait_for_ready(self):
        start_time = time.time()
        while True:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if line in ["READY", "HOMED"]: 
                    return
            if time.time() - start_time > TableXY.TIMEOUT_READY:
                raise RuntimeError("El ARDUINO no respondió READY a tiempo.")

    def _send_command(self, cmd):
        self.ser.write((cmd + "\n").encode('utf-8'))

    def _pre_start_lockin(self, lockin_device, freq):
        """Configura el Lock-In externo antes de iniciar un movimiento."""
        lockin_device.set_frequency(freq, True)
        lockin_device.set_amplitude(Laser.ON_VOLTAGE)
        time.sleep(TableXY.DELAY_PRE_START) 
        lockin_device.Reserve()
        lockin_device.auto_gain()

    def sweep_and_measure_generator(self, lockin_device, x_max, y_max, res, f):
        """Barrido XY inyectando el dispositivo de medición de forma externa."""
        self._abort = False
        current_x, current_y = 0.0, 0.0
        
        # 1. Configurar el equipo externo que nos pasaron
        self._pre_start_lockin(lockin_device, f)
        
        # 2. Iniciar movimiento
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd)
        
        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                
                if line.startswith("POS"):
                    try:
                        _, x_str, y_str = line.split()
                        current_x, current_y = float(x_str), float(y_str)
                    except ValueError: pass

                elif line == "LASER":
                    if self._abort: break
                    
                    # Medimos usando el objeto lockin inyectado
                    time.sleep(lockin_device.tiempo_espera) 
                    z_data = lockin_device.get_measurements()
                    
                    yield current_x, current_y, z_data
                    self._send_command("CONT")

                elif line == "Fin": 
                    break
            else:
                time.sleep(0.001)

        # Al terminar, apagamos el láser usando el lockin inyectado
        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)
    
    def cruz_frequency_generator(self, lockin_device, x_max, y_max, f_start, f_end, steps):
        """Barrido en frecuencia inyectando el dispositivo de medición."""
        self._abort = False

        cmd = f"CRUZ {x_max} {y_max}"
        self._send_command(cmd)
        
        freqs = np.linspace(f_start, f_end, steps)
        punto_actual = 0
        
        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                
                if line == "LASER":
                    if self._abort: break

                    self._pre_start_lockin(lockin_device, freqs[0])
                    
                    for f in freqs:
                        if self._abort: break
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

        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)

    def disable(self):
        self._send_command("EN_OFF")

    def stop_current_operation(self):
        self.disable()
        self._abort = True

    def home(self):
        self._send_command("HOME")
        self._wait_for_ready()

    def close(self):
        if self.ser.is_open: 
            self.ser.close()