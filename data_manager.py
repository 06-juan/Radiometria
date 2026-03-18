import duckdb
import json
from datetime import datetime
import os

import duckdb
import os
from datetime import datetime

class DataManager:
    def __init__(self, folder="data", db_name="ptr_lab.db", min_points=50):
        self.folder = folder
        self.db_path = os.path.join(self.folder, db_name)
        self.min_points = min_points
        
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)
            
        self.conn = duckdb.connect(self.db_path)
        self.current_exp_id = None
        self.current_exp_type = None # 'FREQ' o 'XY'
        self.buffer = []
        self._inicializar_esquema()

    def _inicializar_esquema(self):
        """Crea el esquema relacional: 1 tabla de metadatos, 2 de mediciones."""
        # 1. Tabla Maestra (Metadatos)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experimentos (
                exp_id VARCHAR PRIMARY KEY,
                tipo VARCHAR, -- 'FREQ' o 'XY'
                fecha TIMESTAMP,
                descripcion VARCHAR
            );
        """)
        
        # 2. Tabla para Barridos de Frecuencia
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mediciones_freq (
                exp_id VARCHAR,
                freq DOUBLE,
                mag_r DOUBLE,
                phase_phi DOUBLE,
                ch_y DOUBLE,
                FOREIGN KEY (exp_id) REFERENCES experimentos(exp_id)
            );
        """)

        # 3. Tabla para Barridos XY (Frecuencia Fija)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mediciones_xy (
                exp_id VARCHAR,
                x_pos DOUBLE,
                y_pos DOUBLE,
                mag_r DOUBLE,
                phase_phi DOUBLE,
                laser_freq_fija DOUBLE,
                FOREIGN KEY (exp_id) REFERENCES experimentos(exp_id)
            );
        """)

    def iniciar_experimento(self, tipo, desc=""):
        """
        tipo: 'FREQ' o 'XY'
        """
        if tipo not in ['FREQ', 'XY']:
            raise ValueError("El tipo debe ser 'FREQ' o 'XY'")
            
        self.current_exp_id = f"EXP_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_exp_type = tipo
        self.buffer = []
        
        # Registramos en la tabla maestra
        self.conn.execute("INSERT INTO experimentos VALUES (?, ?, ?, ?)", 
                         (self.current_exp_id, tipo, datetime.now(), desc))
        return self.current_exp_id

    def guardar_punto(self, **datos):
        """
        Usa kwargs para ser flexible según el tipo de experimento.
        Ej para FREQ: guardar_punto(freq=10.5, mag=0.02, phi=45.0, y=0.01)
        Ej para XY: guardar_punto(x=1.2, y=2.2, mag=0.02, phi=45.0, f_fija=100.0)
        """
        if not self.current_exp_id: return

        # Construcción de la tupla según el tipo
        if self.current_exp_type == 'FREQ':
            punto = (self.current_exp_id, datos['freq'], datos['mag'], datos['phi'], datos.get('y', 0.0))
        else: # XY
            punto = (self.current_exp_id, datos['x'], datos['y'], datos['mag'], datos['phi'], datos['f_fija'])

        self.buffer.append(punto)

        # Volcado por lotes (Batching) para eficiencia
        if len(self.buffer) >= self.min_points:
            self._volcar_datos()

    def _volcar_datos(self):
        if not self.buffer: return
        
        tabla = "mediciones_freq" if self.current_exp_type == 'FREQ' else "mediciones_xy"
        num_cols = 5 if self.current_exp_type == 'FREQ' else 6
        placeholders = ", ".join(["?"] * num_cols)
        
        self.conn.executemany(f"INSERT INTO {tabla} VALUES ({placeholders})", self.buffer)
        self.buffer = []

    def limpiar_ruido_historico(self):
        """
        Elimina experimentos (y sus mediciones) que no llegaron al mínimo de puntos.
        Aplica el borrado en cascada lógico.
        """
        for tabla in ['mediciones_freq', 'mediciones_xy']:
            # Borramos las mediciones huérfanas
            self.conn.execute(f"""
                DELETE FROM {tabla} WHERE exp_id IN (
                    SELECT exp_id FROM {tabla} GROUP BY exp_id HAVING COUNT(*) < {self.min_points}
                )
            """)
        
        # Limpiamos la tabla maestra: borramos IDs que ya no tienen mediciones asociadas
        self.conn.execute("""
            DELETE FROM experimentos WHERE exp_id NOT IN (
                SELECT DISTINCT exp_id FROM mediciones_freq
                UNION
                SELECT DISTINCT exp_id FROM mediciones_xy
            )
        """)
        print(f"Limpieza profunda ejecutada (Umbral: {self.min_points} puntos).")

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

            print(z_mag,z_fase,res,x_max,y_max)
            
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
        
    def exportar_experimento_csv(self, experiment_id, filename=None):
        """
        Exporta un experimento específico a CSV usando el poder de DuckDB.
        Si no se da nombre, usa el experiment_id.
        """
        if not filename:
            filename = os.path.join(self.folder, f"{experiment_id}.csv")
        
        query = f"""
        COPY (
            SELECT * FROM mediciones 
            WHERE experiment_id = '{experiment_id}'
            ORDER BY timestamp ASC
        ) TO '{filename}' (HEADER, DELIMITER ',');
        """
        try:
            self.conn.execute(query)
            print(f"Datos exportados a: {filename}")
        except Exception as e:
            print(f"Error al exportar CSV: {e}")

    def cargar_medicion_2d(self, experiment_id):
        """Extrae vectores de frecuencia, magnitud, fase y cuadratura,
        agrupados por x_pos (para los casos de múltiples puntos como CRUZ)."""
        try:
            # Seleccionamos las columnas de interés ordenadas por iterador de punto (x_pos) y frecuencia
            query = """
                SELECT x_pos, laser_freq, magnitude_r, phase_phi, ch_y 
                FROM mediciones 
                WHERE experiment_id = ? 
                ORDER BY x_pos ASC, laser_freq ASC
            """
            rows = self.conn.execute(query, [experiment_id]).fetchall()
            
            if not rows: return None

            import numpy as np
            
            # Agrupar por el iterador (x_pos)
            curves = {}
            for row in rows:
                idx = float(row[0])
                if idx not in curves:
                    curves[idx] = {"freq": [], "mag": [], "phi": [], "quad": []}
                curves[idx]["freq"].append(row[1])
                curves[idx]["mag"].append(row[2])
                curves[idx]["phi"].append(row[3])
                curves[idx]["quad"].append(row[4])

            # Convertir todas las listas de las curvas en arrays
            for k in curves.keys():
                curves[k]["freq"] = np.array(curves[k]["freq"])
                curves[k]["mag"] = np.array(curves[k]["mag"])
                curves[k]["phi"] = np.array(curves[k]["phi"])
                curves[k]["quad"] = np.array(curves[k]["quad"])

            return curves
        except Exception as e:
            print(f"Error cargando datos 2D: {e}")
            return None

    def _ruta_aliases(self):
        return os.path.join(self.folder, "aliases.json")

    def obtener_alias(self, experiment_id):
        """Devuelve el alias de una medición, o None si no existe."""
        path = self._ruta_aliases()
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                aliases = json.load(f)
            return aliases.get(experiment_id)
        except (json.JSONDecodeError, IOError):
            return None

    def guardar_alias(self, experiment_id, alias):
        """Guarda un alias (seudónimo) para una medición."""
        path = self._ruta_aliases()
        aliases = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    aliases = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        alias_limpio = (alias or "").strip()
        if alias_limpio:
            aliases[experiment_id] = alias_limpio
        else:
            aliases.pop(experiment_id, None)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(aliases, f, indent=2, ensure_ascii=False)

    def eliminar_medicion(self, experiment_id):
        """Elimina todos los datos de una medición de la base de datos."""
        try:
            self.conn.execute("DELETE FROM mediciones WHERE experiment_id = ?", [experiment_id])
            self.guardar_alias(experiment_id, "")
            return True
        except Exception as e:
            print(f"Error eliminando medición {experiment_id}: {e}")
            return False

    def cerrar(self):
        if self.conn:
            self.conn.close()
            print("Conexión a DB cerrada.")

if __name__ == "__main__":
    manager = DataManager(min_points=50)
    
    # --- FASE DE LIMPIEZA ---
    print("Mantenimiento: Eliminando experimentos con señal insuficiente...")
    manager.limpiar_ruido_historico()
    
    # --- EJEMPLO DE USO PARA INVESTIGACIÓN ---
    # 1. Simular un barrido de frecuencia (PTR Difusividad)
    manager.iniciar_experimento('FREQ', "Muestra Silicio - Caracterización Térmica")
    for f in range(1, 60): # 60 puntos (pasará el filtro)
        manager.guardar_punto(freq=f, mag=0.5/f, phi=-45.0, y=0.0)
    
    # 2. Simular un barrido XY fallido (Ruido)
    manager.iniciar_experimento('XY', "Mapa de superficie - Intento fallido")
    for i in range(10): # Solo 10 puntos (será ruido)
        manager.guardar_punto(x=i, y=0, mag=0.1, phi=10.0, f_fija=1000.0)

    # Al cerrar, el experimento de 10 puntos no se habrá guardado 
    # permanentemente porque nunca llegó al volcado de 50.
    manager.cerrar()
    print("Proceso finalizado.")