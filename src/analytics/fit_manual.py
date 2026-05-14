import duckdb
import numpy as np
import matplotlib.pyplot as plt
from fit_engine import PCRFitter

# --- Configuración ---
L_ESPESOR = 0.035       # cm
ALPHA_INP_532 = 1.5e5   # cm^-1
SIGMA_FASE = 2.0        
PATH = "/home/randiola/Documentos/Radiometria/data/FREQ_20260513_0843.parquet"

# Usamos fetchnumpy() para evitar crear un DataFrame de Pandas en memoria
con = duckdb.connect()
res = con.execute(f"""
    SELECT laser_freq, magnitude_r, phase_phi 
    FROM read_parquet('{PATH}')
    WHERE x_pos = 0.0 AND y_pos = 0.0
    ORDER BY laser_freq ASC
""").fetchnumpy()

f_exp = res['laser_freq'].astype(float)
amp_exp = res['magnitude_r'].astype(float)
phase_exp = res['phase_phi'].astype(float)

# --- Pre-procesamiento Crítico ---
# 1. Normalización de amplitud (ayuda a la convergencia del ajuste)
amp_norm = amp_exp / np.max(amp_exp)

# 2. Corrección de Fase (Opcional pero recomendado)
# El SR830 a veces entrega la fase "enroscada" o con un offset instrumental.
# Si tu fase empieza en -170° y baja a -190°, np.unwrap ayudará.
phase_exp = np.degrees(np.unwrap(np.radians(phase_exp)))

# --- Ajuste ---
fitter = PCRFitter(L=L_ESPESOR, alpha=ALPHA_INP_532, sigma_fase=SIGMA_FASE)

semillas = {
    'tau': 2e-6, 'D': 4.5, 's1': 500.0, 's2': 5000.0, 'C_amp': 1.0
}

resultado = fitter.fit(f_exp, amp_norm, phase_exp, semillas=semillas)

# --- Visualización de Resultados ---
if resultado.success:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    # Amplitud
    ax1.loglog(f_exp, amp_norm, 'ok', label='Datos InP', markersize=4)
    ax1.loglog(resultado.f_fit, resultado.amp_fit, 'r-', label='Ajuste Mandelis')
    ax1.set_ylabel("Amplitud Normalizada (u.a.)")
    ax1.legend()
    
    # Fase
    ax2.semilogx(f_exp, phase_exp, 'ok', markersize=4)
    ax2.semilogx(resultado.f_fit, resultado.phase_fit, 'r-')
    ax2.set_ylabel("Fase (grados)")
    ax2.set_xlabel("Frecuencia (Hz)")
    
    plt.suptitle(f"Ajuste PCR - InP (tau={resultado.tau*1e6:.2f} us)")
    plt.show()