"""
pcr_model.py
============
Modelo físico completo de Photocarrier Radiometry (PCR) para semiconductores.

Basado en:
  Mandelis, Batista & Shaughnessy, Phys. Rev. B 67, 205208 (2003)
  Ecuaciones (45)-(53): señal PCR como integral de ΔN(z,ω) sobre espesor L.

La señal compleja PCR (proporcional al detector InGaAs) es:

  S(ω) = F₂ · ∫₀ᴸ ΔN(z, ω) dz            [Ec. 45]

donde ΔN(z, ω) es la solución 1D de la ecuación de difusión de portadores:

  D·d²ΔN/dz² - (1 + iωτ)/τ · ΔN = -η_Q·P₀·α·exp(-αz)

con condiciones de frontera:
  D·dΔN/dz|_{z=0} = +s₁·ΔN(0)   (superficie frontal)
  D·dΔN/dz|_{z=L} = -s₂·ΔN(L)   (superficie trasera)

La solución analítica se obtiene por el método de Green (Ref. 14, Cap. 9 de Mandelis).
Aquí se implementa la versión compacta de la solución analítica de ΔN(z,ω) 
para una placa finita de espesor L.

Parámetros del modelo
---------------------
tau  : vida media de recombinación bulk [s]
D    : coeficiente de difusión ambipolar [cm²/s]
s1   : velocidad de recombinación superficial FRONTAL [cm/s]
s2   : velocidad de recombinación superficial TRASERA [cm/s]
L    : espesor de la oblea [cm]           (típico Si: 0.05 cm = 500 µm)
alpha: coef. absorción óptica a λ_laser [cm⁻¹]  (Si@514nm ~ 10⁴ cm⁻¹)
"""

import numpy as np
from scipy.integrate import quad


# ─────────────────────────────────────────────────────────────────────────────
# 1. NÚMERO DE ONDA COMPLEJO DE PORTADORES
# ─────────────────────────────────────────────────────────────────────────────

def sigma_e(omega, tau, D):
    """
    Número de onda complejo de la onda de difusión de portadores [cm⁻¹].

    σ_e(ω) = sqrt((1 + iωτ) / (D·τ))  =  1 / L_ac(ω)

    donde L_ac es la longitud de difusión compleja AC.
    """
    return np.sqrt((1.0 + 1j * omega * tau) / (D * tau))


# ─────────────────────────────────────────────────────────────────────────────
# 2. PERFIL DE PORTADORES ΔN(z, ω) — solución analítica placa finita
# ─────────────────────────────────────────────────────────────────────────────

