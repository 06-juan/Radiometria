# src/ingest/lockin.py
"""
Driver SCPI para el amplificador de bloqueo Stanford Research Systems SR830.

Comunicación vía GPIB usando PyVISA. Gestiona:
  - Configuración de frecuencia y auto-ajuste de TC/slope
  - Lectura de mediciones (X, Y, R, θ) via SNAP?
  - Control de láser via AUX OUT 3 + puerta AND externa
  - Auto-gain y modo Low Reserve

Protocolo SCPI utilizado:
  FREQ {f}       → Establece frecuencia de referencia
  SNAP? 1,2,3,4  → Consulta X, Y, R, Theta en una sola transacción
  AUXV 3, {v}    → Voltaje en salida auxiliar 3 (control de láser)
  AGAN           → Auto-ganancia automática
  RMOD 2         → Modo Low Reserve (preserva señales débiles)
  OFSL {idx}     → Pendiente del filtro de salida (6/12/18/24 dB/oct)
  OFLT {idx}     → Constante de tiempo del filtro (10µs a 300s)
"""

import sys
import time
from pathlib import Path

import numpy as np
import pyvisa

raiz_proyecto = Path(__file__).resolve().parent.parent.parent
if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))

from src.constants.constants import LockIn


class SR830:
    """
    Driver del SR830 lock-in amplifier.

    Gestiona la comunicación GPIB, la configuración de filtros
    y la lectura de mediciones. Los tiempos de espera se ajustan
    dinámicamente según la frecuencia para optimizar la relación
    señal/ruido.
    """

    def __init__(
        self,
        resource_name=LockIn.RESOURCE_NAME,
        timeout=LockIn.TIMEOUT,
        tc_constante=False,
    ):
        """
        Abre la conexión GPIB al SR830.

        Args:
            resource_name: Dirección VISA del instrumento
            timeout: Timeout de lectura en milisegundos
            tc_constante: Si True, usa TC fijo; si False, auto-ajusta por frecuencia
        """
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout

        self.tc_constante = tc_constante
        self.TC_MAP = LockIn.TC_MAP

        # Estado interno de configuración de filtros
        self.current_tc_val = 0.3          # Constante de tiempo actual (segundos)
        self.tiempo_espera = 1.0           # Tiempo de espera post-configuración
        self.current_slope_factor = 5      # Factor de asentamiento según pendiente

    def set_frequency(self, freq, es_primero=False):
        """
        Establece la frecuencia de referencia del lock-in.

        Args:
            freq: Frecuencia en Hz
            es_primero: Si True, aplica Factor extra de asentamiento (10x)
        """
        if freq <= 0:
            return

        self.inst.write(f"FREQ {freq}")

        if self.tc_constante:
            # Configuración fija: TC 100ms, pendiente 24 dB/oct
            indice_tc = 8 if freq < 300 else 7
            self._set_config_fija(indice_tc, slope_index=3)
        else:
            self._ajustar_dinamico(freq)

        # Tiempo de asentamiento: factor × TC
        wait_time = (10 if es_primero else self.current_slope_factor) * self.current_tc_val
        time.sleep(wait_time)

        # Primera medición: flush del filtro digital
        if es_primero:
            self.get_measurements()
            time.sleep(0.5)

    def _ajustar_dinamico(self, freq):
        """
        Auto-selecciona TC y pendiente según la frecuencia.

        Criterios:
          - f < 100 Hz: pendiente 24 dB/oct, factor 10
          - f >= 100 Hz: pendiente 6 dB/oct, factor 7
          - TC mínimo: max(10/freq, 30ms)
        """
        if freq < 100:
            slope_index = 3  # 24 dB/oct
            self.current_slope_factor = 10
        else:
            slope_index = 1  # 6 dB/oct
            self.current_slope_factor = 7

        self.inst.write(f"OFSL {slope_index}")

        # Buscar el TC más pequeño que cumple el criterio de asentamiento
        periodo_objetivo = 10.0 / freq
        indice_optimo = 15  # Fallback: TC más largo (300s)

        for i in sorted(self.TC_MAP.keys()):
            if self.TC_MAP[i] >= periodo_objetivo and self.TC_MAP[i] >= 30e-3:
                indice_optimo = i
                break

        self.inst.write(f"OFLT {indice_optimo}")
        self.current_tc_val = self.TC_MAP[indice_optimo]

    def _set_config_fija(self, tc_index, slope_index=3):
        """
        Aplica TC y pendiente fijos (sin auto-ajuste).

        Args:
            tc_index: Índice del registro TC (0-15)
            slope_index: Índice de pendiente (0=6, 1=12, 2=18, 3=24 dB/oct)
        """
        self.inst.write(f"OFLT {tc_index}")
        self.inst.write(f"OFSL {slope_index}")
        self.current_tc_val = self.TC_MAP[tc_index]
        self.current_slope_factor = [5, 7, 9, 10][slope_index]

    def get_measurements(self):
        """
        Lee X, Y, R y Theta del lock-in via SNAP?

        Returns:
            dict con claves 'X', 'Y', 'R', 'phi' o None si hay error
        """
        try:
            snap = self.inst.query("SNAP? 1,2,3,4").strip()
            x, y, r, phi = map(float, snap.split(","))
            return {"X": x, "Y": y, "R": r, "phi": phi}
        except Exception as e:
            print(f"Error en lectura SNAP: {e}")
            return None

    def set_amplitude(self, voltage):
        """
        Controla el láser via AUX OUT 3 + puerta AND externa.

        Args:
            voltage: 5.0V = láser ON, 0.6V = láser OFF
        """
        self.inst.write(f"AUXV 3, {voltage}")

    def auto_gain(self):
        """
        Ejecuta auto-ganancia (AGAN) y espera a que termine.

        Nota: La constante de tiempo post-AGAN es de 7 segundos
        según las especificaciones del instrumento.
        """
        self.inst.write("AGAN")
        time.sleep(LockIn.DELAY_AUTO_GAIN)

    def Reserve(self):
        """
        Activa modo Low Reserve para preservar señales débiles.

        Modo RMOD 2: optimizado para señales con relación S/N baja,
        típico en mediciones radiométricas donde la amplitud es
        del orden de microvoltios.
        """
        self.inst.write("RMOD 2")
        time.sleep(LockIn.DELAY_RESERVE)

    def close(self):
        """Cierra la conexión VISA al instrumento."""
        self.inst.close()
        self.rm.close()


if __name__ == "__main__":
    pass
