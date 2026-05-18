import duckdb
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from fit_engine import PCRFitter
from pcr_model import pcr_amplitude_phase

def cargar_datos(path_muestra):
    con = duckdb.connect()
    mu_data = con.execute(f"""
        SELECT 
            laser_freq, 
            AVG(magnitude_normalized) AS magnitude_normalized, 
            AVG(phase_normalized) AS phase_normalized
        FROM read_parquet('{path_muestra}')
        WHERE x_pos = 0.0 AND y_pos = 0.0
        GROUP BY laser_freq
        ORDER BY laser_freq ASC
    """).fetchnumpy()
    
    return (mu_data['laser_freq'].astype(float), 
            mu_data['magnitude_normalized'].astype(float), 
            mu_data['phase_normalized'].astype(float))

def lanzar_interactivo():
    path_muestra = "data/raw/FREQ_20260515_1755.parquet"
    grosor = 0.025   
    alpha = 1e4      
    sigma_fase = 2.0
    s2_fijo = 1e7    
    
    f_exp, amp_exp, phase_exp = cargar_datos(path_muestra)
    f_fine = np.logspace(np.log10(f_exp.min()), np.log10(f_exp.max()), 200)

    fitter = PCRFitter(grosor, alpha, sigma_fase)

    # --- AQUÍ ESTÁ EL TRUCO: Calcular el orden de magnitud real del modelo ---
    amp_teo_cruda, _ = pcr_amplitude_phase([f_exp[0]], 40e-6, 12.0, 1000.0, s2_fijo, grosor, alpha, C_amp=1.0)
    C_base = amp_exp[0] / amp_teo_cruda[0]  # Típicamente será ~ 50,000 o más

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    plt.subplots_adjust(bottom=0.35)  

    ax1.loglog(f_exp, amp_exp, 'ok', markersize=4, label='Experimental')
    ax2.semilogx(f_exp, phase_exp, 'ok', markersize=4)

    line_amp, = ax1.loglog(f_fine, np.ones_like(f_fine), 'b-', linewidth=2, label='Modelo PCR')
    line_phase, = ax2.semilogx(f_fine, np.zeros_like(f_fine), 'b-', linewidth=2)

    ax1.set_ylabel("Amplitud Normalizada")
    ax1.legend(loc='upper right')
    ax1.grid(True, which="both", ls="--", alpha=0.5)
    ax2.set_ylabel("Fase (°)")
    ax2.set_xlabel("Frecuencia (Hz)")
    ax2.grid(True, which="both", ls="--", alpha=0.5)

    ax_tau   = plt.axes([0.15, 0.24, 0.65, 0.03])
    ax_D     = plt.axes([0.15, 0.19, 0.65, 0.03])
    ax_s1    = plt.axes([0.15, 0.14, 0.65, 0.03])
    ax_C_amp = plt.axes([0.15, 0.09, 0.65, 0.03])

    # El slider de C ahora va de 0.1 a 5.0 veces el C_base calculado
    slider_tau   = Slider(ax_tau,   'tau (µs)',    0.1,  500.0, valinit=40.0,  valfmt='%1.1f')
    slider_D     = Slider(ax_D,     'D (cm²/s)',   0.5,   40.0, valinit=12.0,  valfmt='%1.1f')
    slider_s1    = Slider(ax_s1,    's1 (cm/s)',   0.0, 5000.0, valinit=1000.0,valfmt='%1.0f')
    slider_C_amp = Slider(ax_C_amp, 'Multipl. C',  0.1,    5.0, valinit=1.0,   valfmt='%1.2f')

    def actualizar(val):
        tau_fisico = slider_tau.val * 1e-6 
        D_fisico = slider_D.val
        s1_fisico = slider_s1.val
        # Aplicamos la escala real combinada
        C_amp_fisico = slider_C_amp.val * C_base 

        amp_teo, phase_teo = pcr_amplitude_phase(
            f_fine, tau_fisico, D_fisico, s1_fisico, s2_fijo, 
            grosor, alpha, C_amp=C_amp_fisico, n_points=100
        )
        
        line_amp.set_ydata(amp_teo)
        line_phase.set_ydata(phase_teo)
        ax1.set_ylim(min(amp_exp.min(), amp_teo.min())*0.8, max(amp_exp.max(), amp_teo.max())*1.2)
        fig.canvas.draw_idle()

    slider_tau.on_changed(actualizar)
    slider_D.on_changed(actualizar)
    slider_s1.on_changed(actualizar)
    slider_C_amp.on_changed(actualizar)

    actualizar(None)

    ax_boton = plt.axes([0.4, 0.02, 0.2, 0.05])
    btn_optimizar = Button(ax_boton, '🚀 Optimizar', color='tomato', hovercolor='red')

    def ejecutar_ajuste_computacional(event):
        btn_optimizar.label.set_text("Ajustando...")
        fig.canvas.draw()
        
        semillas_actuales = {
            'tau': slider_tau.val * 1e-6,
            'D': slider_D.val,
            's1': slider_s1.val,
            'C_amp': slider_C_amp.val * C_base  # Enviamos el valor físico real
        }
        
        print("\n Lanzando SciPy con semillas manuales calibradas...")
        resultado = fitter.fit(f_exp, amp_exp, phase_exp, semillas=semillas_actuales, verbose=True)
        
        if resultado.success:
            print("¡Ajuste exitoso encontrado!")
            slider_tau.set_val(resultado.tau * 1e6)
            slider_D.set_val(resultado.D)
            slider_s1.set_val(resultado.s1)
            slider_C_amp.set_val(resultado.C_amp / C_base)
            
            line_amp.set_color('limegreen')
            line_phase.set_color('limegreen')
            line_amp.set_label('Ajuste Óptimo Computacional')
            ax1.legend(loc='upper right')
        else:
            print("SciPy falló. Ajusta más de cerca la curva azul e intenta de nuevo.")
            
        btn_optimizar.label.set_text("🚀 Optimizar")
        fig.canvas.draw_idle()

    btn_optimizar.on_clicked(ejecutar_ajuste_computacional)
    plt.show()

if __name__ == "__main__":
    lanzar_interactivo()