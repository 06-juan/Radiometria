import duckdb
from datetime import datetime
import os

class DataManager:
    def __init__(self, folder="data", db_name="laboratorio_datos.db"):
        # 1. Definimos la ruta completa
        self.folder = folder
        self.db_path = os.path.join(self.folder, db_name)
        
        # 2. Creamos la carpeta si no existe (como mkdir -p)
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            print(f"Carpeta '{self.folder}' creada exitosamente.")
            
        self.conn = None
        self.current_experiment_id = None
        self._inicializar_tabla()

    def _inicializar_tabla(self):
        """Conecta a la ruta específica dentro de /data"""
        # Conectamos a 'data/laboratorio_datos.db'
        self.conn = duckdb.connect(self.db_path)
        
        query = """
        CREATE TABLE IF NOT EXISTS mediciones (
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
        print(f"Base de datos lista en: {self.db_path}")

    def iniciar_nuevo_experimento(self):
        """Genera un ID único basado en la fecha y hora actual."""
        # Ejemplo de ID: "EXP_20231027_153022"
        now = datetime.now()
        self.current_experiment_id = f"EXP_{now.strftime('%Y%m%d_%H%M%S')}"
        return self.current_experiment_id

    def guardar_punto(self, x, y, lockin_data, freq):
        """
        Inserta una fila de datos.
        lockin_data: diccionario con keys 'X', 'Y', 'R', 'phi'
        """
        if not self.current_experiment_id:
            print("ADVERTENCIA: Intentando guardar sin iniciar experimento.")
            return

        timestamp = datetime.now()
        
        # Preparamos la query parametrizada (Evita errores y es más seguro)
        query = """
        INSERT INTO mediciones VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            self.current_experiment_id,
            timestamp,
            float(x),
            float(y),
            float(lockin_data.get('X', 0.0)),
            float(lockin_data.get('Y', 0.0)),
            float(lockin_data.get('R', 0.0)),
            float(lockin_data.get('phi', 0.0)),
            float(freq)
        )
        
        try:
            self.conn.execute(query, params)
        except Exception as e:
            print(f"Error guardando en DB: {e}")

    def listar_mediciones(self):
        """
        Devuelve lista de (experiment_id, timestamp, n_puntos) ordenada por timestamp descendente.
        Útil para poblar un menú desplegable de mediciones disponibles.
        """
        try:
            result = self.conn.execute("""
                SELECT experiment_id, MIN(timestamp) as fecha, COUNT(*) as n_puntos
                FROM mediciones
                GROUP BY experiment_id
                ORDER BY fecha DESC
            """).fetchall()
            return result
        except Exception as e:
            print(f"Error listando mediciones: {e}")
            return []

    def cargar_medicion(self, experiment_id):
        """
        Carga todos los puntos de una medición.
        Devuelve dict con: x_max, y_max, res, xs, ys, z_mag (2D), z_fase (2D)
        para visualizar en las gráficas 3D.
        """
        try:
            rows = self.conn.execute("""
                SELECT x_pos, y_pos, magnitude_r, phase_phi
                FROM mediciones
                WHERE experiment_id = ?
                ORDER BY y_pos ASC, x_pos ASC
            """, [experiment_id]).fetchall()

            if not rows:
                return None

            import numpy as np
            x_vals = np.array([r[0] for r in rows])
            y_vals = np.array([r[1] for r in rows])
            r_vals = np.array([r[2] for r in rows])
            phi_vals = np.array([r[3] for r in rows])

            x_unique = np.unique(x_vals)
            y_unique = np.unique(y_vals)

            if len(x_unique) < 2:
                dx = 0.001
            else:
                dx = float(np.diff(x_unique).min())
            if len(y_unique) < 2:
                dy = 0.001
            else:
                dy = float(np.diff(y_unique).min())
            res = min(dx, dy)
            x_max = float(x_vals.max())
            y_max = float(y_vals.max())

            nx = int(x_max / res) + 1
            ny = int(y_max / res) + 1

            z_mag = np.zeros((ny, nx))
            z_fase = np.zeros((ny, nx))
            z_mag.fill(np.nan)
            z_fase.fill(np.nan)

            for i, (x, y, r, phi) in enumerate(zip(x_vals, y_vals, r_vals, phi_vals)):
                ix = int(np.clip(round(x / res), 0, nx - 1))
                iy = int(np.clip(round(y / res), 0, ny - 1))
                z_mag[iy, ix] = r
                z_fase[iy, ix] = phi

            z_mag = np.nan_to_num(z_mag, nan=0.0)
            z_fase = np.nan_to_num(z_fase, nan=0.0)

            return {
                "x_max": x_max,
                "y_max": y_max,
                "res": res,
                "xs": np.linspace(0, x_max, nx),
                "ys": np.linspace(0, y_max, ny),
                "z_mag": z_mag,
                "z_fase": z_fase,
            }
        except Exception as e:
            print(f"Error cargando medición {experiment_id}: {e}")
            return None

    def cerrar(self):
        if self.conn:
            self.conn.close()
            print("Conexión a DB cerrada.")