import serial
import time
import numpy as np
# Asegúrate de que lockin.py esté accesible
try:
    from lockin import SR830, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
except ImportError:
    print("error con el lockin")

class MesaXY:
    def __init__(self, port='COM3', baudrate=9600, timeout=5):
        self.TIEMPO_DE_ESTABILIZACION = 1.5
        self.TIEMPO_DE_RELAJACION_TERMICA = 1.5

        self.lockin = SR830()
        # Bajamos un poco el timeout para que el hilo no sufra demasiado
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self._abort = False
        time.sleep(1) # El Arduino se reinicia al conectar
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
            self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
            self.disable() # Apagar motores
            self.lockin.close()
            time.sleep(0.1)
            if self.ser.is_open:
                self.ser.close()
        except Exception as e:
            print(f"Error cerrando: {e}")

    def ajustar_frecuencia(self,freq):
        self.lockin.set_frequency(freq)

    def sweep_and_measure_generator(self, x_max, y_max, res):
        """
        Generador sincronizado: 
        1. Recibe posición (POS) -> La guarda.
        2. Recibe gatillo (LASER) -> Mide y continúa.
        """
        self._abort = False
        current_x, current_y = 0.0, 0.0  # Nuestra "libreta" de coordenadas
        
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        
        cmd = f"SWEEP {x_max} {y_max} {res}"
        self._send_command(cmd)
        
        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                
                # A: Actualizar coordenadas en la libreta
                if line.startswith("POS"):
                    try:
                        _, x_str, y_str = line.split()
                        current_x, current_y = float(x_str), float(y_str)
                    except ValueError:
                        print(f"Error parseando posición: {line}")

                # B: Ejecutar la medición (El "Gatillo")
                elif line == "LASER":
                    if self._abort: break
                    
                    # --- SECUENCIA DE MEDICIÓN ---
                    self.ajustar_frecuencia(LASER_ON_VOLTAGE)
                    time.sleep(self.TIEMPO_DE_ESTABILIZACION)
                    
                    z_data = self.lockin.get_measurements()
                    print(f"Medido en ({current_x}, {current_y}): {z_data}")
                    
                    self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
                    
                    # Ceder datos a la GUI
                    yield current_x, current_y, z_data
                    
                    # Liberar al Arduino para el siguiente punto
                    self._send_command("CONT")

                elif line.startswith("ERR"):
                    raise RuntimeError(f"Arduino Error: {line}")
                
                elif line == "OK":
                    print("Barrido terminado con éxito.")
                    break
            else:
                time.sleep(0.01)

        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)

    def sweep_frequency_generator(self, f_start, f_end, steps, log_space=True):
        """
        Generador de barrido de frecuencia en un punto estático (0,0).
        """
        self._abort = False
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        
        self.disable() # El Arduino descansa
        
        # 2. Asegurar que el láser empiece apagado
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        
        # Generar frecuencias (En PTR el logspace es mejor para ver la difusión)
        if log_space:
            freqs = np.logspace(np.log10(f_start), np.log10(f_end), steps)
        else:
            freqs = np.linspace(f_start, f_end, steps)
        
        for f in freqs:
            if self._abort: break
            
            self.lockin.set_frequency(f)
            self.lockin.set_amplitude(LASER_ON_VOLTAGE)
            
            # --- EL PROBLEMA FÍSICO ---
            time.sleep(self.TIEMPO_DE_ESTABILIZACION) 
            
            # 5. Medir amplitud y fase
            z_data = self.lockin.get_measurements()
            
            yield f, z_data

            # 6. Apagar láser (Respiro térmico)
            self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
            
            # ¿Cuánto tiempo necesita la muestra para volver al equilibrio?
            time.sleep(self.TIEMPO_DE_RELAJACION_TERMICA)
            
            
        # Al terminar, asegurar que todo quede apagado
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        print("Barrido de frecuencia terminado.")
    
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