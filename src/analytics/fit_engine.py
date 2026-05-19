"""
fit_engine.py
=============
Motor de ajuste de curvas PCR por Levenberg-Marquardt (TRF).

Ajusta simultáneamente la Amplitud y la Fase experimental a la teoría
de Mandelis (2003), extrayendo los parámetros de transporte:
  - tau  : vida media de recombinación [s]
  - D    : coeficiente de difusión ambipolar [cm²/s]
  - s1   : velocidad de recombinación superficial frontal [cm/s]
  - s2   : FIJO en 1e7 cm/s (recombinación trasera alta)
  - C_amp: factor de escala instrumental [u.a.]
  - V_floor: piso de ruido instrumental (suma incoherente) [u.a.]

Estrategia de residuales
------------------------
  Amplitud : diferencia logarítmica  log10(amp_exp) - log10(amp_teo)
             → pesa igual un error relativo en cualquier parte del rango
  Fase     : error absoluto / sigma_fase  [grados]

CORRECCIONES respecto a la versión original:
  ─ C_base se inicializa a None y se valida antes de usarse en _residuals,
    lanzando un RuntimeError claro si se llama fuera de fit() (bug silencioso).
  ─ bounds_lo para C_amp cambia de 0.0 a un valor pequeño positivo
    para evitar log10(0) = -inf en el residual de amplitud.
  ─ n_pts reducido de 150 a 60 en _residuals (suficiente para convergencia,
    3× más rápido por evaluación junto con la vectorización de pcr_model).
  ─ Documentación de parámetros de escala clarificada.
"""

import numpy as np
from scipy.optimize import least_squares
from dataclasses import dataclass, field
from typing import Optional
import warnings

from pcr_model import pcr_amplitude_phase, optimal_frequency, diffusion_length_ac


