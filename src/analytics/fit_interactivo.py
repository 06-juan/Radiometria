"""
fit_interactivo.py
==================
Visualizador interactivo de ajuste PCR con sliders y botón de optimización.

Uso
---
    python fit_interactivo.py
    python fit_interactivo.py ruta/al/archivo.parquet

El parquet debe tener columnas:
    laser_freq, magnitude_normalized, phase_normalized, x_pos, y_pos

CORRECCIONES respecto a la versión original:
  ─ Ruta al parquet configurable: acepta argumento de línea de comandos
    (antes estaba hardcodeada a 'data/raw/FREQ_...' y fallaba si el script
    se ejecutaba desde otro directorio).
  ─ Búsqueda automática del parquet: si no se pasa argumento, busca en
    data/raw/, ../data/raw/ y el directorio del propio script.
  ─ Eliminada la inconsistencia de C_amp en la llamada a fitter.fit():
    ahora siempre se pasa el valor físico real (slider_C_amp.val * C_base),
    no un valor relativo.  fit_engine espera el valor físico.
  ─ Actualización de sliders post-optimización: se añade set_val para
    C_amp también (antes se actualizaba en el slider pero faltaba el clip
    al rango del slider).
  ─ ylim del panel de fase: fijado dinámicamente para evitar zoom erróneo
    cuando el modelo está muy alejado de los datos.
  ─ Manejo de errores en cargar_datos: mensaje claro si no hay datos en
    x=0, y=0 (antes el error era un IndexError críptico).
"""

import sys
import os
import glob

import duckdb
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

from fit_engine import PCRFitter
from pcr_model import pcr_amplitude_phase


# ─────────────────────────────────────────────────────────────────────────────
# PARÁMETROS FÍSICOS DE LA MUESTRA Y DEL MONTAJE
# Ajusta estos valores según tu oblea y longitud de onda del láser.
# ─────────────────────────────────────────────────────────────────────────────
GROSOR  = 0.025    # espesor de la oblea [cm]  (0.025 cm = 250 µm)
ALPHA   = 1e4      # coef. absorción óptica [cm⁻¹]
S2_FIJO = 1e7      # vel. recombinación trasera [cm/s]  (alta → fija)
SIGMA_FASE = 2.0   # peso de la fase en el ajuste [grados]


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_parquet():
    """Busca el primer .parquet disponible en rutas estándar del proyecto."""
    candidatos = [
        "data/raw/*.parquet",
        "../data/raw/*.parquet",
        os.path.join(os.path.dirname(__file__), "data", "raw", "*.parquet"),
        os.path.join(os.path.dirname(__file__), "*.parquet"),
        "*.parquet",
    ]
    for patron in candidatos:
        archivos = sorted(glob.glob(patron))
        if archivos:
            return archivos[-1]   # el más reciente (orden alfabético)
    return None


