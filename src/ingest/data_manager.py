# src/ingest/data_manager.py
"""
Gestor de datos experimentales — buffer en memoria y exportación a Parquet.

Responsabilidades:
  - Mantener un buffer en RAM (DuckDB in-memory) durante la adquisición
  - Normalización en tiempo real de fase (respecto a calibración de acero)
  - Normalización global de amplitud al finalizar experimento
  - Exportación a archivos Parquet en data/raw/
  - Gestión de historial (listar, cargar, eliminar, alias)

Estructura del buffer (buffer_activo):
  experiment_id, timestamp, x_pos, y_pos,
  ch_x, ch_y, magnitude_r, magnitude_normalized,
  phase_phi, phase_normalized, laser_freq

Flujo típico:
  1. iniciar_nuevo_experimento(tipo) → genera ID y limpia buffer
  2. guardar_punto(x, y, lockin_data, freq) → inserta fila, retorna normalizados
  3. finalizar_experimento() → normalización global de magnitud, exporta Parquet
"""

import json
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np


class DataManager:
    """Gestiona el ciclo de vida de los datos de experimento."""

    def __init__(self, folder="data/raw"):
        """
        Inicializa el gestor de datos.

        Args:
            folder: Directorio donde se guardan los archivos Parquet
        """
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

        # Conexión DuckDB in-memory (se pierde al cerrar)
        self.conn = duckdb.connect(database=":memory:")
        self.current_experiment_id = None

        # Estado de calibración para normalización en tiempo real
        self.cal_freqs = None    # Frecuencias de referencia (numpy array)
        self.cal_mags = None     # Amplitudes de referencia (no utilizado actualmente)
        self.cal_phases = None   # Fases de referencia (numpy array)
        self.max_mag_actual = 0.0

        self._inicializar_buffer()

    def _inicializar_buffer(self):
        """Crea la tabla temporal en RAM con el esquema de medición."""
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

    # ══════════════════════════════════════════════════════════════════════════
    #  CALIBRACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def cargar_referencia_calibracion(self, path_calibracion):
        """
        Carga la referencia de calibración (acero) en memoria.

        La calibración permite restar la fase del material de referencia
        de cada medición, obteniendo la fase verdadera de la muestra.

        Args:
            path_calibracion: Ruta al Parquet de calibración

        Returns:
            True si se cargó correctamente, False si hubo error
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
        Prepara el buffer para un nuevo experimento.

        Args:
            tipo: Tipo de experimento ("XY" o "FREQ")

        Returns:
            ID del experimento generado (ej: XY_20260708_1430)
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M")
        self.current_experiment_id = f"{tipo.upper()}_{timestamp}"

        # Reiniciar máximo de magnitud (evitar división por cero)
        self.max_mag_actual = 1e-12

        self.conn.execute("DELETE FROM buffer_activo")
        return self.current_experiment_id

    def guardar_punto(self, x, y, lockin_data, freq):
        """
        Inserta un punto medido en el buffer y retorna valores normalizados.

        Args:
            x: Posición X (mm)
            y: Posición Y (mm)
            lockin_data: Dict con claves 'X', 'Y', 'R', 'phi'
            freq: Frecuencia de modulación (Hz)

        Returns:
            tuple: (r_raw, phi_normalizada) o (None, None) si no hay experimento activo
        """
        if not self.current_experiment_id:
            return None, None

        # Extraer valores crudos del lock-in
        r_raw = float(lockin_data.get("R", 0.0))
        phi_raw = float(lockin_data.get("phi", 0.0))
        freq_val = float(freq)

        # Normalización de fase en tiempo real (resta de calibración)
        phi_norm = 0.0
        if self.cal_freqs is not None:
            phi_ref = np.interp(freq_val, self.cal_freqs, self.cal_phases)
            phi_norm = phi_raw - phi_ref
        else:
            phi_norm = phi_raw

        # La magnitud normalizada se calcula al finalizar (global)
        mag_norm = 0.0

        # Insertar en el buffer DuckDB
        query = "INSERT INTO buffer_activo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (
            self.current_experiment_id,
            datetime.now(),
            float(x),
            float(y),
            float(lockin_data.get("X", 0.0)),
            float(lockin_data.get("Y", 0.0)),
            r_raw,
            mag_norm,
            phi_raw,
            phi_norm,
            freq_val,
        )
        self.conn.execute(query, params)

        return r_raw, phi_norm

    # ══════════════════════════════════════════════════════════════════════════
    #  FINALIZACIÓN Y EXPORTACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def finalizar_experimento(self):
        """
        Normaliza magnitud globalmente y exporta el buffer a Parquet.

        La normalización de magnitud es global (R / MAX(R)) para que
        todos los puntos estén en la misma escala relativa.
        """
        if not self.current_experiment_id:
            return

        try:
            # Normalización global de magnitud
            self.conn.execute("""
                UPDATE buffer_activo
                SET magnitude_normalized = magnitude_r / (
                    SELECT MAX(magnitude_r) FROM buffer_activo
                )
            """)

            # Exportar a disco como Parquet
            path = self.folder / f"{self.current_experiment_id}.parquet"
            self.conn.execute(f"COPY buffer_activo TO '{str(path)}' (FORMAT PARQUET)")
            self.conn.execute("DELETE FROM buffer_activo")
            self.max_mag_actual = 0.0

            print(f"Experimento guardado con normalización global: {path}")

        except Exception as e:
            print(f"Error al finalizar experimento: {e}")

    # ══════════════════════════════════════════════════════════════════════════
    #  HISTORIAL
    # ══════════════════════════════════════════════════════════════════════════

    def listar_mediciones(self):
        """
        Lista todas las mediciones disponibles en la carpeta.

        Returns:
            list: Tuplas (experiment_id, fecha, n_puntos) ordenadas por fecha descendente
        """
        path_glob = self.folder / "*.parquet"

        if not any(self.folder.glob("*.parquet")):
            return []

        try:
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
        """
        Carga datos 3D desde un archivo Parquet para visualización.

        Reconstruye las grillas Z de magnitud y fase a partir de
        los puntos (x, y) almacenados.

        Args:
            experiment_id: Identificador del experimento

        Returns:
            dict con claves 'x_max', 'y_max', 'res', 'z_mag', 'z_fase' o None
        """
        path = self.folder / f"{experiment_id}.parquet"
        if not path.exists():
            return None

        # Estandarizamos los nombres usando ALIAS (AS mag, AS fase)
        intentos_query = [
            f"SELECT x_pos, y_pos, magnitude_normalized AS mag, phase_normalized AS fase, laser_freq FROM '{str(path)}'",
            f"SELECT x_pos, y_pos, magnitude_r AS mag, phase_phi AS fase, laser_freq FROM '{str(path)}'",
        ]

        data = None
        for query in intentos_query:
            try:
                # .fetchnumpy() devuelve un dict de {columna: ndarray}
                data = self.conn.execute(query).fetchnumpy()
                break
            except Exception:
                continue

        if not data:
            print(f"No se pudieron extraer datos de {experiment_id}")
            return None

        # Extraemos los arrays directamente
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

        # Creamos las grillas vacías
        z_mag = np.zeros((ny, nx))
        z_fase = np.zeros((ny, nx))

        # Reemplazamos el bucle FOR por indexación vectorizada
        ix = np.clip(np.round(x_vals / res).astype(int), 0, nx - 1)
        iy = np.clip(np.round(y_vals / res).astype(int), 0, ny - 1)

        # NumPy asigna todos los puntos en un solo paso en código C nativo
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
        """
        Carga datos 2D (curvas de frecuencia) desde un Parquet.

        Args:
            experiment_id: Identificador del experimento

        Returns:
            dict: {punto_idx: {freq: [], mag_n: [], phi_n: []}} o None
        """
        path = self.folder / f"{experiment_id}.parquet"
        if not path.exists():
            return None

        try:
            # ORDER BY para que los bloques de x_pos queden contiguos
            query = f"""
                SELECT x_pos, laser_freq, magnitude_normalized AS mag_n, phase_normalized AS phi_n, ch_y AS quad 
                FROM '{str(path)}' 
                ORDER BY x_pos ASC, laser_freq ASC
            """
            data = self.conn.execute(query).fetchnumpy()
            
            x_vals = data["x_pos"]
            
            # Encontramos dónde cambia x_pos y los índices de corte
            unique_xs, indices = np.unique(x_vals, return_index=True)
            
            # np.split corta el array en sub-arrays basados en los índices de cambio (saltamos el cero)
            split_freq = np.split(data["laser_freq"], indices[1:])
            split_mag = np.split(data["mag_n"], indices[1:])
            split_phi = np.split(data["phi_n"], indices[1:])
            split_quad = np.split(data["quad"], indices[1:])
            
            # Construimos el diccionario final. 
            # El bucle ahora corre solo 'U' veces (número de posiciones X).
            curves = {}
            for x, f, m, p, q in zip(unique_xs, split_freq, split_mag, split_phi, split_quad):
                curves[float(x)] = {
                    "freq": f,
                    "mag_n": m,
                    "phi_n": p,
                    "quad": q
                }
                
            return curves

        except Exception as e:
            print(f"Error cargando medición 2D: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    #  ELIMINACIÓN Y ALIASES
    # ══════════════════════════════════════════════════════════════════════════

    def eliminar_medicion(self, experiment_id):
        """
        Elimina el archivo Parquet de una medición.

        Args:
            experiment_id: Identificador del experimento a eliminar

        Returns:
            True si se eliminó correctamente, False si hubo error
        """
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
        """
        Obtiene el alias legible de una medición.

        Args:
            experiment_id: Identificador del experimento

        Returns:
            str con el alias o None si no existe
        """
        path = self.folder / "aliases.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8")).get(experiment_id)
        except Exception:
            return None

    def guardar_alias(self, experiment_id, alias):
        """
        Guarda o elimina el alias de una medición.

        Args:
            experiment_id: Identificador del experimento
            alias: Texto del alias (cadena vacía para eliminar)
        """
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
        """Cierra la conexión DuckDB."""
        self.conn.close()
