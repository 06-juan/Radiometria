"""
fit_engine.py
=============
Motor de ajuste de curvas PCR por Levenberg-Marquardt.

Ajusta simultáneamente la Amplitud y la Fase experimental a la teoría
de Mandelis (2003), extrayendo los parámetros de transporte:
  - tau  : vida media de recombinación [s]
  - D    : coeficiente de difusión ambipolar [cm²/s]
  - s1   : velocidad de recombinación superficial frontal [cm/s]
  - s2   : velocidad de recombinación superficial trasera [cm/s]
  - C_amp: factor de escala instrumental [u.a.]

Estrategia de normalización del vector de residuales
-----------------------------------------------------
Un error de 1% en amplitud debe pesar igual que un error de ~1° en fase.
La normalización se hace:
  - Amplitud: error relativo  = (amp_exp - amp_teo) / amp_exp
  - Fase:     error absoluto  = (fase_exp - fase_teo) / sigma_fase
    donde sigma_fase ≈ 5° (ajustable según ruido experimental).

Uso básico
----------
>>> from analytics.fit_engine import PCRFitter
>>> fitter = PCRFitter(L=0.063, alpha=1e4)
>>> result = fitter.fit(f_data, amp_data, phase_data, semillas)
>>> print(result.summary())
"""

import numpy as np
from scipy.optimize import least_squares
from dataclasses import dataclass
from typing import Optional
import warnings

from pcr_model import pcr_amplitude_phase, optimal_frequency, diffusion_length_ac


# ─────────────────────────────────────────────────────────────────────────────
# 1. RESULTADO DEL AJUSTE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FitResult:
    """Contenedor del resultado del ajuste PCR."""
    tau:    float        # vida media [s]
    D:      float        # difusividad [cm²/s]
    s1:     float        # vel. recombinación frontal [cm/s]
    s2:     float        # vel. recombinación trasera [cm/s]
    C_amp:  float        # factor de escala

    # Incertidumbres (1-sigma estimadas de la jacobiana)
    tau_err:   float = 0.0
    D_err:     float = 0.0
    s1_err:    float = 0.0
    s2_err:    float = 0.0

    # Métricas de calidad
    cost:      float = 0.0    # suma de residuales al cuadrado
    success:   bool  = False
    message:   str   = ""

    # Curvas del ajuste (para graficar)
    f_fit:     Optional[np.ndarray] = None
    amp_fit:   Optional[np.ndarray] = None
    phase_fit: Optional[np.ndarray] = None

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "  RESULTADOS DEL AJUSTE PCR (Mandelis 2003)",
            "=" * 50,
            f"  τ   (vida media)        = {self.tau*1e3:.3f} ± {self.tau_err*1e3:.3f} ms",
            f"  D   (difusividad)       = {self.D:.2f} ± {self.D_err:.2f} cm²/s",
            f"  s₁  (sup. frontal)      = {self.s1:.1f} ± {self.s1_err:.1f} cm/s",
            f"  s₂  (sup. trasera)      = {self.s2:.1f} ± {self.s2_err:.1f} cm/s",
            f"  C   (factor escala)     = {self.C_amp:.3e}",
            f"  Costo (χ²)             = {self.cost:.4f}",
            f"  Convergencia            = {'✓' if self.success else '✗'}  {self.message}",
            "=" * 50,
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CLASE PRINCIPAL DE AJUSTE
# ─────────────────────────────────────────────────────────────────────────────

