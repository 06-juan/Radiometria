import serial
import time
from graficar import graficar_superficie
from lockin import get_measurements

class MesaXY:
    def __init__(self, port='COM6', baudrate=9600, timeout=60):
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.data = []  # Lista para almacenar (x, y, z)
        time.sleep(2)  # Esperar a que Arduino se inicialice
        self._wait_for_ready()

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
                    print(f"Debug: {line}")
                    continue
                return line
            if time.time() - start_time > self.ser.timeout:
                raise TimeoutError(f"No response to command: {cmd}")

    def ping(self): #Verifiquemos la conexion de una forma chistosa jajaja
        response = self._send_command("PING")
        if response != "PONG":
            raise RuntimeError("PING failed")
        print("Ping successful")

    def enable(self):
        self._send_command("EN_ON")
        print("Motors enabled")

    def disable(self):
        self._send_command("EN_OFF")
        print("Motors disabled")

    def home(self):
        self._send_command("HOME")
        print("Homed")

    def test_move(self, x, y):
        cmd = f"TESTMOVE {x} {y}"
        self._send_command(cmd)
        print(f"Moved to ({x}, {y})")

    def measure(self):
        '''
        Se comunica con el lockin para tomar mediciones en el punto
        '''
        z = get_measurements()
        return z

    def sweep_and_measure(self, x_max, y_max, res):
        '''
        Recibe valor maximo de x y y que es el tamaño de muestra
        res es el valor de resolución en mm e.g (0.5) crea un punto cada 0.5mm
        Envia los tres valores al Arduino que se encarga del movimiento y delay
        Recibe confirmacion del Arduino cuando esta en poscicion
        Llama a lockin para que pase los datos en ese punto
        '''
        self.data = []  # Reiniciar datos
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd, wait_response=False)
        
        while True:
            line = self.ser.readline().decode('utf-8').strip()
            if not line:
                raise TimeoutError("No response during sweep")
            if line.startswith("POS"):
                _, x, y = line.split()
                x, y = float(x), float(y)
                z = self.measure() #es un diccionario con 4 variables que pasa el lockin
                self.data.append((x, y, z))
                print(f"Measured at ({x}, {y}): z={z}")
                self._send_command("CONT", wait_response=False)
            elif line == "OK":
                print("Sweep completed")
                break
            elif line.startswith("ERR"):
                raise RuntimeError(line)
            elif line.startswith("DBG"):
                print(f"Debug: {line}")

    def plot_3d(self):
        if not self.data:
            print("No data to plot")
            return

        x, y, z = zip(*self.data)  # z aquí es lista de diccionarios
        graficar_superficie(x, y, z)


    def close(self):
        self.disable()
        self.ser.close()

# Ejemplo de uso
if __name__ == "__main__":
    try:
        mesa = MesaXY(port='COM6')  # Ajustar puerto según el sistema
        mesa.ping()
        mesa.enable()
        mesa.home()
        mesa.sweep_and_measure(0.1, 0.1, 0.005)
        mesa.plot_3d()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        mesa.close()