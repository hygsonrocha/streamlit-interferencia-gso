import math
import numpy as np


TX_VERTICAL_HPBW_TARGET_DEG = {
    1: 59.0,
    2: 27.0,
    4: 13.0,
    6: 8.5,
}


# ============================================================
# Antena RX do satélite GSO
# ============================================================

def psi_b_deg_from_gmax(gmax_dbi: float, eta_ap: float = 0.60) -> float:
    r"""
    Aproxima psi_b (meia largura a 3 dB, em graus)
    a partir do ganho máximo da antena.

    Hipótese:
    - feixe circular simples
    - ganho de abertura: G_lin ≈ eta_ap * (pi * D/lambda)^2
    - meia largura a 3 dB: psi_b ≈ 36 * lambda / D  [graus]

    Resultado:
    psi_b_deg ≈ 36*pi*sqrt(eta_ap) * 10^(-gmax_dbi/20)
    """
    eta_ap = float(eta_ap)
    if not (0.0 < eta_ap <= 1.0):
        raise ValueError("eta_ap deve estar no intervalo (0, 1].")

    return float(36.0 * np.pi * np.sqrt(eta_ap) * 10.0 ** (-float(gmax_dbi) / 20.0))


def resolve_psi_b_deg(gmax_dbi: float, psi_b_deg: float | None = None, eta_ap: float = 0.60) -> float:
    """
    Resolve o valor de psi_b usado no padrão RX do satélite.

    Se psi_b_deg for None, calcula-o a partir de gmax_dbi e eta_ap.
    Caso contrário, usa o valor explícito fornecido.
    """
    if psi_b_deg is None:
        return psi_b_deg_from_gmax(gmax_dbi=float(gmax_dbi), eta_ap=float(eta_ap))

    psi_b_deg = float(psi_b_deg)
    if psi_b_deg <= 0.0:
        raise ValueError("psi_b_deg deve ser positivo.")
    return psi_b_deg


def ganho_antena_gso_s672(
    psi_deg,
    gmax_dbi: float,
    psi_b_deg: float | None = None,
    eta_ap: float = 0.60,
    ln_db: float = -20.0,
    lf_db: float = 0.0,
):
    r"""
    Envelope simplificado inspirado na ITU-R S.672-4
    para antena RX GSO de feixe simples circular.
    """
    psi = np.abs(np.asarray(psi_deg, dtype=float))
    if np.any(psi > 180.0):
        raise ValueError("psi_deg deve estar no intervalo [0, 180] graus em valor absoluto.")

    psi_b_deg = resolve_psi_b_deg(gmax_dbi=float(gmax_dbi), psi_b_deg=psi_b_deg, eta_ap=float(eta_ap))

    if ln_db not in (-20.0, -25.0):
        raise ValueError("ln_db deve ser -20.0 ou -25.0 neste modelo básico.")

    G = np.full_like(psi, np.nan, dtype=float)

    alpha = 2.0
    b = 6.32
    z = 1.0
    a = 2.58 if ln_db == -20.0 else 2.88

    lb_db = max(15.0 + float(ln_db) + 0.25 * float(gmax_dbi) + 5.0 * math.log10(z), 0.0)
    y_deg = b * psi_b_deg * 10.0 ** (0.04 * (float(gmax_dbi) + float(ln_db) - float(lf_db)))
    psi_roll_end = min(y_deg, 90.0)

    r1 = (psi >= 0.0) & (psi <= a * psi_b_deg)
    r2 = (psi > a * psi_b_deg) & (psi <= b * psi_b_deg)
    r3 = (psi > b * psi_b_deg) & (psi <= psi_roll_end) & (y_deg > b * psi_b_deg)
    r4 = (psi > max(b * psi_b_deg, psi_roll_end)) & (psi <= 90.0)
    r5 = (psi > 90.0) & (psi <= 180.0)

    G[r1] = float(gmax_dbi) - 3.0 * (psi[r1] / psi_b_deg) ** alpha
    G[r2] = float(gmax_dbi) + float(ln_db)
    G[r3] = float(gmax_dbi) + float(ln_db) + 20.0 - 25.0 * np.log10(psi[r3] / psi_b_deg)
    G[r4] = float(lf_db)
    G[r5] = lb_db

    if G.ndim == 0:
        return float(G)

    return G


def build_rx_pattern_s672(
    gmax_dbi: float,
    psi_b_deg: float | None = None,
    eta_ap: float = 0.60,
    ln_db: float = -20.0,
    lf_db: float = 0.0,
    angle_step_deg: float = 0.1,
) -> dict:
    """
    Constrói um perfil do padrão RX do satélite GSO para uso em gráficos e relatórios.
    """
    if angle_step_deg <= 0.0:
        raise ValueError("angle_step_deg deve ser positivo.")

    psi_used_deg = resolve_psi_b_deg(gmax_dbi=float(gmax_dbi), psi_b_deg=psi_b_deg, eta_ap=float(eta_ap))
    angle_deg = np.arange(0.0, 180.0 + 0.5 * angle_step_deg, angle_step_deg, dtype=float)
    gain_dbi = ganho_antena_gso_s672(
        psi_deg=angle_deg,
        gmax_dbi=float(gmax_dbi),
        psi_b_deg=psi_used_deg,
        eta_ap=float(eta_ap),
        ln_db=float(ln_db),
        lf_db=float(lf_db),
    )

    return {
        "angle_deg": angle_deg,
        "gain_dbi": np.asarray(gain_dbi, dtype=float),
        "model_name": "s672_simplified_single_beam",
        "gmax_dbi": float(gmax_dbi),
        "psi_b_deg_used": float(psi_used_deg),
        "psi_b_deg_input": None if psi_b_deg is None else float(psi_b_deg),
        "eta_ap": float(eta_ap),
        "ln_db": float(ln_db),
        "lf_db": float(lf_db),
    }


