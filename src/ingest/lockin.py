# src/ingest/lockin.py
import sys
import time
from pathlib import Path
import pyvisa
import numpy as np

raiz_proyecto = Path(__file__).resolve().parent.parent.parent

if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.constants.constants import Laser, LockIn

class SR830:
    def __init__(self, resource_name=LockIn.RESOURCE_NAME, timeout=LockIn.TIMEOUT, tc_constante=False):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout
        
        self.tc_constante = tc_constante
        
        self.TC_MAP = LockIn.TC_MAP
        
        self.current_tc_val = 0.3
        self.tiempo_espera = 1.0
        self.current_slope_factor = 5

    def set_frequency(self, freq, es_primero=False):
        """Establece frecuencia, ajusta TC y Slope, y espera al asentamiento."""
        if freq <= 0: return
        self.inst.write(f'FREQ {freq}')
        
        if self.tc_constante:
            # Configuración fija estándar
            indice_tc = 8 if freq < 300 else 7
            self._set_config_fija(indice_tc, slope_index=3) # 24 dB/oct por seguridad
        else:
            self._ajustar_dinamico(freq)

        wait_time = (10 if es_primero else self.current_slope_factor) * self.current_tc_val
        time.sleep(wait_time)
        
        if es_primero:
            self.get_measurements() 
            time.sleep(0.5)

    def _ajustar_dinamico(self, freq):
        """Ajuste automático de TC y Slope según la frecuencia."""
        if freq < 100:
            slope_index = 3
            self.current_slope_factor = 10 
        else:
            slope_index = 1
            self.current_slope_factor = 7  

        self.inst.write(f'OFSL {slope_index}')

        periodo_objetivo = 10.0 / freq 
        indice_optimo = 15 

        for i in sorted(self.TC_MAP.keys()):
            if self.TC_MAP[i] >= periodo_objetivo and self.TC_MAP[i] >= 30e-3:
                indice_optimo = i
                break
        
        self.inst.write(f'OFLT {indice_optimo}')
        self.current_tc_val = self.TC_MAP[indice_optimo]

    def _set_config_fija(self, tc_index, slope_index=3):
        """Aplica TC y Slope fijos."""
        self.inst.write(f'OFLT {tc_index}')
        self.inst.write(f'OFSL {slope_index}')
        self.current_tc_val = self.TC_MAP[tc_index]
        self.current_slope_factor = [5, 7, 9, 10][slope_index]

    def get_measurements(self):
        """SNAP? 1,2,3,4 obtiene X, Y, R, Theta"""
        try:
            snap = self.inst.query('SNAP? 1,2,3,4').strip()
            x, y, r, phi = map(float, snap.split(','))
            return {'X': x, 'Y': y, 'R': r, 'phi': phi}
        except Exception as e:
            print(f"Error en lectura: {e}")
            return None

    def set_amplitude(self, voltage):
        """Usamos el aux out 3 y una puerta and para encender y apagar el laser"""
        self.inst.write(f'AUXV 3, {voltage}')
        
    def close(self):
        """Cierra la conexion"""
        self.inst.close()
        self.rm.close()

    def auto_gain(self):
        """Ejecuta AGAN y espera a que el hardware termine el ajuste."""
        self.inst.write("AGAN")
        time.sleep(LockIn.DELAYAUTOGAIN)

    def Reserve(self):
        """Ponemos modo en Low Reserve para no destruir la señal del sensor"""
        self.inst.write("RMOD 2")
        time.sleep(LockIn.DELAYRESERVE)

if __name__ == "__main__":
    pass