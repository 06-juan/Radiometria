"""
pcr_model.py
============
Modelo físico de Photocarrier Radiometry (PCR) para semiconductores.

Basado en:
  Mandelis, Batista & Shaughnessy, Phys. Rev. B 67, 205208 (2003)

CORRECCIONES FRENTE A VERSIÓN ANTERIOR:
  ─ Se eliminó la integración numérica (Gauss-Legendre) que sufría de
    submuestreo espacial severo en el primer micrómetro de la muestra.
  ─ Se implementó la solución analítica EXACTA de la integral espacial.
    Esto recupera el "codo filudo" natural de las altas frecuencias.
  ─ Corregido un error de signo en los coeficientes de frontera (G1, G2)
    que desfasaba la onda de portadores.
"""

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# 1. NÚMERO DE ONDA COMPLEJO DE PORTADORES
# ─────────────────────────────────────────────────────────────────────────────

def sigma_e(omega, tau, D):
    """
    Número de onda complejo σ_e(ω) = sqrt((1 + iωτ) / (D·τ))  [cm⁻¹].
    """
    return np.sqrt((1.0 + 1j * np.asarray(omega) * tau) / (D * tau))


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEÑAL PCR VECTORIZADA — INTEGRAL ANALÍTICA EXACTA
# ─────────────────────────────────────────────────────────────────────────────

def _pcr_signal_vectorized(f_array, tau, D, s1, s2, L, alpha,
                           n_points=None, eta_Q=1.0, P0=1.0, h_nu=1.0):
    """
    S(ω) = ∫₀ᴸ ΔN(z,ω) dz  para un array de frecuencias.
    
    Usa la primitiva analítica exacta, eliminando errores de cuadratura
    y devolviendo la forma perfecta de las caídas de alta frecuencia.
    """
    omega = 2.0 * np.pi * np.asarray(f_array, dtype=float)
    se = sigma_e(omega, tau, D)

    # Amplitud de fuente (constantes absorbidas por C_amp más adelante)
    A = eta_Q * P0 * alpha / (h_nu * D)

    # Factores adimensionales de frontera acoplados
    g1 = (D * alpha + s1) / (D * se + s1)
    g2 = (D * alpha - s2) / (D * se - s2)
    G1 = (D * se - s1) / (D * se + s1)
    G2 = (D * se + s2) / (D * se - s2)

    denom = G2 - G1 * np.exp(-2.0 * se * L)

    # Términos espaciales independientes de z (corregido el signo físico)
    T1 = G2 * g1 - G1 * g2 * np.exp(-(se + alpha) * L)
    T2 = denom
    T3 = g1 - g2 * np.exp(-(alpha - se) * L)

    # Primitivas exactas evaluadas de 0 a L: E = ∫ exp(...) dz
    E1 = (1.0 - np.exp(-se * L)) / se
    E2 = (1.0 - np.exp(-alpha * L)) / alpha
    E3 = (np.exp(-se * L) - np.exp(-2.0 * se * L)) / se

    # Suma de la integral analítica
    integral_exacta = T2 * E2 - T1 * E1 - T3 * E3

    # Señal total
    S = (A / (alpha**2 - se**2)) * (integral_exacta / denom)
    
    return S


# ─────────────────────────────────────────────────────────────────────────────
# 3. API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def pcr_amplitude_phase(f, tau, D, s1, s2, L, alpha,
                        C_amp=1.0, phase_offset=0.0, n_points=None):
    """
    Amplitud [u.a.] y fase [grados] de la señal PCR para frecuencias f [Hz].
    """
    f = np.asarray(f, dtype=float)
    S = _pcr_signal_vectorized(f, tau, D, s1, s2, L, alpha)
    S_scaled = C_amp * S
    # Sumamos el desfase instrumental a la fase teórica
    phase = np.angle(S_scaled, deg=True) + phase_offset
    return np.abs(S_scaled), phase


def diffusion_length_ac(f, tau, D):
    """
    |L_ac(f)| : longitud de difusión compleja AC [cm].
    """
    omega = 2.0 * np.pi * np.asarray(f)
    se = np.sqrt((1.0 + 1j * omega * tau) / (D * tau))
    return 1.0 / np.abs(se)


def optimal_frequency(tau, D, L):
    """
    Frecuencia donde |L_ac(f)| ≈ L/2 [Hz].
    """
    target = 2.0 / L
    val = (target**2 * D * tau)**2 - 1.0
    if val <= 0:
        return 1.0 / (2.0 * np.pi * tau)
    return np.sqrt(val) / (tau * 2.0 * np.pi)


# ─────────────────────────────────────────────────────────────────────────────
# 4. PRUEBA RÁPIDA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import time

    TAU, D_AMB, S1, S2 = 1e-3, 12.0, 10.0, 210.0
    L, ALPHA = 0.063, 1e4

    f_vec = np.logspace(1, np.log10(100000), 100) # Extendido a 100 kHz

    t0 = time.time()
    amp, phase = pcr_amplitude_phase(f_vec, TAU, D_AMB, S1, S2, L, ALPHA, C_amp=1e-4)
    print(f"Tiempo analítico ({len(f_vec)} freqs): {(time.time()-t0)*1000:.2f} ms")

    f_opt = optimal_frequency(TAU, D_AMB, L)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    ax1.loglog(f_vec, amp)
    ax1.axvline(f_opt, color='r', ls='--')
    ax1.set_ylabel("PCR Amplitude (a.u.)"); ax1.grid(True, which='both', alpha=0.3)
    ax2.semilogx(f_vec, phase)
    ax2.axvline(f_opt, color='r', ls='--')
    ax2.set_ylabel("PCR Phase (deg)"); ax2.set_xlabel("Frequency (Hz)")
    ax2.grid(True, which='both', alpha=0.3)
    plt.tight_layout()
    plt.show()