# ============================================================
# Antena TX terrestre: modelo analítico vertical
# ============================================================

def q_from_single_level_hpbw(hpbw_deg: float) -> float:
    r"""
    Ajusta o fator de elemento:

        E_elem(theta) = |cos(theta)|^q

    impondo a condição de meia potência para 1 nível:

        |cos(theta_3dB)|^q = 1/sqrt(2)

    com:
        theta_3dB = HPBW / 2
    """
    if hpbw_deg <= 0.0 or hpbw_deg >= 180.0:
        raise ValueError("hpbw_deg deve estar no intervalo (0, 180).")

    theta_3db_deg = 0.5 * float(hpbw_deg)
    theta_3db_rad = np.deg2rad(theta_3db_deg)

    cos_val = float(np.cos(theta_3db_rad))
    if cos_val <= 0.0:
        raise ValueError("A HPBW escolhida leva a cos(theta_3dB) não positivo.")

    q = np.log(1.0 / np.sqrt(2.0)) / np.log(cos_val)
    return float(q)


def element_factor_vertical(theta_deg, q: float):
    r"""
    Fator de elemento vertical normalizado:

        E_elem(theta) = |cos(theta)|^q

    theta é a elevação em graus, medida a partir do horizonte.
    """
    theta_rad = np.deg2rad(np.asarray(theta_deg, dtype=float))
    e = np.abs(np.cos(theta_rad)) ** float(q)
    e = e / np.max(e)
    return np.clip(e, 1e-12, 1.0)


def uniform_weights(n: int) -> np.ndarray:
    if int(n) <= 0:
        raise ValueError("n deve ser positivo.")
    return np.ones(int(n), dtype=float)


def binomial_weights(n: int) -> np.ndarray:
    r"""
    Pesos binomiais para um null-filling simples.
    """
    from math import comb

    n = int(n)
    if n <= 0:
        raise ValueError("n deve ser positivo.")

    w = np.array([comb(n - 1, k) for k in range(n)], dtype=float)
    return w / np.max(w)


def get_tx_weights(n: int, use_binomial: bool = False) -> np.ndarray:
    return binomial_weights(n) if bool(use_binomial) else uniform_weights(n)


def array_factor_vertical(theta_deg, n_levels: int, d_lambda: float = 1.0, beta_rad: float = 0.0, weights=None):
    r"""
    Array factor vertical:

                            N-1
                           -----
                            \         j m (2*pi*d_lambda*sin(theta) + beta)
        AF_N(theta) = | 1/W  >  w_m e
                            /
                           -----
                            m=0
    """
    n_levels = int(n_levels)
    if n_levels <= 0:
        raise ValueError("n_levels deve ser positivo.")
    if d_lambda <= 0.0:
        raise ValueError("d_lambda deve ser positivo.")

    theta_rad = np.deg2rad(np.asarray(theta_deg, dtype=float))

    if weights is None:
        weights = uniform_weights(n_levels)
    else:
        weights = np.asarray(weights, dtype=float)
        if len(weights) != n_levels:
            raise ValueError("len(weights) deve ser igual a n_levels")
        if np.any(weights < 0.0):
            raise ValueError("weights não pode conter valores negativos.")
        if np.all(weights == 0.0):
            raise ValueError("weights não pode ser todo zero.")

    m = np.arange(n_levels, dtype=float)
    psi = 2.0 * np.pi * float(d_lambda) * np.sin(theta_rad) + float(beta_rad)

    af_complex = np.sum(weights[:, None] * np.exp(1j * np.outer(m, psi)), axis=0)
    af = np.abs(af_complex) / np.sum(weights)
    return np.clip(af, 1e-12, 1.0)


def vertical_pattern_levels(theta_deg, n_levels: int, d_lambda: float = 1.0, q: float | None = None, beta_rad: float = 0.0, weights=None):
    r"""
    Padrão total vertical:

        E_TX(theta) = E_elem(theta) * AF_N(theta)
    """
    if q is None:
        q = q_from_single_level_hpbw(TX_VERTICAL_HPBW_TARGET_DEG[1])

    e_elem = element_factor_vertical(theta_deg, q=float(q))
    af = array_factor_vertical(
        theta_deg,
        n_levels=int(n_levels),
        d_lambda=float(d_lambda),
        beta_rad=float(beta_rad),
        weights=weights,
    )

    e_total = e_elem * af
    e_total = e_total / np.max(e_total)
    return np.clip(e_total, 1e-12, 1.0)


