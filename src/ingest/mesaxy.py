import serial
import time
import numpy as np
try:
    from src.ingest.lockin import SR830, LASER_ON_VOLTAGE, LASER_OFF_VOLTAGE
except ImportError:
    print("Error importando el controlador del Lock-in")

class MesaXY:
    def __init__(self, port='COM3', baudrate=9600, timeout=5):
        try:
            self.lockin = SR830()
        except:
            print("Error conectando el lockin")
            #hacer que el error sea en la ventana emergente de gui
            raise()
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self._abort = False
        time.sleep(1) 
        self._wait_for_ready()
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)

    def _wait_for_ready(self):
        start_time = time.time()
        while True:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if line in ["READY", "HOMED"]: 
                    return
            if time.time() - start_time > 100:
                raise RuntimeError("El ARDUINO no respondió READY a tiempo.")

    def _send_command(self, cmd):
        self.ser.write((cmd + "\n").encode('utf-8'))

    def ajustar_frecuencia(self, freq, es_primero=False):
        """Ajusta frecuencia y maneja automáticamente la TC y la espera."""
        self.lockin.set_frequency(freq, es_primero)

    def sweep_and_measure_generator(self, x_max, y_max, res):
        """
        Barrido optimizado: Mantiene el láser encendido para preservar 
        el equilibrio térmico y elimina tiempos de espera mecánicos redundantes.
        """
        self._abort = False
        current_x, current_y = 0.0, 0.0
        
        # 1. PREPARACIÓN: Encendemos el láser ANTES de empezar el movimiento
        # Esto permite que la muestra alcance una temperatura base.
        self.lockin.set_amplitude(LASER_ON_VOLTAGE)
        
        # Espera inicial de seguridad para que el primer punto no sea un transitorio
        time.sleep(5.0) 
        
        self.lockin.Reserve()
        
        self.lockin.auto_gain()

        # 2. INICIO DEL COMANDO
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
                    # El Arduino ya llegó a la posición y frenó.
                    if self._abort: break
                    
                    # 3. ESPERA FÍSICA: Solo el tiempo necesario para el filtro del Lock-in
                    # No apagamos el láser, solo esperamos la estabilización de la señal AC.
                    time.sleep(self.lockin.tiempo_espera) 
                    
                    # 4. CAPTURA DE DATOS
                    z_data = self.lockin.get_measurements()
                    
                    # Enviamos señal de continuar inmediatamente
                    yield current_x, current_y, z_data
                    self._send_command("CONT")

                elif line == "Fin": 
                    break
            else:
                time.sleep(0.001) # Mínimo respiro para el procesador

        # 5. CIERRE: Solo apagamos al terminar todo el barrido
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
    
    def cruz_frequency_generator(self, x_max, y_max, f_start, f_end, steps, log_space=False):
        """Barrido en frecuencia en los 5 puntos de alineación (CRUZ)."""
        self._abort = False

        # 1. INICIO DEL COMANDO
        cmd = f"CRUZ {x_max} {y_max}"
        self._send_command(cmd)
        
        if log_space:
            freqs = np.logspace(np.log10(f_start), np.log10(f_end), steps)
        else:
            freqs = np.linspace(f_start, f_end, steps)
            
        punto_actual = 0

        self.lockin.Reserve() #ajustamos reserve del lockin
        
        while not self._abort:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if not line: continue
                
                if line.startswith("POS"):
                    pass
                elif line == "LASER":
                    if self._abort: break

                    self.ajustar_frecuencia(freqs[0],True)
                    self.lockin.set_amplitude(LASER_ON_VOLTAGE)
                    time.sleep(self.lockin.tiempo_espera + 2)
                    
                    self.lockin.auto_gain()
                    
                    # 3. Barrido de Frecuencia en este punto
                    for f in freqs:
                        if self._abort: break
                        self.ajustar_frecuencia(f)
                        
                        time.sleep(self.lockin.tiempo_espera) 
                        z_data = self.lockin.get_measurements()
                        
                        # Enviamos índice del punto (para curva distinta en GUI)
                        yield punto_actual, f, z_data
                        
                        
                        #time.sleep(self.TIEMPO_DE_RELAJACION_TERMICA)
                    self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
                    punto_actual += 1
                    
                    # Le pedimos al Arduino que continúe al siguiente punto
                    self._send_command("CONT")

                elif line == "Fin": 
                    break
            else:
                time.sleep(0.001)

        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)

    def disable(self):
        self._send_command("EN_OFF")

    def stop_current_operation(self):
        """Detenemos bucle de medicion"""
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        self.disable()
        self._abort = True

    def home(self):
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        self._send_command("HOME")
        self._wait_for_ready()

    def close(self):
        self.lockin.set_amplitude(LASER_OFF_VOLTAGE)
        self.lockin.close()
        if self.ser.is_open: self.ser.close()