def delta_N_profile(z, omega, tau, D, s1, s2, L, alpha, eta_Q=1.0, P0=1.0, h_nu=1.0):
    """
    Densidad de portadores fotogenerados ΔN(z, ω) para una placa finita.

    Solución analítica de la EDO de difusión con absorción óptica y dos
    condiciones de frontera (s1 frontal, s2 trasera). Ver Mandelis (2001)
    Diffusion-Wave Fields, Cap. 9, Ec. (9.106), simplificado a 1D.

    Parámetros
    ----------
    z      : posición en profundidad [cm]   (escalar o array)
    omega  : frecuencia angular [rad/s]
    tau    : vida media [s]
    D      : difusividad [cm²/s]
    s1     : velocidad recombinación frontal [cm/s]
    s2     : velocidad recombinación trasera [cm/s]
    L      : espesor [cm]
    alpha  : coeficiente absorción óptica [cm⁻¹]
    eta_Q  : eficiencia cuántica óptico→electrónica (adimensional)
    P0     : potencia láser [W] (factor de escala, absorbido en C)
    h_nu   : energía del fotón [J]  (absorbido en C)

    Retorna
    -------
    ΔN(z, ω) : array complejo [cm⁻³ · unidades de C]
    """
    se = sigma_e(omega, tau, D)   # complejo

    # Amplitud de la fuente (factor global de escala; se ajusta con C en el fit)
    A = eta_Q * P0 * alpha / (h_nu * D)

    # Factores adimensionales de frontera
    #   g₁ = (D·α + s₁) / (D·σ_e + s₁)
    #   g₂ = (D·α - s₂) / (D·σ_e - s₂)
    g1 = (D * alpha + s1) / (D * se + s1)
    g2 = (D * alpha - s2) / (D * se - s2)

    #   G₁ = (D·σ_e - s₁) / (D·σ_e + s₁)
    #   G₂ = (D·σ_e + s₂) / (D·σ_e - s₂)
    G1 = (D * se - s1) / (D * se + s1)
    G2 = (D * se + s2) / (D * se - s2)

    denom = G2 - G1 * np.exp(-2 * se * L)   # denominador de la solución

    # Numeradores de los términos de la solución particular homogénea
    #   Término proporcional a exp(-σ_e · z)  [onda hacia el interior]
    num_forward = (G2 * g1 - g2 * G1 * np.exp(-(se + alpha) * L)) / denom

    #   Término proporcional a exp(-σ_e · (2L - z))  [onda reflejada trasera]
    num_backward = (g1 - g2 * np.exp(-(alpha - se) * L)) / denom

    # Solución completa: particular (absorción óptica) + homogénea
    z = np.asarray(z, dtype=complex)

    dN = (A / (alpha**2 - se**2)) * (
        (num_forward * np.exp(-se * z) - np.exp(-se * (2*L - z)) * num_backward)
        - np.exp(-alpha * z)
        + (g1 - g2 * np.exp(-(alpha - se)*L)) / denom * np.exp(-se*(2*L-z))
    )

    # Forma compacta equivalente directa de la Ec. (9.106) de Mandelis 2001:
    # Se reescribe para evitar cancelaciones numéricas a alta frecuencia.
    numerator = (
        (G2*g1 - g2*G1*np.exp(-(se + alpha)*L)) * np.exp(-se*z)
        - np.exp(-alpha*z) * (G2 - G1*np.exp(-2*se*L))
        + (g1 - g2*np.exp(-(alpha-se)*L)) * np.exp(-se*(2*L-z))
    )

    return (A / (alpha**2 - se**2)) * (numerator / denom)


# ─────────────────────────────────────────────────────────────────────────────
# 3. SEÑAL PCR COMPLEJA — integral sobre el espesor
# ─────────────────────────────────────────────────────────────────────────────

def pcr_signal_complex(omega, tau, D, s1, s2, L, alpha,
                       n_points=200, eta_Q=1.0, P0=1.0, h_nu=1.0):
    """
    Señal PCR compleja S(ω) = C · ∫₀ᴸ ΔN(z,ω) dz   [Ec. 45 de Mandelis 2003]

    La constante C = F₂(λ₁,λ₂) agrupa todos los factores espectrales e
    instrumentales; se trata como parámetro libre en el ajuste (C_amp).

    Integración numérica sobre z con cuadratura de Gauss-Legendre.

    Retorna
    -------
    S_complex : número complejo (sin el factor C)
    """
    # Puntos de integración de Gauss-Legendre en [0, L]
    z_nodes, w_nodes = np.polynomial.legendre.leggauss(n_points)
    # Mapeo de [-1,1] → [0,L]
    z_phys = 0.5 * L * (z_nodes + 1.0)
    w_phys = 0.5 * L * w_nodes

    dN = delta_N_profile(z_phys, omega, tau, D, s1, s2, L, alpha, eta_Q, P0, h_nu)

    return np.dot(w_phys, dN)


def pcr_amplitude_phase(f, tau, D, s1, s2, L, alpha,
                        C_amp=1.0, n_points=200):
    """
    Retorna amplitud [u.a.] y fase [grados] de la señal PCR para un array
    de frecuencias f [Hz].

    Parámetros físicos fijos durante el ajuste:
      L     : espesor de la oblea [cm]
      alpha : coef. absorción óptica [cm⁻¹]

    Parámetros libres del ajuste:
      tau   : vida media [s]
      D     : difusividad [cm²/s]
      s1    : vel. recombinación frontal [cm/s]
      s2    : vel. recombinación trasera [cm/s]
      C_amp : factor de escala instrumental [u.a.]
    """
    f = np.asarray(f)
    amp = np.zeros(len(f))
    phase = np.zeros(len(f))

    for i, fi in enumerate(f):
        omega = 2 * np.pi * fi
        S = pcr_signal_complex(omega, tau, D, s1, s2, L, alpha, n_points)
        S_scaled = C_amp * S
        amp[i] = np.abs(S_scaled)
        phase[i] = np.angle(S_scaled, deg=True)

    return amp, phase


