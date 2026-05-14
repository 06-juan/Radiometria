"""
Crea Apartir de una medicion sobre una muestra metalica como acero inoxidable un archivo .parquet
que se restara a las fases de las demas mediciones como un desfase instrumental.
Recomendamos se debe asegurar una medicion por cada 10Hz del rango
"""

import duckdb

# Conectar a DuckDB (instancia en memoria)
con = duckdb.connect()

# Rutas de archivos
parquet_input = "./data/raw/FREQ_20260513_0843.parquet"
parquet_output = "./data/calibracion/calibracion.parquet"

# Consulta SQL:
# 1. ROUND(laser_freq, 0) agrupa las frecuencias aproximadas.
# 2. AVG(...) promedia los canales y magnitudes.
# 3. Al NO incluir x_pos ni y_pos en el SELECT o GROUP BY, se eliminan del resultado final.
query = f"""
COPY (
    SELECT 
        ROUND(laser_freq, 0) AS laser_freq,
        ROUND(AVG(phase_phi), 3) AS phase_phi
    FROM read_parquet('{parquet_input}')
    GROUP BY laser_freq
    ORDER BY laser_freq ASC
) TO '{parquet_output}' (FORMAT PARQUET);
"""

# Ejecutar la transformación y exportación
con.execute(query)

print(f"Archivo exportado exitosamente en: {parquet_output}")

# Opcional: Mostrar los primeros resultados para verificar
con.sql(f"SELECT * FROM read_parquet('{parquet_output}') LIMIT 5").show()