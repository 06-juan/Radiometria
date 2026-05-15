import duckdb
import numpy as np
import matplotlib.pyplot as plt
from fit_engine import PCRFitter
import sys
import time
import threading
import os

def animar_spinner(evento_parar, texto="Ajustando modelo"):
    """Función para mostrar un spinner animado en la consola."""
    spinner = ['/', '-', '\\', '|']
    i = 0
    while not evento_parar.is_set():
        sys.stdout.write(f"\r🚀 {texto}... {spinner[i % len(spinner)]} ")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write(f"\r✅ {texto} completado!          \n")

def calibrar_y_guardar(path_muestra, path_calibracion, path_salida):
    con = duckdb.connect()

    # 1. INSPECCIONAR EL ESQUEMA
    columnas_info = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path_muestra}')").fetchall()
    nombres_columnas = [col[0] for col in columnas_info]

    # 2. VERIFICAR SI FALTA INFORMACIÓN Y ACTUALIZAR ARCHIVO ORIGINAL SI ES NECESARIO
    if 'phase_normalized' not in nombres_columnas or 'magnitude_normalized' not in nombres_columnas:
        print("⚠️ Faltan columnas procesadas en el archivo original. Actualizando Parquet...")
        
        # Cargar calibración
        cal_data = con.execute(f"SELECT laser_freq, phase_phi FROM read_parquet('{path_calibracion}') ORDER BY laser_freq ASC").fetchnumpy()
        
        # Cargar TODO el archivo de muestra
        todo_data = con.execute(f"SELECT * FROM read_parquet('{path_muestra}')").fetchnumpy()
        
        # Calcular fase normalizada e interpolada para cada fila
        # Usamos np.interp para ajustar la fase de calibración a las frecuencias de la muestra
        f_cal = cal_data['laser_freq'].astype(float)
        phi_cal = cal_data['phase_phi'].astype(float)
        
        phi_cal_interp = np.interp(todo_data['laser_freq'].astype(float), f_cal, phi_cal)
        phase_norm = todo_data['phase_phi'].astype(float) - phi_cal_interp
        
        # Calcular magnitud normalizada (global o por cada barrido, aquí lo hacemos global)
        mag_raw = todo_data['magnitude_r'].astype(float)
        mag_norm = mag_raw / np.max(mag_raw)
        
        # Añadir al dataset
        todo_data['phase_normalized'] = phase_norm
        todo_data['magnitude_normalized'] = mag_norm
        
        # Sobrescribir el archivo Parquet original
        temp_path = path_muestra + ".tmp"
        con.execute("CREATE TABLE t_update AS SELECT * FROM todo_data")
        con.execute(f"COPY t_update TO '{temp_path}' (FORMAT PARQUET)")
        con.execute("DROP TABLE t_update")
        
        # Reemplazo de archivo seguro
        os.remove(path_muestra)
        os.rename(temp_path, path_muestra)
        print("✅ Archivo original actualizado con 'phase_normalized' y 'magnitude_normalized'.")

    # 3. CARGA DE DATOS PARA EL AJUSTE (Ahora ya existen seguro)
    mu_data = con.execute(f"""
        SELECT laser_freq, magnitude_normalized, phase_normalized
        FROM read_parquet('{path_muestra}')
        WHERE x_pos = 0.0 AND y_pos = 0.0
        ORDER BY laser_freq ASC
    """).fetchnumpy()
    
    f_exp = mu_data['laser_freq'].astype(float)
    amp_norm = mu_data['magnitude_normalized'].astype(float)
    phase_true = mu_data['phase_normalized'].astype(float)

    # 4. EJECUTAR EL AJUSTE PCR
    fitter = PCRFitter(L=0.035, alpha=1.5e5, sigma_fase=2.0)
    semillas = {'tau': 1e-6, 'D': 3.0, 's1': 500.0, 's2': 5000.0, 'C_amp': 1.0}
    
    parar_spinner = threading.Event()
    hilo_spinner = threading.Thread(target=animar_spinner, args=(parar_spinner, "Ajustando modelo PCR"))

    try:
        hilo_spinner.start()
        resultado = fitter.fit(f_exp, amp_norm, phase_true, semillas=semillas)
    finally:
        parar_spinner.set()
        hilo_spinner.join()
    
    # 5. GUARDAR RESULTADOS DEL AJUSTE (Archivo de salida separado para el fit)
    if resultado.success:
        amp_fit_eval = np.interp(f_exp, resultado.f_fit, resultado.amp_fit)
        phase_fit_eval = np.interp(f_exp, resultado.f_fit, resultado.phase_fit)

        con.execute("""
            CREATE TABLE datos_fit AS 
            SELECT 
                unnest(?::DOUBLE[]) AS freq_hz,
                unnest(?::DOUBLE[]) AS amp_norm_exp,
                unnest(?::DOUBLE[]) AS phase_verdadera_deg,
                unnest(?::DOUBLE[]) AS amp_modelo,
                unnest(?::DOUBLE[]) AS phase_modelo
        """, [f_exp, amp_norm, phase_true, amp_fit_eval, phase_fit_eval])
        
        con.execute(f"COPY datos_fit TO '{path_salida}' (FORMAT PARQUET)")
        print(f"💾 Resultados del ajuste guardados en: {path_salida}")

    # 6. VISUALIZACIÓN
    if resultado.success:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        ax1.loglog(f_exp, amp_norm, 'ok', label='Medido (Normalizado)')
        ax1.loglog(resultado.f_fit, resultado.amp_fit, 'r-', label='Ajuste PCR')
        ax1.set_ylabel("Amplitud")
        ax1.legend()
        
        ax2.semilogx(f_exp, phase_true, 'ok')
        ax2.semilogx(resultado.f_fit, resultado.phase_fit, 'r-')
        ax2.set_ylabel("Fase (°)")
        ax2.set_xlabel("Frecuencia (Hz)")
        plt.show()

if __name__ == "__main__":
    calibrar_y_guardar(
        path_muestra="data/raw/FREQ_20260513_0843.parquet",
        path_calibracion="data/calibracion/calibracion.parquet",
        path_salida="data/procesados/PROCESADO_InP_0843.parquet"
    )