class PCRFitter:
    """
    Ajustador de espectros PCR por Levenberg-Marquardt.

    Parámetros fijos (propiedades de la muestra y del montaje)
    ----------------------------------------------------------
    L     : float — espesor de la oblea [cm]   (ej. 0.050 para 500 µm)
    alpha : float — coef. absorción óptica a λ_laser [cm⁻¹]
                    Si a 514 nm: ~10⁴; Si a 532 nm: ~8x10³

    sigma_fase : float — peso del error de fase [grados].
        Un valor de 5 significa que 5° de error en fase pesa igual
        que 100% de error relativo en amplitud.
    """

    # Límites físicos de los parámetros (Si)
    # [tau_min, tau_max, D_min, D_max, s1_min, s1_max, s2_min, s2_max, C_min, C_max]
    BOUNDS_LOWER = [1e-8,  0.1,    1.0,  1.0,    0.0,   1e-6]
    BOUNDS_UPPER = [1e-2,  40.0,  1e6,   1e6,    np.inf, np.inf]
    #               tau     D      s1     s2       C_amp   (reordenado abajo)

    def __init__(self, L: float, alpha: float, sigma_fase: float = 5.0,
                 n_integration_points: int = 150):
        self.L = L
        self.alpha = alpha
        self.sigma_fase = sigma_fase
        self.n_pts = n_integration_points

    # ── Función de residuales ──────────────────────────────────────────────

    def _residuals(self, params, f_exp, amp_exp, phase_exp):
        """
        Vector de residuales normalizados para scipy.optimize.least_squares.

        params = [tau, D, s1, s2, C_amp]
        """
        tau, D, s1, s2, C_amp = params

        # Evitar parámetros no físicos durante la iteración
        if tau <= 0 or D <= 0 or s1 < 0 or s2 < 0 or C_amp <= 0:
            return np.ones(2 * len(f_exp)) * 1e6

        try:
            amp_teo, phase_teo = pcr_amplitude_phase(
                f_exp, tau, D, s1, s2, self.L, self.alpha,
                C_amp=C_amp, n_points=self.n_pts
            )
        except Exception:
            return np.ones(2 * len(f_exp)) * 1e6

        # Error relativo en amplitud (sin unidades)
        with np.errstate(divide='ignore', invalid='ignore'):
            r_amp = np.where(amp_exp > 0,
                             (amp_exp - amp_teo) / amp_exp,
                             amp_exp - amp_teo)

        # Error absoluto en fase, normalizado por sigma_fase
        r_phase = (phase_exp - phase_teo) / self.sigma_fase

        return np.concatenate([r_amp, r_phase])

    # ── Estimación automática de semillas ─────────────────────────────────

    def auto_seeds(self, f_exp: np.ndarray, amp_exp: np.ndarray,
                   phase_exp: np.ndarray) -> dict:
        """
        Estima semillas iniciales razonables a partir de los datos.

        Estrategia:
        - tau: la fase cae 45° respecto a su máximo ≈ cuando ωτ = 1
        - D: valor típico de Si (12-15 cm²/s)
        - s1, s2: valores conservadores intermedios
        - C_amp: escala para que amp_teo(f_min) ≈ amp_exp(f_min)
        """
        # Estimación de tau desde la frecuencia donde la fase empieza a caer
        # El cruce de -45° es una heurística razonable
        phase_mid = 0.5 * (np.max(phase_exp) + np.min(phase_exp))
        idx = np.argmin(np.abs(phase_exp - phase_mid))
        f_mid = f_exp[idx]
        tau_est = 1.0 / (2 * np.pi * f_mid)
        tau_est = np.clip(tau_est, 1e-7, 5e-3)

        D_est = 12.0    # cm²/s — valor típico de Si
        s1_est = 100.0  # cm/s
        s2_est = 300.0  # cm/s

        # Factor de escala: ajustar para que el primer punto coincida
        amp_teo_ref, _ = pcr_amplitude_phase(
            [f_exp[0]], tau_est, D_est, s1_est, s2_est,
            self.L, self.alpha, C_amp=1.0, n_points=50
        )
        C_est = amp_exp[0] / (amp_teo_ref[0] + 1e-30)

        return {
            'tau':   tau_est,
            'D':     D_est,
            's1':    s1_est,
            's2':    s2_est,
            'C_amp': C_est,
        }

    # ── Ajuste principal ───────────────────────────────────────────────────

    def fit(self,
            f_exp:     np.ndarray,
            amp_exp:   np.ndarray,
            phase_exp: np.ndarray,
            semillas:  Optional[dict] = None,
            verbose:   bool = True) -> FitResult:
        """
        Ejecuta el ajuste Levenberg-Marquardt.

        Parámetros
        ----------
        f_exp     : array de frecuencias [Hz]
        amp_exp   : array de amplitudes [u.a.] (ya normalizadas al ref)
        phase_exp : array de fases [grados]
        semillas  : dict con llaves tau, D, s1, s2, C_amp.
                    Si es None, se estiman automáticamente.
        verbose   : imprime resultado al terminar

        Retorna
        -------
        FitResult con parámetros ajustados e incertidumbres.
        """
        if semillas is None:
            semillas = self.auto_seeds(f_exp, amp_exp, phase_exp)

        x0 = [semillas['tau'], semillas['D'],
               semillas['s1'],  semillas['s2'], semillas['C_amp']]

        bounds_lo = [1e-8,  0.1,  0.0,  0.0,  0.0]
        bounds_hi = [1e-2, 40.0, 1e6,  1e6,  np.inf]

        result = least_squares(
            self._residuals,
            x0,
            args=(f_exp, amp_exp, phase_exp),
            bounds=(bounds_lo, bounds_hi),
            method='trf',         # Trust Region Reflective (LM con límites)
            loss='soft_l1',       # robusto a outliers
            f_scale=0.1,          # escala de la pérdida robusta
            max_nfev=2000,
            xtol=1e-10,
            ftol=1e-10,
            gtol=1e-10,
            verbose=1 if verbose else 0,
        )

        tau_o, D_o, s1_o, s2_o, C_o = result.x

        # Estimación de incertidumbres desde la jacobiana
        try:
            J = result.jac
            cov = np.linalg.inv(J.T @ J) * (result.cost / (len(result.fun) - 5))
            errs = np.sqrt(np.abs(np.diag(cov)))
        except np.linalg.LinAlgError:
            errs = np.zeros(5)
            warnings.warn("No se pudo invertir la Jacobiana; incertidumbres no disponibles.")

        # Curvas del ajuste (resolución más alta para graficar)
        f_fine = np.logspace(np.log10(f_exp.min()), np.log10(f_exp.max()), 200)
        amp_fit, phase_fit = pcr_amplitude_phase(
            f_fine, tau_o, D_o, s1_o, s2_o, self.L, self.alpha,
            C_amp=C_o, n_points=self.n_pts
        )

        fit_result = FitResult(
            tau=tau_o, D=D_o, s1=s1_o, s2=s2_o, C_amp=C_o,
            tau_err=errs[0], D_err=errs[1], s1_err=errs[2], s2_err=errs[3],
            cost=result.cost,
            success=result.success,
            message=result.message,
            f_fit=f_fine,
            amp_fit=amp_fit,
            phase_fit=phase_fit,
        )

        if verbose:
            print(fit_result.summary())
            f_opt = optimal_frequency(tau_o, D_o, self.L)
            L_ac = diffusion_length_ac([f_opt], tau_o, D_o)[0]
            print(f"\n  → Frecuencia óptima de barrido XY: {f_opt:.1f} Hz")
            print(f"    |L_ac| = {L_ac*1e4:.0f} µm  (L/2 = {self.L/2*1e4:.0f} µm)")

        return fit_result


# ─────────────────────────────────────────────────────────────────────────────
# 3. PRUEBA RÁPIDA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from pcr_model import pcr_amplitude_phase
    import numpy as np

    # Parámetros "verdaderos" (simulados)
    TRUE = dict(tau=1e-3, D=12.0, s1=10.0, s2=210.0)
    L, alpha = 0.063, 1e4

    f_data = np.logspace(1, np.log10(5000), 60)
    amp_true, phase_true = pcr_amplitude_phase(
        f_data, **TRUE, L=L, alpha=alpha, C_amp=5e-5)
    np.random.seed(42)
    amp_data   = amp_true   * (1 + np.random.normal(0, 0.02, len(f_data)))
    phase_data = phase_true + np.random.normal(0, 0.5, len(f_data))

    fitter = PCRFitter(L=L, alpha=alpha)
    result = fitter.fit(f_data, amp_data, phase_data)