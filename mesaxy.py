import serial
import time
from lockin import get_measurements, set_amplitude, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
from graficar import graficar_superficie
# La función de graficar ahora se llama desde la GUI, no desde aquí.
# from graficar_seaborn import graficar_superficie 

class MesaXY:
    def __init__(self, port='COM6', baudrate=9600, timeout=60):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.data = []  # Lista para almacenar (x, y, z)
        self.log_callback = None  # Callback para enviar logs a la GUI
        time.sleep(2)
        self._wait_for_ready()

    def _log(self, message):
        """Envía un mensaje al callback de log si está definido, si no, lo imprime."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _wait_for_ready(self):
        start_time = time.time()
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            if line == "READY":
                return
            if time.time() - start_time > self.ser.timeout:
                raise TimeoutError("Arduino no respondió READY")

    def _send_command(self, cmd, wait_response=True):
        self.ser.write((cmd + "\n").encode('utf-8'))
        if not wait_response:
            return None
        start_time = time.time()
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            if line:
                if line.startswith("ERR"):
                    raise RuntimeError(line)
                if line.startswith("DBG"):
                    self._log(f"Debug: {line}")
                    continue
                return line
            if time.time() - start_time > self.ser.timeout:
                raise TimeoutError(f"No response to command: {cmd}")

    def ping(self):
        response = self._send_command("PING")
        if response != "PONG":
            raise RuntimeError("PING failed")

    def enable(self):
        self._send_command("EN_ON")

    def disable(self):
        self._send_command("EN_OFF")

    def home(self):
        self._send_command("HOME")
        self._send_command("EN_OFF")

    def measure(self):
        z = get_measurements()
        return z

    def sweep_and_measure(self, x_max, y_max, res):
        self.x = []
        self.y = []
        self.z = []
        
        # 1. Asegurar láser APAGADO antes de empezar a moverse
        set_amplitude(LASER_OFF_VOLTAGE)
        time.sleep(0.1) # Breve espera para asegurar que el láser reaccione
        
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd, wait_response=False)
        
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            
            if not line:
                # Si no hay línea, a veces es mejor continuar que lanzar error inmediato 
                # a menos que sea timeout real.
                continue 
                
            if line.startswith("POS"):
                # EL ARDUINO YA LLEGÓ A LA POSICIÓN
                _, x, y = line.split()
                x, y = float(x), float(y)
                self.x.append(x)
                self.y.append(y)
                
                # 2. Encender Láser
                set_amplitude(LASER_ON_VOLTAGE)
                
                # 3. Esperar estabilización (importante para el Lock-in)
                # El Lock-in necesita unos milisegundos para estabilizar la lectura
                # tras el encendido repentino de la señal.
                time.sleep(0.5)  # Ajusta este tiempo según la constante de tiempo (Time Constant) de tu Lock-in
                
                # 4. Medir
                z = self.measure()
                
                # 5. Apagar Láser inmediatamente después de medir
                set_amplitude(LASER_OFF_VOLTAGE)
                
                if z is None:
                    # Manejo de error suave, o lanzar excepción
                    self._log("Error midiendo, reintentando o saltando punto...")
                else:
                    self.z.append(z)
                    self._log(f"Medido en ({x:.4f}, {y:.4f}): R={z['R']:.4e} V")
                
                # 6. Decirle al Arduino que continúe al siguiente punto
                self._send_command("CONT", wait_response=False)

            elif line == "OK":
                self._log("Barrido completado.")
                break
            elif line.startswith("ERR"):
                raise RuntimeError(line)
            elif line.startswith("DBG"):
                self._log(f"Debug: {line}")

        # Asegurar que quede apagado al terminar
        set_amplitude(LASER_OFF_VOLTAGE)
        self._send_command("EN_OFF")

    def plot_3d(self):
        if not self.x or not self.y or not self.z:
            self._log("No hay datos para graficar.")
            return
        graficar_superficie(self.x, self.y, self.z)

    def close(self):
        try:
            set_amplitude(LASER_OFF_VOLTAGE)
        except:
            pass
        try:
            self.disable()
        except Exception as e:
            self._log(f"Advertencia: No se pudo deshabilitar motores al cerrar. {e}")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

# El bloque __main__ se elimina, ya que la ejecución ahora es desde gui_estacion.py