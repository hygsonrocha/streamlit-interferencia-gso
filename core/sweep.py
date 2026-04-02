import numpy as np
import pandas as pd
from .geometry import geodetic_to_ecef, gso_to_ecef, ecef_to_enu_matrix, unit_vector, angle_between_vectors_deg
from .antenna import ganho_antena_gso_s672, low_elevation_excess_loss_dB
from .budget import W_to_dBW, calcular_banda_sobreposta_hz


DBD_TO_DBI = 2.15


def calcular_i_agg_total_e_in(
    estacoes_expandidas: list[dict],
    params_rx_sat_base: dict,
    tx_pattern: dict,
    gso_lon_deg: float,
    g_r_max_dBi: float,
) -> dict:
    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    t_sys_K = float(params_rx_sat_base["t_sys_K"])
    b_rx_Hz = float(params_rx_sat_base["b_rx_Hz"])
    f_rx_center_MHz = float(params_rx_sat_base.get("f_rx_center_MHz", 300.0))
    l_rx_dB = float(params_rx_sat_base["l_rx_dB"])
    psi_b_deg = float(params_rx_sat_base["psi_b_deg"])
    ln_db = float(params_rx_sat_base["ln_db"])
    lf_db = float(params_rx_sat_base["lf_db"])
    elev_min_deg = float(params_rx_sat_base.get("elev_min_deg", 0.0))
    apply_low_elevation_excess_loss = bool(
        params_rx_sat_base.get("apply_low_elevation_excess_loss", True)
    )

    if elev_min_deg < 0.0:
        raise ValueError("elev_min_deg não pode ser negativo. Use 0° ou maior.")

    i_total_W = 0.0
    n_dBW_ref = -228.6 + 10.0 * np.log10(t_sys_K) + 10.0 * np.log10(b_rx_Hz)
    n_estacoes_visiveis = 0

    r_sat_ecef = gso_to_ecef(gso_lon_deg)

    for estacao in estacoes_expandidas:
        lat_deg = float(estacao["latitude_deg"])
        lon_deg = float(estacao["longitude_deg"])
        f_tx_center_MHz = float(estacao["frequencia_MHz"])
        site_alt_m = float(estacao["site_alt_m"])
        ant_height_m = float(estacao["ant_height_m"])
        p_tx_kW = float(estacao["p_tx_kW"])
        g_t_max_dBd = float(estacao["g_t_max_dBd"])
        tilt_deg = float(estacao["tilt_deg"])
        l_atm_dB = float(estacao["l_atm_dB"])
        l_pol_mismatch_dB = float(estacao["l_pol_mismatch_dB"])
        line_length_m = float(estacao["line_length_m"])
        line_att_dB_per_100m = float(estacao["line_att_dB_per_100m"])
        accessory_losses_dB = float(estacao["accessory_losses_dB"])
        b_tx_Hz = float(estacao["b_tx_Hz"])
        horizontal_discrimination_loss_dB = float(estacao["Eh_dB"])

        h_station_m = site_alt_m + ant_height_m
        l_tx_dB = line_att_dB_per_100m * (line_length_m / 100.0) + accessory_losses_dB
        p_tx_dBW = 10.0 * np.log10(p_tx_kW * 1000.0)

        r_station_ecef = geodetic_to_ecef(lat_deg, lon_deg, h_station_m)
        los_ecef = r_sat_ecef - r_station_ecef
        d_station_sat_km = np.linalg.norm(los_ecef) / 1000.0

        R_ecef2enu = ecef_to_enu_matrix(lat_deg, lon_deg)
        los_enu = R_ecef2enu @ los_ecef
        east, north, up = los_enu

        elev_deg = np.rad2deg(np.arctan2(up, np.hypot(east, north)))
        visible_geom_flag = bool(elev_deg > 0.0)
        visible_flag = bool(visible_geom_flag and (elev_deg >= elev_min_deg))
        if not visible_flag:
            continue

        if apply_low_elevation_excess_loss:
            l_low_elev_excess_dB = float(low_elevation_excess_loss_dB(elev_deg))
            if np.isinf(l_low_elev_excess_dB):
                continue
        else:
            l_low_elev_excess_dB = 0.0

        n_estacoes_visiveis += 1

        # Convenção adotada neste arquivo: tilt_deg é downtilt positivo.
        tx_vertical_offaxis_deg = elev_deg + tilt_deg
        theta_eval_abs_deg = abs(tx_vertical_offaxis_deg)
        theta_eval_used_deg = float(
            np.clip(
                theta_eval_abs_deg,
                float(np.min(angle_deg)),
                float(np.max(angle_deg)),
            )
        )

        ev_rel = float(np.interp(theta_eval_used_deg, angle_deg, e_rel))
        ev_rel = max(ev_rel, 1e-12)
        ev_dB = 20.0 * np.log10(ev_rel)
        g_t_dir_dBd = g_t_max_dBd - horizontal_discrimination_loss_dB + ev_dB
        g_t_dir_dBi = g_t_dir_dBd + DBD_TO_DBI

        u_sat_to_station_ecef = unit_vector(r_station_ecef - r_sat_ecef)
        u_sat_boresight_ecef = unit_vector(-r_sat_ecef)
        psi_rx_deg = angle_between_vectors_deg(u_sat_boresight_ecef, u_sat_to_station_ecef)

        g_r_dir_dBi = ganho_antena_gso_s672(
            psi_deg=psi_rx_deg,
            gmax_dbi=g_r_max_dBi,
            psi_b_deg=psi_b_deg,
            ln_db=ln_db,
            lf_db=lf_db,
        )

        l_fs_dB = 32.45 + 20.0 * np.log10(f_tx_center_MHz) + 20.0 * np.log10(d_station_sat_km)
        l_path_dB = l_fs_dB + l_atm_dB + l_low_elev_excess_dB

        p_ant_dBW = p_tx_dBW - l_tx_dB
        eirp_dir_dBW = p_ant_dBW + g_t_dir_dBi

        b_ov_Hz = calcular_banda_sobreposta_hz(
            f_tx_center_MHz=f_tx_center_MHz,
            b_tx_Hz=b_tx_Hz,
            f_rx_center_MHz=f_rx_center_MHz,
            b_rx_Hz=b_rx_Hz,
        )
        if b_ov_Hz <= 0.0:
            continue

        eirp_density_dBW_per_Hz = eirp_dir_dBW - 10.0 * np.log10(b_tx_Hz)

        i_density_dBW_per_Hz = (
            eirp_density_dBW_per_Hz
            - l_path_dB
            + g_r_dir_dBi
            - l_pol_mismatch_dB
            - l_rx_dB
        )

        i_dBW = i_density_dBW_per_Hz + 10.0 * np.log10(b_ov_Hz)

        i_total_W += 10.0 ** (i_dBW / 10.0)

    if n_estacoes_visiveis == 0:
        return {
            "n_estacoes_visiveis": 0,
            "i_agg_total_dBW": -np.inf,
            "i_over_n_agg_total_dB": np.nan,
        }

    i_agg_total_dBW = W_to_dBW(i_total_W)
    i_over_n_agg_total_dB = i_agg_total_dBW - n_dBW_ref

    return {
        "n_estacoes_visiveis": n_estacoes_visiveis,
        "i_agg_total_dBW": i_agg_total_dBW,
        "i_over_n_agg_total_dB": i_over_n_agg_total_dB,
    }



