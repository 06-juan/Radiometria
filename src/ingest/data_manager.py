# src/ingest/data_manager.py
"""
Gestor de datos experimentales — buffer persistente por lotes y exportación a Parquet.

Responsabilidades:
  - Mantener un buffer temporal en disco (.buffer_temp.db) resistente a fallos de energía/app.
  - Escritura por lotes (batching) en disco para evitar saturación de I/O y memoria RAM.
  - Normalización en tiempo real de fase (respecto a calibración de acero).
  - Normalización global al vuelo de amplitud durante la exportación final.
  - Exportación a archivos Parquet en data/raw/.
  - Gestión de historial (listar, cargar, eliminar, alias).

Estructura del buffer (buffer_activo):
  experiment_id, timestamp, x_pos, y_pos,
  ch_x, ch_y, magnitude_r, magnitude_normalized,
  phase_phi, phase_normalized, laser_freq

Flujo típico:
  1. iniciar_nuevo_experimento(tipo) → genera ID y limpia buffer
  2. guardar_punto(x, y, lockin_data, freq) → acumula en RAM y vuelca a disco cada N puntos
  3. finalizar_experimento() → vuelca residuo, normaliza al vuelo y exporta a Parquet
"""

import json
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np


class DataManager:
    """Gestiona el ciclo de vida y la persistencia de los datos experimentales."""

    def __init__(self, folder="data/raw", batch_size=500):
        """
        Inicializa el gestor de datos.

        Args:
            folder: Directorio donde se guardan los archivos Parquet.
            batch_size: Cantidad de puntos a acumular en memoria antes de volcar a disco.
        """
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size

        # Buffer en memoria RAM para acumulación rápida punto por punto
        self.ram_buffer = []

        # Base de datos física temporal en disco para evitar pérdida de datos ante crashes
        self.db_path = self.folder / ".buffer_temp.db"
        self.conn = duckdb.connect(database=str(self.db_path))

        self.current_experiment_id = None

        # Estado de calibración para normalización en tiempo real de fase
        self.cal_freqs = None    # Frecuencias de referencia (numpy array)
        self.cal_mags = None     # Amplitudes de referencia (reservado)
        self.cal_phases = None   # Fases de referencia (numpy array)
        self.max_mag_actual = 0.0

        self._inicializar_buffer()

    def _inicializar_buffer(self):
        """Crea la tabla física temporal con el esquema de medición si no existe."""
        query = """
        CREATE TABLE IF NOT EXISTS buffer_activo (
            experiment_id VARCHAR,
            timestamp TIMESTAMP,
            x_pos DOUBLE,
            y_pos DOUBLE,
            ch_x DOUBLE,
            ch_y DOUBLE,
            magnitude_r DOUBLE,
            magnitude_normalized DOUBLE,
            phase_phi DOUBLE,
            phase_normalized DOUBLE,
            laser_freq DOUBLE
        );
        """
        self.conn.execute(query)

    def _flush_buffer(self):
        """Vuelca los puntos acumulados en la RAM hacia el archivo de base de datos en disco."""
        if not self.ram_buffer:
            return

        try:
            query = "INSERT INTO buffer_activo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            self.conn.executemany(query, self.ram_buffer)
            self.ram_buffer.clear()
        except Exception as e:
            print(f"Error volcando lote a disco: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  CALIBRACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def cargar_referencia_calibracion(self, path_calibracion):
        """
        Carga la referencia de calibración (acero) en memoria.

        Args:
            path_calibracion: Ruta al Parquet de calibración.

        Returns:
            True si se cargó correctamente, False si hubo error.
        """
        path_cal = Path(path_calibracion)

        if not path_cal.exists():
            print(f"Archivo de calibración no encontrado: {path_calibracion}")
            return False

        try:
            cal_data = duckdb.execute(f"""
                SELECT laser_freq, phase_phi
                FROM read_parquet('{str(path_cal)}')
                ORDER BY laser_freq ASC
            """).fetchnumpy()

            self.cal_freqs = cal_data["laser_freq"]
            self.cal_phases = cal_data["phase_phi"]
            print("Calibración cargada en memoria para tiempo real.")
            return True
        except Exception as e:
            print(f"Error cargando calibración: {e}")
            return False

    # ══════════════════════════════════════════════════════════════════════════
    #  ADQUISICIÓN DE DATOS
    # ══════════════════════════════════════════════════════════════════════════

    def iniciar_nuevo_experimento(self, tipo="XY"):
        """
        Prepara el buffer temporal (RAM y disco) para un nuevo experimento.

        Args:
            tipo: Tipo de experimento ("XY" o "FREQ").

        Returns:
            ID del experimento generado (ej: XY_20260708_1430).
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M")
        self.current_experiment_id = f"{tipo.upper()}_{timestamp}"

        self.max_mag_actual = 1e-12
        self.ram_buffer.clear()

        # Limpiar registros previos en el archivo DB
        self.conn.execute("DELETE FROM buffer_activo")
        return self.current_experiment_id

    def guardar_punto(self, x, y, lockin_data, freq):
        """
        Inserta un punto en el buffer RAM y realiza un flush a disco cuando alcanza el tamaño de lote.

        Args:
            x: Posición X (mm)
            y: Posición Y (mm)
            lockin_data: Dict con claves 'X', 'Y', 'R', 'phi'
            freq: Frecuencia de modulación (Hz)

        Returns:
            tuple: (r_raw, phi_normalizada) o (None, None) si no hay experimento activo.
        """
        if not self.current_experiment_id:
            return None, None

        r_raw = float(lockin_data.get("R", 0.0))
        phi_raw = float(lockin_data.get("phi", 0.0))
        freq_val = float(freq)

        # Normalización de fase en tiempo real (resta de calibración)
        if self.cal_freqs is not None:
            phi_ref = np.interp(freq_val, self.cal_freqs, self.cal_phases)
            phi_norm = phi_raw - phi_ref
        else:
            phi_norm = phi_raw

        # Guardar en el lote actual en RAM (magnitude_normalized se calculará al exportar)
        row = (
            self.current_experiment_id,
            datetime.now(),
            float(x),
            float(y),
            float(lockin_data.get("X", 0.0)),
            float(lockin_data.get("Y", 0.0)),
            r_raw,
            0.0,
            phi_raw,
            phi_norm,
            freq_val,
        )
        self.ram_buffer.append(row)

        # Si el lote alcanza el tamaño límite, se escribe de forma segura en disco
        if len(self.ram_buffer) >= self.batch_size:
            self._flush_buffer()

        return r_raw, phi_norm

    # ══════════════════════════════════════════════════════════════════════════
    #  FINALIZACIÓN Y EXPORTACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def finalizar_experimento(self):
        """
        Guarda los últimos puntos pendientes, calcula la normalización global al vuelo
        y exporta directamente el resultado a un archivo Parquet final.
        """
        if not self.current_experiment_id:
            return

        try:
            # 1. Volcar cualquier punto restante que haya quedado en la RAM
            self._flush_buffer()

            path = self.folder / f"{self.current_experiment_id}.parquet"

            # 2. Exportación a Parquet calculando magnitude_normalized al vuelo en la consulta SQL.
            #    Esto evita hacer un 'UPDATE' masivo sobre la tabla en disco/RAM.
            copy_query = f"""
            COPY (
                SELECT 
                    experiment_id,
                    timestamp,
                    x_pos,
                    y_pos,
                    ch_x,
                    ch_y,
                    magnitude_r,
                    magnitude_r / NULLIF((SELECT MAX(magnitude_r) FROM buffer_activo), 0) AS magnitude_normalized,
                    phase_phi,
                    phase_normalized,
                    laser_freq
                FROM buffer_activo
            ) TO '{str(path)}' (FORMAT PARQUET);
            """
            self.conn.execute(copy_query)

            # 3. Limpiar buffer de trabajo en el archivo DB
            self.conn.execute("DELETE FROM buffer_activo")
            self.max_mag_actual = 0.0

            print(f"Experimento exportado con éxito a: {path}")

        except Exception as e:
            print(f"Error al finalizar y exportar experimento: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  HISTORIAL Y LECTURA
    # ══════════════════════════════════════════════════════════════════════════

    def listar_mediciones(self):
        """Lista todas las mediciones Parquet en la carpeta del proyecto."""
        if not any(self.folder.glob("*.parquet")):
            return []

        try:
            path_glob = self.folder / "*.parquet"
            query = f"""
                SELECT experiment_id, MIN(timestamp) as fecha, COUNT(*) as n_puntos
                FROM '{str(path_glob)}'
                GROUP BY experiment_id
                ORDER BY fecha DESC
            """
            return self.conn.execute(query).fetchall()
        except Exception as e:
            print(f"Error listando mediciones: {e}")
            return []

    def cargar_medicion_3d(self, experiment_id):
        """Carga datos 3D desde Parquet y reconstruye las matrices z_mag y z_fase."""
        path = self.folder / f"{experiment_id}.parquet"
        if not path.exists():
            return None

        intentos_query = [
            f"SELECT x_pos, y_pos, magnitude_normalized AS mag, phase_normalized AS fase, laser_freq FROM '{str(path)}'",
            f"SELECT x_pos, y_pos, magnitude_r AS mag, phase_phi AS fase, laser_freq FROM '{str(path)}'",
        ]

        data = None
        for query in intentos_query:
            try:
                data = self.conn.execute(query).fetchnumpy()
                break
            except Exception:
                continue

        if not data:
            print(f"No se pudieron extraer datos de {experiment_id}")
            return None

        x_vals = data["x_pos"]
        y_vals = data["y_pos"]
        r_vals = data["mag"]
        phi_vals = data["fase"]

        x_unique = np.unique(x_vals)
        y_unique = np.unique(y_vals)

        dx = float(np.diff(x_unique).min()) if len(x_unique) > 1 else 0.001
        dy = float(np.diff(y_unique).min()) if len(y_unique) > 1 else 0.001
        res = min(dx, dy)

        x_max, y_max = float(x_vals.max()), float(y_vals.max())
        nx, ny = int(x_max / res) + 1, int(y_max / res) + 1

        z_mag = np.zeros((ny, nx))
        z_fase = np.zeros((ny, nx))

        ix = np.clip(np.round(x_vals / res).astype(int), 0, nx - 1)
        iy = np.clip(np.round(y_vals / res).astype(int), 0, ny - 1)

        z_mag[iy, ix] = r_vals
        z_fase[iy, ix] = phi_vals

        return {
            "x_max": x_max,
            "y_max": y_max,
            "res": res,
            "xs": np.linspace(0, x_max, nx),
            "ys": np.linspace(0, y_max, ny),
            "z_mag": z_mag,
            "z_fase": z_fase,
        }

    def cargar_medicion_2d(self, experiment_id):
        """Carga datos 2D (curvas de frecuencia) desde Parquet."""
        path = self.folder / f"{experiment_id}.parquet"
        if not path.exists():
            return None

        try:
            query = f"""
                SELECT x_pos, laser_freq, magnitude_normalized AS mag_n, phase_normalized AS phi_n, ch_y AS quad 
                FROM '{str(path)}' 
                ORDER BY x_pos ASC, laser_freq ASC
            """
            data = self.conn.execute(query).fetchnumpy()

            x_vals = data["x_pos"]
            unique_xs, indices = np.unique(x_vals, return_index=True)

            split_freq = np.split(data["laser_freq"], indices[1:])
            split_mag = np.split(data["mag_n"], indices[1:])
            split_phi = np.split(data["phi_n"], indices[1:])
            split_quad = np.split(data["quad"], indices[1:])

            curves = {}
            for x, f, m, p, q in zip(unique_xs, split_freq, split_mag, split_phi, split_quad):
                curves[float(x)] = {
                    "freq": f,
                    "mag_n": m,
                    "phi_n": p,
                    "quad": q,
                }

            return curves

        except Exception as e:
            print(f"Error cargando medición 2D: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    #  ELIMINACIÓN Y ALIASES
    # ══════════════════════════════════════════════════════════════════════════

    def eliminar_medicion(self, experiment_id):
        """Elimina el archivo Parquet de una medición."""
        path = self.folder / f"{experiment_id}.parquet"
        try:
            if path.exists():
                path.unlink()
                self.guardar_alias(experiment_id, "")
                return True
        except Exception as e:
            print(f"Error eliminando medición: {e}")
        return False

    def obtener_alias(self, experiment_id):
        """Obtiene el alias asignado a una medición."""
        path = self.folder / "aliases.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8")).get(experiment_id)
        except Exception:
            return None

    def guardar_alias(self, experiment_id, alias):
        """Guarda o borra un alias legible."""
        path = self.folder / "aliases.json"
        aliases = {}

        if path.exists():
            try:
                aliases = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                aliases = {}

        if alias.strip():
            aliases[experiment_id] = alias.strip()
        else:
            aliases.pop(experiment_id, None)

        path.write_text(json.dumps(aliases, indent=2), encoding="utf-8")

    def cerrar(self):
        """Vuelca pendientes y cierra la conexión con DuckDB."""
        self._flush_buffer()
        self.conn.close()