# ─────────────────────────────────────────────────────────────────────────────
# 4. LONGITUD DE DIFUSIÓN AC (útil para seleccionar frecuencia óptima)
# ─────────────────────────────────────────────────────────────────────────────

def diffusion_length_ac(f, tau, D):
    """
    Longitud de difusión compleja de portadores L_ac(ω).

    |L_ac| determina la profundidad de sondeo. Cuando |L_ac| ~ L/2,
    la sensibilidad de la fase a s₂ (superficie trasera) es máxima.

    Retorna |L_ac| en cm para cada frecuencia en f [Hz].
    """
    omega = 2 * np.pi * np.asarray(f)
    se = np.sqrt((1 + 1j * omega * tau) / (D * tau))
    return 1.0 / np.abs(se)


def optimal_frequency(tau, D, L):
    """
    Estima la frecuencia donde |L_ac(f)| ≈ L/2 (máxima sensibilidad de fase).

    Resuelve: |L_ac(f)| = L/2  =>  f ≈ (1/(2π)) · sqrt( (4D/L²)² + (1/τ)² ) - 1/τ

    Retorna f_opt en Hz.
    """
    # |se|² = (1 + ω²τ²)^(1/2) / (Dτ)  — aproximación para ωτ >> 1:
    # |L_ac| ≈ (D*tau)^(1/2) / (1 + ω²τ²)^(1/4) = L/2
    # => ω_opt ≈ sqrt( ((2/L)² * D*tau)² - 1 ) / tau
    target = (2.0 / L)   # |se_opt| = 2/L  =>  |L_ac| = L/2
    # |se|² = sqrt(1 + ω²τ²) / (Dτ)  => ω²τ² = (target²·Dτ)² - 1
    val = (target**2 * D * tau)**2 - 1
    if val <= 0:
        # Régimen DC: frecuencia muy baja
        return 1.0 / (2 * np.pi * tau)
    omega_opt = np.sqrt(val) / tau
    return omega_opt / (2 * np.pi)


# ─────────────────────────────────────────────────────────────────────────────
# 5. PRUEBA RÁPIDA (ejecutar directamente)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    # Parámetros típicos de Si tipo-p (Mandelis 2003, Fig. 14)
    TAU   = 1e-3      # 1 ms
    D_AMB = 12.0      # cm²/s
    S1    = 10.0      # cm/s  (superficie pulida, baja)
    S2    = 210.0     # cm/s  (superficie trasera)
    L     = 0.063     # cm  (630 µm — oblea típica de Si)
    ALPHA = 1e4       # cm⁻¹ a 514 nm en Si

    f_vec = np.logspace(1, np.log10(5000), 80)   # 10 Hz – 5 kHz

    amp, phase = pcr_amplitude_phase(f_vec, TAU, D_AMB, S1, S2, L, ALPHA, C_amp=1e-4)

    f_opt = optimal_frequency(TAU, D_AMB, L)
    print(f"Frecuencia óptima de sondeo: {f_opt:.1f} Hz")
    print(f"|L_ac| a esa frecuencia: {diffusion_length_ac([f_opt], TAU, D_AMB)[0]*1e4:.0f} µm  "
          f"(L/2 = {L/2*1e4:.0f} µm)")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    ax1.loglog(f_vec, amp)
    ax1.axvline(f_opt, color='r', linestyle='--', label=f'f_opt = {f_opt:.0f} Hz')
    ax1.set_ylabel("PCR Amplitude (a.u.)")
    ax1.legend()
    ax1.grid(True, which='both', alpha=0.3)

    ax2.semilogx(f_vec, phase)
    ax2.axvline(f_opt, color='r', linestyle='--')
    ax2.set_ylabel("PCR Phase (deg)")
    ax2.set_xlabel("Frequency (Hz)")
    ax2.grid(True, which='both', alpha=0.3)

    plt.tight_layout()
    plt.savefig("data/pcr_model_test.png", dpi=150)
    plt.show()
    print("Figura guardada en pcr_model_test.png")