def build_longitude_grid(lon_min_deg: float, lon_max_deg: float, lon_step_deg: float) -> np.ndarray:
    if lon_step_deg <= 0:
        raise ValueError("lon_step_deg deve ser positivo.")
    if lon_max_deg < lon_min_deg:
        raise ValueError("lon_max_deg deve ser maior ou igual a lon_min_deg.")

    grid = np.arange(lon_min_deg, lon_max_deg + 0.5 * lon_step_deg, lon_step_deg, dtype=float)
    return np.round(grid, 10)



def extrair_faixas_contiguas(df: pd.DataFrame, lon_step_deg: float) -> pd.DataFrame:
    linhas = []

    for g_r, grupo in df.groupby("g_r_max_dBi", sort=True):
        grupo = grupo.sort_values("gso_lon_deg").reset_index(drop=True)
        grupo_ok = grupo[grupo["atende_criterio"]].copy().reset_index(drop=True)

        if grupo_ok.empty:
            linhas.append(
                {
                    "g_r_max_dBi": float(g_r),
                    "lon_ini_deg": np.nan,
                    "lon_fim_deg": np.nan,
                    "n_pontos": 0,
                    "largura_deg_amostrada": np.nan,
                    "i_over_n_min_dB_na_faixa": np.nan,
                    "i_over_n_max_dB_na_faixa": np.nan,
                    "benchmark_i_over_n_dB": float(grupo["benchmark_i_over_n_dB"].iloc[0]),
                    "lon_step_deg": float(lon_step_deg),
                    "observacao": "Nenhuma longitude atendeu ao critério.",
                }
            )
            continue

        idx_ini = 0
        for i in range(1, len(grupo_ok) + 1):
            fim_bloco = False

            if i == len(grupo_ok):
                fim_bloco = True
            else:
                lon_atual = float(grupo_ok.loc[i - 1, "gso_lon_deg"])
                lon_prox = float(grupo_ok.loc[i, "gso_lon_deg"])
                if not np.isclose(lon_prox - lon_atual, lon_step_deg, atol=1e-9):
                    fim_bloco = True

            if fim_bloco:
                bloco = grupo_ok.iloc[idx_ini:i].copy()
                lon_ini = float(bloco["gso_lon_deg"].iloc[0])
                lon_fim = float(bloco["gso_lon_deg"].iloc[-1])

                linhas.append(
                    {
                        "g_r_max_dBi": float(g_r),
                        "lon_ini_deg": lon_ini,
                        "lon_fim_deg": lon_fim,
                        "n_pontos": int(len(bloco)),
                        "largura_deg_amostrada": float(lon_fim - lon_ini),
                        "i_over_n_min_dB_na_faixa": float(bloco["i_over_n_agg_total_dB"].min()),
                        "i_over_n_max_dB_na_faixa": float(bloco["i_over_n_agg_total_dB"].max()),
                        "benchmark_i_over_n_dB": float(bloco["benchmark_i_over_n_dB"].iloc[0]),
                        "lon_step_deg": float(lon_step_deg),
                        "observacao": "Faixa contígua amostrada que atende ao critério.",
                    }
                )
                idx_ini = i

    return pd.DataFrame(linhas)
