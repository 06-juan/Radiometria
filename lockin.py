import pyvisa
import time
import numpy as np

LASER_ON_VOLTAGE = 5
LASER_OFF_VOLTAGE = 0.6

class SR830:
    def __init__(self, resource_name='GPIB0::8::INSTR', timeout=10000, tc_constante=True):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout
        
        # Indica si usaremos 300ms fijo o ajuste automático
        self.tc_constante = tc_constante
        
        self.TC_MAP = {
            0: 10e-6, 1: 30e-6, 2: 100e-6, 3: 300e-6,
            4: 1e-3,  5: 3e-3,  6: 10e-3,  7: 30e-3,
            8: 100e-3, 9: 300e-3, 10: 1.0,  11: 3.0,
            12: 10.0, 13: 30.0, 14: 100.0, 15: 300.0
        }
        self.current_tc_val = 0.3
        self.tiempo_espera = 1.5

    def set_frequency(self, freq, es_primero=False):
        """Establece la frecuencia y decide qué TC aplicar."""
        if freq <= 0: return
        self.inst.write(f'FREQ {freq}')
        
        if self.tc_constante and freq <= 100:
            self._set_tc_fija(9) # Índice 9 = 300 ms
        elif self.tc_constante and freq >= 100:
            self._set_tc_fija(7)
        else:
            self._ajustar_tc_automatico(freq)

        factor = 10 if es_primero else 5 
        wait_time = factor * self.current_tc_val
        time.sleep(wait_time)
        
        if es_primero:
            # "Limpiamos" el buffer haciendo una lectura que nadie va a usar
            self.get_measurements() 
            time.sleep(0.5)

    def _set_tc_fija(self, indice):
        """Aplica una TC fija (por defecto 300ms)."""
        self.inst.write(f'OFLT {indice}')
        self.current_tc_val = self.TC_MAP[indice]
        self.tiempo_espera = 5 * self.current_tc_val
        
        time.sleep(self.tiempo_espera)

    def _ajustar_tc_automatico(self, freq):
        """Cálculo dinámico: TC >= 10 ciclos (TC >= 10/f)."""
        periodo_objetivo = 10.0 / freq 
        
        # Buscamos el índice adecuado en el hardware
        indice_optimo = 15 
        for i in sorted(self.TC_MAP.keys()):
            # Mantenemos un mínimo de 100ms para evitar ruido excesivo
            if self.TC_MAP[i] >= periodo_objetivo and self.TC_MAP[i] >= 100e-3:
                indice_optimo = i
                break
        
        self.inst.write(f'OFLT {indice_optimo}')
        self.current_tc_val = self.TC_MAP[indice_optimo]
        self.tiempo_espera = 5 * self.current_tc_val
        
        print(f"[SR830] MODO AUTO: Freq {freq:.2f}Hz -> TC {self.current_tc_val}s")
        time.sleep(self.tiempo_espera)

    def get_measurements(self):
        """SNAP? 1,2,3,4 obtiene X, Y, R, Theta de un solo golpe."""
        try:
            snap = self.inst.query('SNAP? 1,2,3,4').strip()
            x, y, r, phi = map(float, snap.split(','))
            return {'X': x, 'Y': y, 'R': r, 'phi': phi}
        except Exception as e:
            print(f"Error en lectura: {e}")
            return None

    def set_amplitude(self,voltage):
        """Usamos el aux out 3 y una puerta and para encender y apagar el laser
        ya que TTL out no se puede detener"""
        self.inst.write(f'AUXV 3, {voltage}')
        
    def close(self):
        self.inst.close()
        self.rm.close()

if __name__ == "__main__":
    # Ejemplo de uso:
    try:
        # Para el barrido XY, mejor tc_constante=True
        lockin = SR830(tc_constante=True)
        
        #for f in [100, 300, 500, 700]:
            #lockin.set_frequency(f)
            #datos = lockin.get_measurements()
            #print(f"Resultado a {f}Hz: {datos}")
            
        #lockin.close()
        lockin.set_amplitude(LASER_ON_VOLTAGE)
        #lockin.set_amplitude(LASER_OFF_VOLTAGE)
    except Exception as e:
        print(f"Falla de conexión: {e}")