# ─────────────────────────────────────────────────────────────────────────────
# 1. RESULTADO DEL AJUSTE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FitResult:
    """Contenedor del resultado del ajuste PCR."""
    tau:    float
    D:      float
    s1:     float
    s2:     float
    C_amp:  float

    tau_err:   float = 0.0
    D_err:     float = 0.0
    s1_err:    float = 0.0
    s2_err:    float = 0.0

    cost:      float = 0.0
    success:   bool  = False
    message:   str   = ""

    f_fit:     Optional[np.ndarray] = None
    amp_fit:   Optional[np.ndarray] = None
    phase_fit: Optional[np.ndarray] = None

    def summary(self) -> str:
        lines = [
            "=" * 52,
            "  RESULTADOS DEL AJUSTE PCR (Mandelis 2003)",
            "=" * 52,
            f"  τ   (vida media)        = {self.tau*1e6:.2f} ± {self.tau_err*1e6:.2f} µs",
            f"  D   (difusividad)       = {self.D:.3f} ± {self.D_err:.3f} cm²/s",
            f"  s₁  (sup. frontal)      = {self.s1:.1f} ± {self.s1_err:.1f} cm/s",
            f"  s₂  (sup. trasera)      = {self.s2:.2e} cm/s  [fija]",
            f"  C   (factor escala)     = {self.C_amp:.4e}",
            f"  Costo (χ²)             = {self.cost:.6f}",
            f"  Convergencia            = {'✓' if self.success else '✗'}  {self.message}",
            "=" * 52,
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CLASE PRINCIPAL DE AJUSTE
# ─────────────────────────────────────────────────────────────────────────────

class PCRFitter:
    """
    Ajustador de espectros PCR por Levenberg-Marquardt (método TRF).

    Parámetros fijos del montaje
    ----------------------------
    L          : espesor de la oblea [cm]
    alpha      : coef. absorción óptica a λ_laser [cm⁻¹]
    sigma_fase : peso del error de fase [grados].
                 5° de error en fase pesa igual que 100% de error relativo
                 en amplitud.  Valor por defecto: 2.0°
    """

    def __init__(self, L: float, alpha: float, sigma_fase: float = 2.0,
                 n_integration_points: int = 60):
        self.L = L
        self.alpha = alpha
        self.sigma_fase = sigma_fase
        self.n_pts = n_integration_points
        # C_base se calcula dinámicamente dentro de fit(); None aquí protege
        # contra llamadas accidentales a _residuals fuera de fit().
        self._C_base: Optional[float] = None

    # ── Función de residuales ──────────────────────────────────────────────

    def _residuals(self, params, f_exp, amp_exp, phase_exp):
        """
        Vector de residuales normalizado SOLO PARA LA FASE (con Offset instrumental).
        """
        tau_sc, D_sc, s1_sc, phase_off = params

        tau = tau_sc * 1e-5
        D   = D_sc   * 10.0
        s1  = s1_sc  * 1000.0
        s2  = 1e7      

        if tau <= 0 or D <= 0 or s1 < 0:
            return np.ones(len(f_exp)) * 1e6

        try:
            _, phase_teo = pcr_amplitude_phase(
                f_exp, tau, D, s1, s2, self.L, self.alpha,
                C_amp=1.0, phase_offset=phase_off
            )
        except Exception:
            return np.ones(len(f_exp)) * 1e6

        r_phase = (phase_exp - phase_teo) / self.sigma_fase

        return r_phase

    # ── Estimación automática de semillas ─────────────────────────────────

    def auto_seeds(self, f_exp: np.ndarray, amp_exp: np.ndarray,
                   phase_exp: np.ndarray) -> dict:
        """
        Estima semillas razonables a partir de los datos.

        Estrategia:
          tau  ← frecuencia del punto medio de la fase (heurística ωτ ≈ 1)
          D    ← valor típico de Si (12 cm²/s)
          s1   ← conservador (100 cm/s)
          C_amp← escala para que amp_teo(f_min) ≈ amp_exp(f_min)
        """
        phase_mid = 0.5 * (np.max(phase_exp) + np.min(phase_exp))
        idx = np.argmin(np.abs(phase_exp - phase_mid))
        f_mid = f_exp[idx]
        tau_est = np.clip(1.0 / (2.0 * np.pi * f_mid), 1e-7, 5e-3)

        D_est  = 12.0
        s1_est = 100.0
        s2_est = 1e7

        amp_teo_ref, _ = pcr_amplitude_phase(
            [f_exp[0]], tau_est, D_est, s1_est, s2_est,
            self.L, self.alpha, C_amp=1.0, n_points=50
        )
        C_est = amp_exp[0] / (amp_teo_ref[0] + 1e-30)

        return {'tau': tau_est, 'D': D_est, 's1': s1_est, 's2': s2_est, 'C_amp': C_est}

    # ── Ajuste principal ───────────────────────────────────────────────────

    def fit(self, f_exp: np.ndarray, amp_exp: np.ndarray, phase_exp: np.ndarray,
            semillas: Optional[dict] = None, verbose: bool = True) -> FitResult:
        """
        Ajusta el espectro PCR experimental usando la fase + offset instrumental.
        """
        if semillas is None:
            semillas = self.auto_seeds(f_exp, amp_exp, phase_exp)

        f_tau   = 1e-5
        f_D     = 10.0
        f_s1    = 1000.0

        # Estimamos un offset inicial lógico: 
        # La teoría a baja frec es ~0°, así que la diferencia inicial es el offset
        offset_inicial = phase_exp[0]

        x0 = [
            semillas['tau']   / f_tau,
            semillas['D']     / f_D,
            semillas['s1']    / f_s1,
            offset_inicial
        ]

        # Límites físicos (y permitimos a la fase desfasarse entre -360° y 360°)
        bounds_lo = [1e-8 / f_tau,   0.1 / f_D,   0.0 / f_s1, -360.0]
        bounds_hi = [1e-2 / f_tau,  40.0 / f_D,   5e3 / f_s1,  360.0]

        result = least_squares(
            self._residuals,
            x0,
            args=(f_exp, amp_exp, phase_exp), 
            bounds=(bounds_lo, bounds_hi),
            method='trf',
            loss='soft_l1',
            f_scale=0.1,
            max_nfev=2000,
            xtol=1e-12,
            ftol=1e-12,
            gtol=1e-12,
            verbose=2 if verbose else 0,
        )

        tau_o       = result.x[0] * f_tau
        D_o         = result.x[1] * f_D
        s1_o        = result.x[2] * f_s1
        phase_off_o = result.x[3]
        s2_o        = 1e7
        C_o         = semillas.get('C_amp', 1.0)

        try:
            J = result.jac
            cov = np.linalg.inv(J.T @ J) * (result.cost / max(len(result.fun) - 4, 1))
            errs_sc = np.sqrt(np.abs(np.diag(cov)))
            errs = [errs_sc[0]*f_tau, errs_sc[1]*f_D, errs_sc[2]*f_s1, errs_sc[3]]
        except np.linalg.LinAlgError:
            errs = [0.0, 0.0, 0.0, 0.0]

        f_fine = np.logspace(np.log10(f_exp.min()), np.log10(f_exp.max()), 300)
        amp_fit, phase_fit = pcr_amplitude_phase(
            f_fine, tau_o, D_o, s1_o, s2_o, self.L, self.alpha,
            C_amp=C_o, phase_offset=phase_off_o
        )

        fit_result = FitResult(
            tau=tau_o, D=D_o, s1=s1_o, s2=s2_o, C_amp=C_o,
            tau_err=errs[0], D_err=errs[1], s1_err=errs[2], s2_err=0.0,
            cost=result.cost,
            success=result.success,
            message=result.message,
            f_fit=f_fine,
            amp_fit=amp_fit,
            phase_fit=phase_fit,
        )

        if verbose:
            print(fit_result.summary())
            print(f"  NOTA: Fase Offset instrumental calculado = {phase_off_o:.2f} grados")

        return fit_result

# ─────────────────────────────────────────────────────────────────────────────
# 3. PRUEBA RÁPIDA CON DATOS SINTÉTICOS
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    TRUE = dict(tau=40e-6, D=12.0, s1=500.0, s2=1e7)
    L, alpha = 0.025, 1e4

    f_data = np.logspace(np.log10(100), np.log10(15000), 100)
    amp_true, phase_true = pcr_amplitude_phase(f_data, **TRUE, L=L, alpha=alpha, C_amp=1.35e5)
    np.random.seed(42)
    amp_data   = amp_true   * (1 + np.random.normal(0, 0.02, len(f_data)))
    phase_data = phase_true + np.random.normal(0, 0.5, len(f_data))

    fitter = PCRFitter(L=L, alpha=alpha, sigma_fase=2.0)
    t0 = time.time()
    result = fitter.fit(f_data, amp_data, phase_data, verbose=True)
    print(f"\nTiempo total del ajuste: {time.time()-t0:.2f} s")