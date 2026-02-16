import serial
import time
# Asegúrate de que lockin.py esté accesible
try:
    from lockin import get_measurements, set_amplitude, set_frequency, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
except ImportError:
    # MOCK para pruebas si no está el hardware conectado
    def get_measurements(): return {'R': 0.0, 'X':0, 'Y':0, 'phi':0}
    def set_amplitude(v): pass
    LASER_ON_VOLTAGE = 2.5
    LASER_OFF_VOLTAGE = 1.0

class MesaXY:
    def __init__(self, port='COM3', baudrate=9600, timeout=5):
        # Bajamos un poco el timeout para que el hilo no sufra demasiado
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self._abort = False
        time.sleep(2) # El Arduino se reinicia al conectar
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

    def stop_current_operation(self):
        """Activa la bandera para detener el bucle de medición"""
        self._abort = True

    def close(self):
        """Secuencia de apagado seguro"""
        try:
            self.stop_current_operation()
            set_amplitude(LASER_OFF_VOLTAGE)
            self._send_command("EN_OFF") # Apagar motores
            time.sleep(0.1)
            if self.ser.is_open:
                self.ser.close()
        except Exception as e:
            print(f"Error cerrando: {e}")

    def ajustar_frecuencia(self,freq):
        set_frequency(freq)


    def sweep_and_measure_generator(self, x_max, y_max, res):
        """
        Generador que cede el control (yield) en cada punto.
        Esto permite que la GUI se actualice y procese el STOP.
        """
        z_data={}
        self._abort = False
        
        # 1. Asegurar láser APAGADO al inicio
        set_amplitude(LASER_OFF_VOLTAGE)
        time.sleep(0.01)
        
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd)
        
        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                
                if not line: continue
                
                if line.startswith("POS"):
                    # Parsear posición
                    _, x_str, y_str = line.split()
                    x, y = float(x_str), float(y_str)
                    
                    # --- SECUENCIA DE MEDICIÓN ---
                    if self._abort: break # Chequeo de última hora
                    
                    set_amplitude(LASER_ON_VOLTAGE)
                    time.sleep(1.5) # Tiempo de estabilización térmica/Lock-in
                    
                    z_data = get_measurements()
                    
                    print(x,y, z_data)

                    set_amplitude(LASER_OFF_VOLTAGE)
                    
                    # Devolvemos el dato a la GUI
                    yield x, y, z_data
                    
                    # Decirle al Arduino que continúe
                    self._send_command("CONT")

                elif line.startswith("ERR"):
                                    raise RuntimeError(f"Arduino Error: {line}")
                
                elif line == "OK":
                    print("Barrido terminado legalmente.")
                    break
            # Pequeña pausa para no saturar CPU mientras espera serial
            else:
                time.sleep(0.01)

        # Limpieza final si se salió del loop
        set_amplitude(LASER_OFF_VOLTAGE)

    def home(self):
        self._send_command("HOME")
        self._wait_for_ready()

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