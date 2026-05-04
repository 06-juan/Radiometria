import duckdb
import json
from datetime import datetime
import os
import numpy as np

class DataManager:
    def __init__(self, folder="data"):
        self.folder = folder
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            print(f"Carpeta '{self.folder}' creada.")
            
        # Conexión principal EN MEMORIA para máxima velocidad de captura
        self.conn = duckdb.connect(database=':memory:')
        self.current_experiment_id = None
        self._inicializar_buffer()

    def _inicializar_buffer(self):
        """Crea la tabla temporal en RAM."""
        query = """
        CREATE TABLE IF NOT EXISTS buffer_activo (
            experiment_id VARCHAR,
            timestamp TIMESTAMP,
            x_pos DOUBLE,
            y_pos DOUBLE,
            ch_x DOUBLE,
            ch_y DOUBLE,
            magnitude_r DOUBLE,
            phase_phi DOUBLE,
            laser_freq DOUBLE
        );
        """
        self.conn.execute(query)

    def iniciar_nuevo_experimento(self, tipo="XY"):
        """Genera ID corto: XY_20240520_1430"""
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M')
        self.current_experiment_id = f"{tipo.upper()}_{timestamp}"
        # Limpiar buffer por si acaso
        self.conn.execute("DELETE FROM buffer_activo")
        return self.current_experiment_id

    def guardar_punto(self, x, y, lockin_data, freq):
        """Inserta en RAM (Ultra rápido)."""
        if not self.current_experiment_id:
            return

        query = "INSERT INTO buffer_activo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (
            self.current_experiment_id,
            datetime.now(),
            float(x), float(y),
            float(lockin_data.get('X', 0.0)),
            float(lockin_data.get('Y', 0.0)),
            float(lockin_data.get('R', 0.0)),
            float(lockin_data.get('phi', 0.0)),
            float(freq)
        )
        self.conn.execute(query, params)

    def finalizar_experimento(self):
        """Vuelca los datos de RAM a un archivo Parquet individual."""
        if not self.current_experiment_id:
            return
            
        path = os.path.join(self.folder, f"{self.current_experiment_id}.parquet")
        try:
            self.conn.execute(f"COPY buffer_activo TO '{path}' (FORMAT PARQUET)")
            self.conn.execute("DELETE FROM buffer_activo")
            print(f"✅ Guardado en: {path}")
        except Exception as e:
            print(f"Error al persistir Parquet: {e}")

    def listar_mediciones(self):
        """Busca en todos los archivos .parquet de la carpeta."""
        path_glob = os.path.join(self.folder, "*.parquet")
        if not any(fname.endswith('.parquet') for fname in os.listdir(self.folder)):
            return []
            
        try:
            # DuckDB lee todos los archivos al vuelo
            query = f"""
                SELECT experiment_id, MIN(timestamp) as fecha, COUNT(*) as n_puntos
                FROM '{path_glob}'
                GROUP BY experiment_id
                ORDER BY fecha DESC
            """
            return self.conn.execute(query).fetchall()
        except Exception as e:
            print(f"Error listando: {e}")
            return []

    def cargar_medicion(self, experiment_id):
        """Carga datos desde el archivo Parquet específico para visualización 3D."""
        path = os.path.join(self.folder, f"{experiment_id}.parquet")
        if not os.path.exists(path): return None

        try:
            query = f"SELECT x_pos, y_pos, magnitude_r, phase_phi, laser_freq FROM '{path}' ORDER BY y_pos ASC, x_pos ASC"
            rows = self.conn.execute(query).fetchall()
            
            if not rows: return None

            x_vals = np.array([r[0] for r in rows])
            y_vals = np.array([r[1] for r in rows])
            r_vals = np.array([r[2] for r in rows])
            phi_vals = np.array([r[3] for r in rows])
            freq_vals = np.array([r[4] for r in rows])

            x_unique = np.unique(x_vals)
            y_unique = np.unique(y_vals)

            dx = float(np.diff(x_unique).min()) if len(x_unique) > 1 else 0.001
            dy = float(np.diff(y_unique).min()) if len(y_unique) > 1 else 0.001
            res = min(dx, dy)
            
            x_max, y_max = float(x_vals.max()), float(y_vals.max())
            nx, ny = int(x_max / res) + 1, int(y_max / res) + 1

            laser_freq = freq_vals[0]

            z_mag = np.zeros((ny, nx))
            z_fase = np.zeros((ny, nx))
            
            for x, y, r, phi in zip(x_vals, y_vals, r_vals, phi_vals):
                ix = int(np.clip(round(x / res), 0, nx - 1))
                iy = int(np.clip(round(y / res), 0, ny - 1))
                z_mag[iy, ix] = r
                z_fase[iy, ix] = phi

            print(f'"x_max": {x_max}, "y_max": {y_max}, "res": {res}, "freq": {laser_freq}')

            return {
                "x_max": x_max, "y_max": y_max, "res": res,
                "xs": np.linspace(0, x_max, nx), "ys": np.linspace(0, y_max, ny),
                "z_mag": z_mag, "z_fase": z_fase,
            }
        except Exception as e:
            print(f"Error cargando {experiment_id}: {e}")
            return None

    def cargar_medicion_2d(self, experiment_id):
        """Carga datos desde el Parquet para curvas 2D."""
        path = os.path.join(self.folder, f"{experiment_id}.parquet")
        if not os.path.exists(path): return None

        try:
            query = f"SELECT x_pos, laser_freq, magnitude_r, phase_phi, ch_y FROM '{path}' ORDER BY x_pos ASC, laser_freq ASC"
            rows = self.conn.execute(query).fetchall()
            
            curves = {}
            for r in rows:
                idx = float(r[0])
                if idx not in curves:
                    curves[idx] = {"freq": [], "mag": [], "phi": [], "quad": []}
                curves[idx]["freq"].append(r[1])
                curves[idx]["mag"].append(r[2])
                curves[idx]["phi"].append(r[3])
                curves[idx]["quad"].append(r[4])

            for k in curves:
                for field in curves[k]:
                    curves[k][field] = np.array(curves[k][field])
            return curves
        except Exception as e:
            print(f"Error 2D: {e}")
            return None

    def eliminar_medicion(self, experiment_id):
        """Borra el archivo Parquet físico."""
        path = os.path.join(self.folder, f"{experiment_id}.parquet")
        try:
            if os.path.exists(path):
                os.remove(path)
                self.guardar_alias(experiment_id, "")
                return True
        except Exception as e:
            print(f"Error eliminando: {e}")
        return False

    def obtener_alias(self, experiment_id):
        path = os.path.join(self.folder, "aliases.json")
        if not os.path.exists(path): return None
        with open(path, "r") as f:
            return json.load(f).get(experiment_id)

    def guardar_alias(self, experiment_id, alias):
        path = os.path.join(self.folder, "aliases.json")
        aliases = {}
        if os.path.exists(path):
            with open(path, "r") as f: aliases = json.load(f)
        if alias.strip(): aliases[experiment_id] = alias.strip()
        else: aliases.pop(experiment_id, None)
        with open(path, "w") as f: json.dump(aliases, f, indent=2)

    def cerrar(self):
        self.conn.close()