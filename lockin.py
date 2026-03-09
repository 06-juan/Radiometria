import pyvisa
import time
import numpy as np

# Constantes de configuración para el láser
LASER_ON_VOLTAGE = 5  
LASER_OFF_VOLTAGE = 0.6 

class SR830:
    def __init__(self, resource_name='GPIB0::8::INSTR', timeout=10000):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout
        
        # Mapeo de índices de OFLT del manual del SR830
        # Índice: Valor en segundos
        self.TC_MAP = {
            0: 10e-6, 1: 30e-6, 2: 100e-6, 3: 300e-6,
            4: 1e-3,  5: 3e-3,  6: 10e-3,  7: 30e-3,
            8: 100e-3, 9: 300e-3, 10: 1.0,  11: 3.0,
            12: 10.0, 13: 30.0, 14: 100.0, 15: 300.0
        }
        self.current_tc_val = 1.0 # Valor por defecto inicial
        self.tiempo_espera = 3.0 # Valor por defecto inicial para evitar AttributeError

    def set_amplitude(self, voltage):
        self.inst.write(f'SLVL {voltage}')

    def set_frequency(self, freq):
        """Establece frecuencia y ajusta automáticamente la TC y el tiempo de espera."""
        self.inst.write(f'FREQ {freq}')
        self._ajustar_tc_automatico(freq)

    def _ajustar_tc_automatico(self, freq):
        """
        Calcula la TC óptima (10 ciclos: TC >= 10/f).
        Selecciona el índice de hardware adecuado y espera 5*TC.
        """
        # Evitar división por cero
        if freq <= 0: return
        
        periodo_objetivo = 10.0 / freq #de 5 a 10
        
        #if periodo_objetivo <= 0.03: 
        #    periodo_objetivo = 0.03

        # Buscamos el índice más pequeño cuyo valor sea >= al periodo objetivo
        indice_optimo = 15 # Empezamos por el máximo por seguridad
        for i in sorted(self.TC_MAP.keys()):
            if self.TC_MAP[i] >= periodo_objetivo:
                indice_optimo = i
                break
        
        # Enviamos comando de Time Constant al Lock-in
        self.inst.write(f'OFLT {indice_optimo}')
        self.current_tc_val = self.TC_MAP[indice_optimo]
        
        # Tiempo de espera crítico para estabilización (5 * TC)
        # Esto bloquea la ejecución para asegurar datos reales
        self.tiempo_espera = 3 * self.current_tc_val
        print(f"[SR830] Freq: {freq:.2f}Hz -> TC auto-set: {self.current_tc_val}s (Idx: {indice_optimo})")
        print(f"[SR830] Esperando {self.tiempo_espera:.3f}s para estabilización...")
        if self.tiempo_espera >= 0.03:
            time.sleep(self.tiempo_espera * 2)
        else: 
            time.sleep(0.03)

    def get_measurements(self):
        """Obtiene X, Y, R y Phase usando el comando SNAP (sincronizado)."""
        snap = self.inst.query('SNAP? 1,2,3,4').strip()
        x, y, r, phi = map(float, snap.split(','))
        return {'X': x, 'Y': y, 'R': r, 'phi': phi}

    def close(self):
        self.inst.close()
        self.rm.close()

if __name__ == "__main__":
    # Script de prueba
    try:
        lockin = SR830()
        # Prueba a 10 Hz (Debería poner TC = 1s y esperar 5s)
        lockin.set_frequency(10.0)
        print(f"Medición: {lockin.get_measurements()}")
        
        # Prueba a 500 Hz (Debería poner TC = 30ms o 100ms y esperar mucho menos)
        lockin.set_frequency(500.0)
        print(f"Medición: {lockin.get_measurements()}")
        
        lockin.close()
    except Exception as e:
        print(f"Error: {e}")