import duckdb
import json
from datetime import datetime
import os
import numpy as np

class DataManager:
    def __init__(self, folder="data/raw"):
        self.folder = folder
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            
        self.conn = duckdb.connect(database=':memory:')
        self.current_experiment_id = None
        
        # --- ATRIBUTOS PARA TIEMPO REAL DATOS CALCULADOS ---
        self.cal_freqs = None
        self.cal_mags = None
        self.cal_phases = None
        self.max_mag_actual = 0.0
        
        self._inicializar_buffer()

    def _inicializar_buffer(self):
        """Crea la tabla temporal en RAM con columnas para datos normalizados."""
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

    def cargar_referencia_calibracion(self, path_calibracion):
        """Carga la calibración en memoria para cálculos instantáneos."""
        if not os.path.exists(path_calibracion):
            print(f"⚠️ Archivo de calibración no encontrado en {path_calibracion}")
            return False
        
        try:
            # Cargamos los datos de referencia (ej. del acero)
            cal_data = duckdb.execute(f"""
                SELECT laser_freq, phase_phi 
                FROM read_parquet('{path_calibracion}') 
                ORDER BY laser_freq ASC
            """).fetchnumpy()
            
            self.cal_freqs = cal_data['laser_freq']
            self.cal_phases = cal_data['phase_phi']
            print("✅ Calibración cargada en memoria para tiempo real.")
            return True
        except Exception as e:
            print(f"❌ Error cargando calibración: {e}")
            return False

    def iniciar_nuevo_experimento(self, tipo="XY"):
        """Reinicia el ID y el contador de magnitud máxima."""
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M')
        self.current_experiment_id = f"{tipo.upper()}_{timestamp}"
        
        #Reiniciar el máximo para el nuevo experimento
        self.max_mag_actual = 1e-12 # Evitar división por cero inicial
        
        self.conn.execute("DELETE FROM buffer_activo")
        return self.current_experiment_id

    def guardar_punto(self, x, y, lockin_data, freq):
        """Calcula normalización respecto al máximo actual e inserta en RAM."""
        if not self.current_experiment_id:
            return

        # 1. Obtener valores crudos
        r_raw = float(lockin_data.get('R', 0.0))
        phi_raw = float(lockin_data.get('phi', 0.0))
        freq_val = float(freq)

        # 3. CÁLCULO DE NORMALIZACIÓN EN TIEMPO REAL
        # Magnitud: Normalizamos al final
        mag_norm = 0.0

        # Fase: respecto a la calibración (si existe)
        phi_norm = 0.0
        if self.cal_freqs is not None:
            phi_ref = np.interp(freq_val, self.cal_freqs, self.cal_phases)
            phi_norm = phi_raw - phi_ref
        else:
            phi_norm = phi_raw

        # 4. Insertar en la tabla de DuckDB
        query = "INSERT INTO buffer_activo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        params = (
            self.current_experiment_id,
            datetime.now(),
            float(x), float(y),
            float(lockin_data.get('X', 0.0)),
            float(lockin_data.get('Y', 0.0)),
            r_raw,
            mag_norm,
            phi_raw,
            phi_norm,
            freq_val
        )
        self.conn.execute(query, params)
        
        return r_raw, phi_norm

    def finalizar_experimento(self):
        """Simplemente guarda lo que ya está calculado en el buffer."""
        if not self.current_experiment_id:
            return
            
        try:
            # Usamos una subconsulta para obtener el máximo global
            print("Calculando normalización final...")
            self.conn.execute("""
                UPDATE buffer_activo 
                SET magnitude_normalized = magnitude_r / (SELECT MAX(magnitude_r) FROM buffer_activo)
            """)
            
            # Exportar a disco
            path = os.path.join(self.folder, f"{self.current_experiment_id}.parquet")
            self.conn.execute(f"COPY buffer_activo TO '{path}' (FORMAT PARQUET)")
            self.conn.execute("DELETE FROM buffer_activo")
            self.max_mag_actual = 0.0 # Reset para el próximo
            print(f"✅ Guardado con normalización global en: {path}")
            
        except Exception as e:
            print(f"❌ Error al finalizar: {e}")

    def normalizar_fase(self, path_calibracion):
        """Calcula la fase verdadera interpolada y actualiza el buffer en RAM."""
        print("Normalizando fase con archivo de calibración...")
        
        try:
            # 1. Cargar datos de calibración (desde el parquet guardado del Acero)
            cal_data = duckdb.execute(f"""
                SELECT laser_freq, phase_phi 
                FROM read_parquet('{path_calibracion}') 
                ORDER BY laser_freq ASC
            """).fetchnumpy()
            f_cal = cal_data['laser_freq']
            phi_cal = cal_data['phase_phi']

            # 2. Extraer datos actuales de la RAM (usamos rowid para saber qué fila actualizar)
            exp_data = self.conn.execute("""
                SELECT rowid, laser_freq, phase_phi 
                FROM buffer_activo
            """).fetchnumpy()
            rowids = exp_data['rowid']
            f_exp = exp_data['laser_freq']
            phi_exp = exp_data['phase_phi']

            # 3. Matemática: Interpolación y resta
            phi_cal_interpolada = np.interp(f_exp, f_cal, phi_cal)
            phase_true = phi_exp - phi_cal_interpolada

            # 4. Actualizar la tabla en RAM vía una tabla temporal rápida
            self.conn.execute("""
                CREATE TEMP TABLE temp_fase AS 
                SELECT unnest(?::BIGINT[]) AS id, unnest(?::DOUBLE[]) AS fase_norm
            """, [rowids, phase_true])

            self.conn.execute("""
                UPDATE buffer_activo 
                SET phase_normalized = temp_fase.fase_norm 
                FROM temp_fase 
                WHERE buffer_activo.rowid = temp_fase.id
            """)

            self.conn.execute("DROP TABLE temp_fase")
            print("✅ Fase normalizada inyectada correctamente en el buffer.")
            
        except Exception as e:
            print(f"Error durante la normalización de fase: {e}")

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
        if not os.path.exists(path): 
            return None

        # Intentamos primero con las columnas nuevas
        intentos_query = [
            f"SELECT x_pos, y_pos, magnitude_normalized, phase_normalized, laser_freq FROM '{path}' ORDER BY y_pos ASC, x_pos ASC",
            f"SELECT x_pos, y_pos, magnitude_r, phase_phi, laser_freq FROM '{path}' ORDER BY y_pos ASC, x_pos ASC"
        ]

        rows = None
        for query in intentos_query:
            try:
                rows = self.conn.execute(query).fetchall()
                break # Si funciona, salimos del bucle
            except Exception:
                continue # Si falla (columna no existe), probamos la siguiente

        if not rows: 
            print(f"⚠️ No se pudieron extraer datos de {experiment_id}")
            return None

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

    def cargar_medicion_2d(self, experiment_id):
        """Carga datos desde el Parquet para curvas 2D."""
        path = os.path.join(self.folder, f"{experiment_id}.parquet")
        if not os.path.exists(path): return None

        try:
            query = f"SELECT x_pos, laser_freq, magnitude_normalized, phase_normalized, ch_y FROM '{path}' ORDER BY x_pos ASC, laser_freq ASC"
            rows = self.conn.execute(query).fetchall()
            
            curves = {}
            for r in rows:
                idx = float(r[0])
                if idx not in curves:
                    curves[idx] = {"freq": [], "mag_n": [], "phi_n": [], "quad": []}
                curves[idx]["freq"].append(r[1])
                curves[idx]["mag_n"].append(r[2])
                curves[idx]["phi_n"].append(r[3])
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