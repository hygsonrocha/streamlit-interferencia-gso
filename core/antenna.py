import math
import numpy as np


def ganho_antena_gso_s672(
    psi_deg,
    gmax_dbi: float,
    psi_b_deg: float,
    ln_db: float = -20.0,
    lf_db: float = 0.0,
):
    if psi_b_deg <= 0.0:
        raise ValueError("psi_b_deg deve ser positivo.")

    if ln_db not in (-20.0, -25.0):
        raise ValueError("ln_db deve ser -20.0 ou -25.0 neste modelo básico.")

    psi = np.asarray(psi_deg, dtype=float)

    if np.any((psi < 0.0) | (psi > 180.0)):
        raise ValueError("psi_deg deve estar no intervalo [0, 180] graus.")

    G = np.full_like(psi, np.nan, dtype=float)

    alpha = 2.0
    b = 6.32
    z = 1.0
    a = 2.58 if ln_db == -20.0 else 2.88

    lb_db = max(15.0 + ln_db + 0.25 * gmax_dbi + 5.0 * math.log10(z), 0.0)
    y_deg = b * psi_b_deg * 10.0 ** (0.04 * (gmax_dbi + ln_db - lf_db))
    psi_roll_end = min(y_deg, 90.0)

    r1 = (psi >= 0.0) & (psi <= a * psi_b_deg)
    r2 = (psi > a * psi_b_deg) & (psi <= b * psi_b_deg)
    r3 = (psi > b * psi_b_deg) & (psi <= psi_roll_end) & (y_deg > b * psi_b_deg)
    r4 = (psi > max(b * psi_b_deg, psi_roll_end)) & (psi <= 90.0)
    r5 = (psi > 90.0) & (psi <= 180.0)

    G[r1] = gmax_dbi - 3.0 * (psi[r1] / psi_b_deg) ** alpha
    G[r2] = gmax_dbi + ln_db
    G[r3] = gmax_dbi + ln_db + 20.0 - 25.0 * np.log10(psi[r3] / psi_b_deg)
    G[r4] = lf_db
    G[r5] = lb_db

    if G.ndim == 0:
        return float(G)

    return G


def low_elevation_excess_loss_dB(elev_deg: float) -> float:
    if elev_deg <= 0.0:
        return np.inf
    elif elev_deg < 1.0:
        return 6.0
    elif elev_deg < 2.0:
        return 4.0
    elif elev_deg < 5.0:
        return 2.0
    else:
        return 0.0
