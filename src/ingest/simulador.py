"""
Simuladores de hardware para modo debug sin dispositivos reales.

Implementan la misma interfaz que MesaXY y SR830, pero generan
datos ficticios con ruido gaussiano para permitir probar la GUI
y la lógica de control sin conexión al Arduino ni al lock-in.
"""

import time
import numpy as np

from src.constants.constants import TableXY, Laser


class MesaXYSimulator:
    """
    Simulador de la mesa XY motorizada.

    Imita el protocolo de comunicación serial del Arduino sin abrir
    ningún puerto. Los generators simulan el barrido punto a punto
    con tiempos de espera reducidos para debug rápido.
    """

    def __init__(self, port="SIM", baudrate=9600, timeout=5):
        self.port = port
        self._abort = False
        self.origin_offset_x = 0.0
        self.origin_offset_y = 0.0
        self._sim_delay = 0.02  # 20ms entre puntos

    def home(self):
        """Simula la secuencia de homing (200ms fake delay)."""
        time.sleep(0.2)

    def set_origin(self, logical_x=0.0, logical_y=0.0):
        """Establece el origen acumulando el offset (mecánica de la mesa)."""
        self.origin_offset_x += logical_x
        self.origin_offset_y += logical_y

    def _send_command(self, cmd):
        """No-op en simulación (no hay serial)."""
        pass

    def move_to(self, x, y):
        """Simula un movimiento a la posición (x, y) con breve delay."""
        time.sleep(0.05)

    def _pre_start_lockin(self, lockin_device, freq):
        """Configura el lock-in simulado antes del barrido."""
        lockin_device.set_frequency(freq, True)
        lockin_device.set_amplitude(Laser.ON_VOLTAGE)
        lockin_device.Reserve()
        lockin_device.auto_gain()

    def sweep_and_measure_generator(self, lockin_device, x_max, y_max, res, f):
        """
        Generador de barrido XY simulado.

        Recorre una grilla de puntos (x, y) y en cada uno genera
        mediciones ficticias con ruido gaussiano. El lock-in
        simulado produce valores coherentes con la posición.
        """
        self._abort = False
        self._pre_start_lockin(lockin_device, f)

        xs = np.arange(0, x_max + res, res)
        ys = np.arange(0, y_max + res, res)

        for y in ys:
            if self._abort:
                break
            for x in xs:
                if self._abort:
                    break

                time.sleep(self._sim_delay)

                # Datos sintéticos: amplitud varía con posición
                base_amp = 5e-6 * (1 + 0.3 * np.sin(0.1 * x) * np.cos(0.1 * y))
                ruido = np.random.normal(0, 1e-7)
                z_data = lockin_device.get_measurements(
                    fake_x=x, fake_y=y, fake_r=base_amp + ruido
                )

                yield x, y, z_data

        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)

    def cruz_frequency_generator(self, lockin_device, x_max, y_max, f_start, f_end, steps):
        """
        Generador de barrido de frecuencia simulado.

        Visita 5 puntos de cruce (esquinas + centro) y en cada uno
        barre las frecuencias solicitadas.
        """
        self._abort = False

        # 5 puntos de cruce: esquinas + centro
        puntos = [
            (0.0, 0.0),
            (x_max, 0.0),
            (x_max, y_max),
            (0.0, y_max),
            (x_max / 2, y_max / 2),
        ]

        freqs = np.linspace(f_start, f_end, steps)

        for idx, (px, py) in enumerate(puntos):
            if self._abort:
                break

            self._pre_start_lockin(lockin_device, freqs[0])

            for f in freqs:
                if self._abort:
                    break

                lockin_device.set_frequency(f, False)
                time.sleep(0.01)  # Tiempo reducido para debug

                # Amplitud sintética dependiente de frecuencia
                base_amp = 3e-6 * np.exp(-f / 5000) + np.random.normal(0, 5e-8)
                z_data = lockin_device.get_measurements(fake_r=max(base_amp, 1e-10))

                yield idx, f, z_data

            lockin_device.set_amplitude(Laser.OFF_VOLTAGE)
            time.sleep(0.01)

        lockin_device.set_amplitude(Laser.OFF_VOLTAGE)

    def disable(self):
        """No-op en simulación."""
        pass

    def stop_current_operation(self):
        """Detiene la operación simulada."""
        self._abort = True

    def close(self):
        """No-op en simulación."""
        pass


class SR830Simulator:
    """
    Simulador del amplificador de bloqueo SR830.

    Produce mediciones sintéticas con valores coherentes
    para cada frecuencia y posición, útil para verificar
    el pipeline completo de datos sin hardware real.
    """

    def __init__(self, resource_name="SIM", timeout=10000, tc_constante=False):
        self.tc_constante = tc_constante
        self.TC_MAP = {
            0: 10e-6, 1: 30e-6, 2: 100e-6, 3: 300e-6,
            4: 1e-3, 5: 3e-3, 6: 10e-3, 7: 30e-3,
            8: 100e-3, 9: 300e-3, 10: 1.0, 11: 3.0,
            12: 10.0, 13: 30.0, 14: 100.0, 15: 300.0,
        }
        self.current_tc_val = 0.3
        self.tiempo_espera = 0.01  # 10ms para debug rápido
        self.current_slope_factor = 5
        self.current_freq = 1000.0

    def set_frequency(self, freq, es_primero=False):
        """Registra la frecuencia actual (sin hardware real)."""
        if freq <= 0:
            return
        self.current_freq = freq

        if self.tc_constante:
            self.current_tc_val = 0.1
            self.current_slope_factor = 5
        else:
            self._ajustar_dinamico(freq)

    def _ajustar_dinamico(self, freq):
        """Ajusta TC y slope ficticios según la frecuencia."""
        if freq < 100:
            self.current_slope_factor = 10
        else:
            self.current_slope_factor = 7
        self.current_tc_val = max(10e-3, 10.0 / freq)

    def get_measurements(self, fake_x=None, fake_y=None, fake_r=None):
        """
        Retorna mediciones sintéticas.

        Si se proporcionan fake_*, los usa como base. Si no,
        genera valores aleatorios coherentes con la frecuencia actual.
        """
        if fake_r is not None:
            r = fake_r
        else:
            # Amplitud sintética: decae con frecuencia
            r = 5e-6 * np.exp(-self.current_freq / 3000) + np.random.normal(0, 1e-7)
            r = max(r, 1e-10)

        # Fase sintética: varía linealmente con frecuencia
        phi = 45.0 + 0.01 * self.current_freq + np.random.normal(0, 0.5)

        x = r * np.cos(np.radians(phi)) + np.random.normal(0, 1e-8)
        y = r * np.sin(np.radians(phi)) + np.random.normal(0, 1e-8)

        return {"X": float(x), "Y": float(y), "R": float(r), "phi": float(phi)}

    def set_amplitude(self, voltage):
        """Registra el estado del láser (sin enviar AUXV real)."""
        self._laser_voltage = voltage

    def auto_gain(self):
        """No-op en simulación (sin espera de 7s real)."""
        pass

    def Reserve(self):
        """No-op en simulación (sin espera de 1s real)."""
        pass

    def close(self):
        """No-op en simulación."""
        pass