def hpbw_deg_from_pattern(theta_deg, e_rel) -> float:
    r"""
    Calcula a largura a meia potência (HPBW), assumindo máximo em theta=0
    e padrão simétrico.
    """
    theta_deg = np.asarray(theta_deg, dtype=float)
    e_rel = np.asarray(e_rel, dtype=float)

    if theta_deg.shape != e_rel.shape:
        raise ValueError("theta_deg e e_rel devem ter o mesmo tamanho.")

    level = 1.0 / np.sqrt(2.0)

    mask = theta_deg >= 0.0
    th = theta_deg[mask]
    ee = e_rel[mask]

    idx = np.where(ee < level)[0]
    if len(idx) == 0:
        return np.nan

    i = idx[0]
    if i == 0:
        return np.nan

    x1, x2 = th[i - 1], th[i]
    y1, y2 = ee[i - 1], ee[i]

    if np.isclose(y2, y1):
        return np.nan

    theta_3db = x1 + (level - y1) * (x2 - x1) / (y2 - y1)
    return float(2.0 * theta_3db)


def build_tx_pattern_analytic(
    n_levels: int = 2,
    d_lambda: float = 1.0,
    use_binomial: bool = False,
    beta_tilt_deg: float = 0.0,
    angle_step_deg: float = 0.1,
    target_hpbw_deg: dict | None = None,
):
    """
    Constrói o padrão vertical TX a partir do modelo analítico.

    Retorna um dicionário compatível com o restante do projeto:
    - angle_deg: ângulos de avaliação do padrão, em graus
    - e_rel: padrão de campo normalizado E/Emax

    Também retorna metadados de calibração para uso em relatórios e na UI.
    """
    if target_hpbw_deg is None:
        target_hpbw_deg = TX_VERTICAL_HPBW_TARGET_DEG

    n_levels = int(n_levels)
    if n_levels not in target_hpbw_deg:
        raise ValueError(
            "n_levels deve ser um dos valores da tabela do datasheet: "
            f"{sorted(target_hpbw_deg.keys())}."
        )
    if angle_step_deg <= 0.0:
        raise ValueError("angle_step_deg deve ser positivo.")

    tx_q_element = q_from_single_level_hpbw(float(target_hpbw_deg[1]))
    tx_beta_tilt_rad = np.deg2rad(float(beta_tilt_deg))
    tx_weights_selected = get_tx_weights(n_levels, use_binomial=use_binomial)

    pattern_angle_deg = np.arange(0.0, 90.0 + 0.5 * angle_step_deg, angle_step_deg, dtype=float)
    pattern_e_rel = vertical_pattern_levels(
        pattern_angle_deg,
        n_levels=n_levels,
        d_lambda=float(d_lambda),
        q=tx_q_element,
        beta_rad=tx_beta_tilt_rad,
        weights=tx_weights_selected,
    )
    pattern_e_rel = np.clip(pattern_e_rel, 1e-6, 1.0)

    tx_theta_hpbw_eval_deg = np.linspace(-90.0, 90.0, 20001)
    calibration_report = []
    for ref_n_levels in [1, 2, 4, 6]:
        if ref_n_levels not in target_hpbw_deg:
            continue
        ref_weights = get_tx_weights(ref_n_levels, use_binomial=use_binomial)
        ref_e_rel = vertical_pattern_levels(
            tx_theta_hpbw_eval_deg,
            n_levels=ref_n_levels,
            d_lambda=float(d_lambda),
            q=tx_q_element,
            beta_rad=0.0,
            weights=ref_weights,
        )
        calibration_report.append(
            {
                "n_levels": int(ref_n_levels),
                "hpbw_model_deg": float(hpbw_deg_from_pattern(tx_theta_hpbw_eval_deg, ref_e_rel)),
                "hpbw_target_deg": float(target_hpbw_deg[ref_n_levels]),
            }
        )

    tx_pattern_full_eval = vertical_pattern_levels(
        tx_theta_hpbw_eval_deg,
        n_levels=n_levels,
        d_lambda=float(d_lambda),
        q=tx_q_element,
        beta_rad=tx_beta_tilt_rad,
        weights=tx_weights_selected,
    )

    return {
        "angle_deg": pattern_angle_deg,
        "e_rel": pattern_e_rel,
        "model_name": "analytic_vertical_array",
        "n_levels": int(n_levels),
        "d_lambda": float(d_lambda),
        "use_binomial": bool(use_binomial),
        "beta_tilt_deg": float(beta_tilt_deg),
        "beta_tilt_rad": float(tx_beta_tilt_rad),
        "q_element": float(tx_q_element),
        "weights": np.asarray(tx_weights_selected, dtype=float),
        "target_hpbw_deg": dict(target_hpbw_deg),
        "selected_hpbw_deg": float(hpbw_deg_from_pattern(tx_theta_hpbw_eval_deg, tx_pattern_full_eval)),
        "calibration_report": calibration_report,
    }


# ============================================================
# Perda adicional em baixa elevação
# ============================================================

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
