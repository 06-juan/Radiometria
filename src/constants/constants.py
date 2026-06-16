# src/constants/constants.py

class Laser:
    ON_VOLTAGE = 5.0
    OFF_VOLTAGE = 0.6

class LockIn:
    RESOURCE_NAME = 'GPIB0::8::INSTR'
    TIMEOUT = 10000
    
    # Delays de configuración (Tiempos de espera arbitrarios de hardware)
    DELAY_AUTO_GAIN = 7.0
    DELAY_RESERVE = 1.0
    
    TC_MAP = {
        0: 10e-6, 1: 30e-6, 2: 100e-6, 3: 300e-6,
        4: 1e-3,  5: 3e-3,  6: 10e-3,  7: 30e-3,
        8: 100e-3, 9: 300e-3, 10: 1.0,  11: 3.0,
        12: 10.0, 13: 30.0, 14: 100.0, 15: 300.0
    }

class TableXY:
    # Configuración de puerto Serial y hardware
    PORT = 'COM3'
    BAUDRATE = 9600
    TIMEOUT_SERIAL = 5
    TIMEOUT_READY = 100.0   # Antes el número mágico 100 de _wait_for_ready
    
    # Tiempos de estabilización térmica y física
    DELAY_PRE_START = 10.0  # Corresponde a t_preinicio
    
    # Límites físicos absolutos de la mesa (en milímetros)
    X_MIN = 0.0
    X_MAX = 100.0  
    Y_MIN = 0.0
    Y_MAX = 100.0  

    # Configuración de la interfaz de control manual (JOG)
    DEFAULT_STEP = 10.0   
    STEP_MIN = 1         
    STEP_MAX = 1000       
    STEP_FACTOR = 100.0