def cargar_datos(path_parquet: str):
    """
    Carga el espectro en frecuencia del punto central (x=0, y=0).

    Retorna
    -------
    f_exp     : array de frecuencias [Hz]
    amp_exp   : amplitud normalizada [u.a.]
    phase_exp : fase normalizada [grados]
    """
    con = duckdb.connect()
    mu_data = con.execute(f"""
        SELECT
            laser_freq,
            AVG(magnitude_normalized) AS magnitude_normalized,
            AVG(phase_normalized)     AS phase_normalized
        FROM read_parquet('{path_parquet}')
        WHERE x_pos = 0.0 AND y_pos = 0.0 AND laser_freq > 4000
        GROUP BY laser_freq
        ORDER BY laser_freq ASC
    """).fetchnumpy()

    if len(mu_data['laser_freq']) == 0:
        raise ValueError(
            f"No se encontraron datos con x_pos=0, y_pos=0 en '{path_parquet}'.\n"
            "Verifica que el archivo tenga mediciones en el origen."
        )

    return (
        mu_data['laser_freq'].astype(float),
        mu_data['magnitude_normalized'].astype(float),
        mu_data['phase_normalized'].astype(float),
    )


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def lanzar_interactivo(path_parquet: str = None):

    # ── Resolver ruta al parquet ──────────────────────────────────────────
    if path_parquet is None:
        path_parquet = _buscar_parquet()
    if path_parquet is None:
        raise FileNotFoundError(
            "No se encontró ningún archivo .parquet.\n"
            "Usa:  python fit_interactivo.py ruta/al/archivo.parquet"
        )
    print(f"Cargando datos: {path_parquet}")

    # ── Cargar datos ──────────────────────────────────────────────────────
    f_exp, amp_exp, phase_exp = cargar_datos(path_parquet)
    f_fine = np.logspace(np.log10(f_exp.min()), np.log10(f_exp.max()), 300)

    # ── Fitter e inicialización de C_base ─────────────────────────────────
    fitter = PCRFitter(GROSOR, ALPHA, sigma_fase=SIGMA_FASE)

    # C_base: factor para que el modelo coincida en amplitud con los datos
    # (con los parámetros iniciales de los sliders)
    tau_init, D_init, s1_init = 40e-6, 12.0, 1000.0
    amp_teo_ref, _ = pcr_amplitude_phase(
        [f_exp[0]], tau_init, D_init, s1_init, S2_FIJO,
        GROSOR, ALPHA, C_amp=1.0
    )
    C_base = amp_exp[0] / (amp_teo_ref[0] + 1e-30)

    # ── Figura ────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    plt.subplots_adjust(bottom=0.35)

    # Datos experimentales
    ax1.loglog(f_exp, amp_exp, 'ok', markersize=4, label='Experimental')
    ax2.semilogx(f_exp, phase_exp, 'ok', markersize=4)

    # Curvas del modelo (inicialmente planas; actualizar() las rellena)
    line_amp,   = ax1.loglog(f_fine, np.ones_like(f_fine),  'b-', lw=2, label='Modelo PCR')
    line_phase, = ax2.semilogx(f_fine, np.zeros_like(f_fine), 'b-', lw=2)

    ax1.set_ylabel("Amplitud Normalizada")
    ax1.legend(loc='upper right')
    ax1.grid(True, which="both", ls="--", alpha=0.5)
    ax2.set_ylabel("Fase (°)")
    ax2.set_xlabel("Frecuencia (Hz)")
    ax2.grid(True, which="both", ls="--", alpha=0.5)

    # ── Sliders ───────────────────────────────────────────────────────────
    ax_tau   = plt.axes([0.15, 0.24, 0.65, 0.03])
    ax_D     = plt.axes([0.15, 0.19, 0.65, 0.03])
    ax_s1    = plt.axes([0.15, 0.14, 0.65, 0.03])
    ax_C_amp = plt.axes([0.15, 0.09, 0.65, 0.03])

    slider_tau   = Slider(ax_tau,   'tau (µs)',   0.1,  500.0, valinit=tau_init*1e6, valfmt='%1.1f')
    slider_D     = Slider(ax_D,     'D (cm²/s)',  0.5,   40.0, valinit=D_init,       valfmt='%1.1f')
    slider_s1    = Slider(ax_s1,    's1 (cm/s)',  0.0, 5000.0, valinit=s1_init,      valfmt='%1.0f')
    slider_C_amp = Slider(ax_C_amp, 'Multipl. C', 0.1,    5.0, valinit=1.0,          valfmt='%1.2f')

    # ── Callback de actualización ─────────────────────────────────────────

    def actualizar(val):
        tau_fis   = slider_tau.val * 1e-6
        D_fis     = slider_D.val
        s1_fis    = slider_s1.val
        C_amp_fis = slider_C_amp.val * C_base    # valor físico real

        amp_teo, phase_teo = pcr_amplitude_phase(
            f_fine, tau_fis, D_fis, s1_fis, S2_FIJO,
            GROSOR, ALPHA, C_amp=C_amp_fis, n_points=60
        )

        line_amp.set_ydata(amp_teo)
        line_phase.set_ydata(phase_teo)

        # Ajustar límites dinámicamente
        ymin_amp = min(amp_exp.min(), amp_teo.min()) * 0.8
        ymax_amp = max(amp_exp.max(), amp_teo.max()) * 1.2
        ax1.set_ylim(ymin_amp, ymax_amp)

        ymin_ph = min(phase_exp.min(), phase_teo.min()) - 3
        ymax_ph = max(phase_exp.max(), phase_teo.max()) + 3
        ax2.set_ylim(ymin_ph, ymax_ph)

        fig.canvas.draw_idle()

    slider_tau.on_changed(actualizar)
    slider_D.on_changed(actualizar)
    slider_s1.on_changed(actualizar)
    slider_C_amp.on_changed(actualizar)

    actualizar(None)   # dibujo inicial

    # ── Botón de optimización ─────────────────────────────────────────────

    ax_boton = plt.axes([0.38, 0.02, 0.24, 0.05])
    btn = Button(ax_boton, '🚀 Optimizar', color='tomato', hovercolor='orangered')

    def ejecutar_ajuste(event):
        btn.label.set_text("Ajustando...")
        fig.canvas.draw()

        # Semillas desde los sliders (valores físicos reales)
        semillas = {
            'tau':   slider_tau.val * 1e-6,
            'D':     slider_D.val,
            's1':    slider_s1.val,
            's2':    S2_FIJO,
            'C_amp': slider_C_amp.val * C_base,
        }

        print("\n🔬 Lanzando ajuste con semillas manuales:")
        for k, v in semillas.items():
            print(f"   {k:6s} = {v:.4e}")

        resultado = fitter.fit(f_exp, amp_exp, phase_exp,
                               semillas=semillas, verbose=True)

        if resultado.success:
            print("\n✅ ¡Ajuste exitoso!")

            # Actualizar sliders con los valores óptimos
            slider_tau.set_val(np.clip(resultado.tau * 1e6,
                                       slider_tau.valmin, slider_tau.valmax))
            slider_D.set_val(np.clip(resultado.D,
                                     slider_D.valmin, slider_D.valmax))
            slider_s1.set_val(np.clip(resultado.s1,
                                      slider_s1.valmin, slider_s1.valmax))
            # C óptimo en unidades del slider (relativo a C_base)
            C_rel = resultado.C_amp / C_base
            slider_C_amp.set_val(np.clip(C_rel,
                                         slider_C_amp.valmin, slider_C_amp.valmax))

            # Pintar curva óptima en verde
            if resultado.f_fit is not None:
                line_amp.set_xdata(resultado.f_fit)
                line_amp.set_ydata(resultado.amp_fit)
                line_phase.set_xdata(resultado.f_fit)
                line_phase.set_ydata(resultado.phase_fit)

            line_amp.set_color('limegreen')
            line_phase.set_color('limegreen')
            line_amp.set_label('Ajuste Óptimo')
            ax1.legend(loc='upper right')

        else:
            print("\n⚠️  SciPy no convergió. Acerca más la curva azul a los datos e intenta de nuevo.")

        btn.label.set_text("🚀 Optimizar")
        fig.canvas.draw_idle()

    btn.on_clicked(ejecutar_ajuste)

    plt.suptitle(f"PCR — {os.path.basename(path_parquet)}", fontsize=10)
    plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parquet_arg = sys.argv[1] if len(sys.argv) > 1 else None
    lanzar_interactivo(parquet_arg)