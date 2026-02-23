import serial
import time
import numpy as np
try:
    from lockin import SR830, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
except ImportError:
    print("Error importando el controlador del Lock-in")

class MesaXY:
    def __init__(self, port='COM3', baudrate=9600, timeout=5):
        self.TIEMPO_DE_RELAJACION_TERMICA = 0.005
        self.lockin = SR830()
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
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
            if time.time() - start_time > 80:
                raise RuntimeError("El ARDUINO no respondió READY a tiempo.")

    def _send_command(self, cmd):
        self.ser.write((cmd + "\n").encode('utf-8'))

    def ajustar_frecuencia(self, freq):
        """Ajusta frecuencia y maneja automáticamente la TC y la espera."""
        self.lockin.set_frequency(freq)

    def sweep_and_measure_generator(self, x_max, y_max, res, freq_actual):
        """Barrido espacial XY. Ajusta la TC antes de empezar."""
        self._abort = False
        current_x, current_y = 0.0, 0.0
        
        # 1. Ajuste crítico de TC antes de medir cualquier punto
        self.ajustar_frecuencia(freq_actual)
        
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
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
                    self.lockin.set_amplitude(LASER_ON_VOLTAGE)
                    
                    # La espera de estabilización ya ocurrió en ajustar_frecuencia

                    time.sleep(self.lockin.tiempo_espera) 
                    
                    z_data = self.lockin.get_measurements()
                    self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
                    yield current_x, current_y, z_data
                    self._send_command("CONT")

                elif line == "OK": break
            else:
                time.sleep(0.01)

    def sweep_frequency_generator(self, f_start, f_end, steps, log_space=False):
        """Barrido de frecuencia. Ajusta la TC en cada paso automáticamente."""
        self._abort = False
        self.disable()
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        
        if log_space:
            freqs = np.logspace(np.log10(f_start), np.log10(f_end), steps)
        else:
            freqs = np.linspace(f_start, f_end, steps)
        
        for f in freqs:
            if self._abort: break
            
            # 2. Ajuste automático: cambia frecuencia, cambia TC y ESPERA 5*TC
            self.ajustar_frecuencia(f)
            
            self.lockin.set_amplitude(LASER_ON_VOLTAGE)
            time.sleep(self.lockin.tiempo_espera) 
            z_data = self.lockin.get_measurements()
            yield f, z_data
            self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
            time.sleep(self.TIEMPO_DE_RELAJACION_TERMICA)
            
        print("Barrido de frecuencia terminado.")
    
    def stop_current_operation(self):
        """Detenemos bucle de medicion"""
        self._abort = True

    def disable(self):
        self._send_command("EN_OFF")

    def home(self):
        self._send_command("HOME")
        self._wait_for_ready()

    def close(self):
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        self.lockin.close()
        if self.ser.is_open: self.ser.close()