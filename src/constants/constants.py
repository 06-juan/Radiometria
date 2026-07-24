# src/constants/constants.py
"""
Constantes globales del sistema de Radiometría Fototérmica.

Organizadas en tres clases de dominio:
  - Laser:      voltajes de control del láser via AUX OUT 3
  - LockIn:     configuración GPIB, delays, mapa de time-constants
  - TableXY:    parámetros seriales del Arduino, límites físicos
  - Simulation: flags del modo simulación
"""


class Laser:
    """Voltajes de control del láser mediante AUX OUT 3 + puerta AND."""

    ON_VOLTAGE = 5.0   # Encender láser
    OFF_VOLTAGE = 0.6  # Apagar láser


class LockIn:
    """Configuración del amplificador de bloqueo SR830."""

    # Dirección GPIB del instrumento
    RESOURCE_NAME = "GPIB0::8::INSTR"

    # Timeout de lectura VISA (milisegundos)
    TIMEOUT = 10000

    # Tiempos de espera tras comandos de configuración
    DELAY_AUTO_GAIN = 7.0   # Segundos tras AGAN (auto-ganancia)
    DELAY_RESERVE = 1.0     # Segundos tras RMOD (modo reserva)

    # Mapa de registros de time-constant: índice → valor en segundos
    TC_MAP = {
        0: 10e-6,   1: 30e-6,   2: 100e-6,  3: 300e-6,
        4: 1e-3,    5: 3e-3,    6: 10e-3,   7: 30e-3,
        8: 100e-3,  9: 300e-3,  10: 1.0,    11: 3.0,
        12: 10.0,   13: 30.0,   14: 100.0,  15: 300.0,
    }


class TableXY:
    """Configuración de la mesa XY motorizada (Arduino + AccelStepper)."""

    # Puerto serial por defecto
    PORT = "COM3"
    BAUDRATE = 9600

    # Timeouts de comunicación serial
    TIMEOUT_SERIAL = 5           # Timeout de lectura serial (segundos)
    TIMEOUT_READY = 100.0        # Tiempo máximo de espera para "READY" del Arduino

    # Tiempo de estabilización pre-barrido (segundos)
    DELAY_PRE_START = 10.0

    # Límites físicos absolutos de la mesa (milímetros)
    X_MIN = 0.0
    X_MAX = 10.0
    Y_MIN = 0.0
    Y_MAX = 10.0

    # Configuración del control manual de pasos (JOG)
    DEFAULT_STEP = 1.0   # Paso por defecto (mm)
    STEP_MIN = 1          # Mínimo del slider de pasos
    STEP_MAX = 100       # Máximo del slider de pasos
    STEP_FACTOR = 100.0   # Divisor para convertir valor del slider a mm


class Simulation:
    """Configuración del modo simulación (debug sin hardware)."""

    # Se sobreescribe con --sim desde main.py
    ENABLED = False
