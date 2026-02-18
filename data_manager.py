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

    def cerrar(self):
        if self.conn:
            self.conn.close()
            print("Conexión a DB cerrada.")