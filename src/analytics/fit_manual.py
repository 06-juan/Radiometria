import duckdb
import numpy as np
import matplotlib.pyplot as plt
from fit_engine import PCRFitter

def calibrar_y_guardar(path_muestra, path_calibracion, path_salida):
    """
    Carga los datos. Si la fase ya está normalizada, la lee directamente.
    Si no, usa el archivo de calibración para corregirla.
    Luego ajusta el modelo y guarda los datos procesados.
    """
    con = duckdb.connect()

    # 1. INSPECCIONAR EL ESQUEMA DEL ARCHIVO (Identificar si ya tiene la columna)
    # DESCRIBE nos devuelve los metadatos del archivo sin cargar todos los gigas/megas
    columnas_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path_muestra}')").fetchall()
    nombres_columnas = [col[0] for col in columnas_info]

    # 2. CARGA Y PRE-PROCESAMIENTO DINÁMICO
    if 'phase_normalizada' in nombres_columnas:
        print("✅ Columna 'phase_normalizada' detectada. Omitiendo calibración manual...")
        mu_data = con.execute(f"""
            SELECT laser_freq, magnitude_r, phase_normalizada
            FROM read_parquet('{path_muestra}')
            WHERE x_pos = 0.0 AND y_pos = 0.0
            ORDER BY laser_freq ASC
        """).fetchnumpy()
        
        f_exp = mu_data['laser_freq'].astype(float)
        amp_exp = mu_data['magnitude_r'].astype(float)
        phase_true = mu_data['phase_normalizada'].astype(float)
        
    else:
        print("⚠️ Columna 'phase_normalizada' NO detectada. Aplicando calibración al vuelo...")
        
        # Cargar muestra cruda
        mu_data = con.execute(f"""
            SELECT laser_freq, magnitude_r, phase_phi 
            FROM read_parquet('{path_muestra}')
            WHERE x_pos = 0.0 AND y_pos = 0.0
            ORDER BY laser_freq ASC
        """).fetchnumpy()
        
        f_exp = mu_data['laser_freq'].astype(float)
        amp_exp = mu_data['magnitude_r'].astype(float)
        phi_exp = mu_data['phase_phi'].astype(float)

        # Cargar calibración (Acero)
        cal_data = con.execute(f"""
            SELECT laser_freq, phase_phi 
            FROM read_parquet('{path_calibracion}') 
            ORDER BY laser_freq ASC
        """).fetchnumpy()
        
        f_cal = cal_data['laser_freq'].astype(float)
        phi_cal = cal_data['phase_phi'].astype(float)

        # Interpolación y resta
        phi_cal_interpolada = np.interp(f_exp, f_cal, phi_cal)
        phase_true = phi_exp - phi_cal_interpolada

    # 3. Normalizamos amplitud (Siempre se hace)
    amp_norm = amp_exp / np.max(amp_exp)

    # 4. EJECUTAR EL AJUSTE PCR
    fitter = PCRFitter(L=0.035, alpha=1.5e5, sigma_fase=2.0)
    semillas = {'tau': 1e-6, 'D': 3.0, 's1': 500.0, 's2': 5000.0, 'C_amp': 1.0}
    
    print("🚀 Iniciando ajuste PCR...")
    resultado = fitter.fit(f_exp, amp_norm, phase_true, semillas=semillas)
    
    # 5. GUARDAR DATOS PROCESADOS EN DUCKDB -> PARQUET
    amp_fit_eval = np.interp(f_exp, resultado.f_fit, resultado.amp_fit)
    phase_fit_eval = np.interp(f_exp, resultado.f_fit, resultado.phase_fit)

    con.execute("""
        CREATE TABLE datos_procesados AS 
        SELECT 
            unnest(?::DOUBLE[]) AS freq_hz,
            unnest(?::DOUBLE[]) AS amp_norm_exp,
            unnest(?::DOUBLE[]) AS phase_verdadera_deg,
            unnest(?::DOUBLE[]) AS amp_modelo,
            unnest(?::DOUBLE[]) AS phase_modelo
    """, [f_exp, amp_norm, phase_true, amp_fit_eval, phase_fit_eval])
    
    con.execute(f"COPY datos_procesados TO '{path_salida}' (FORMAT PARQUET)")
    print(f"💾 Datos procesados y ajuste guardados en: {path_salida}")

    # 6. VISUALIZACIÓN RÁPIDA
    if resultado.success:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        ax1.loglog(f_exp, amp_norm, 'ok', label='InP (Medido)')
        ax1.loglog(resultado.f_fit, resultado.amp_fit, 'r-', label='Mandelis Fit')
        ax1.set_ylabel("Amplitud Normalizada")
        ax1.legend()
        
        ax2.semilogx(f_exp, phase_true, 'ok')
        ax2.semilogx(resultado.f_fit, resultado.phase_fit, 'r-')
        ax2.set_ylabel("Fase Calibrada (°)")
        ax2.set_xlabel("Frecuencia (Hz)")
        plt.show()

# --- USO ---
if __name__ == "__main__":
    calibrar_y_guardar(
        path_muestra="data/raw/FREQ_20260513_0843.parquet",
        path_calibracion="data/calibracion/calibracion.parquet",
        path_salida="data/procesados/PROCESADO_InP_0843.parquet"
    )