import numpy as np
from .geometry import geodetic_to_ecef, gso_to_ecef, ecef_to_enu_matrix, unit_vector, angle_between_vectors_deg
from .antenna import ganho_antena_gso_s672, low_elevation_excess_loss_dB


def dBW_to_W(p_dbw: float) -> float:
    return 10.0 ** (p_dbw / 10.0)


def W_to_dBW(p_w: float) -> float:
    if p_w <= 0.0:
        return -np.inf
    return 10.0 * np.log10(p_w)


def expandir_estacoes_com_defaults(estacoes: list[dict], params_tx_default: dict) -> list[dict]:
    return [{**params_tx_default, **estacao} for estacao in estacoes]


def validar_estacoes(estacoes: list[dict]) -> None:
    campos_obrigatorios = {"municipio", "uf", "latitude_deg", "longitude_deg", "frequencia_MHz"}
    for i, estacao in enumerate(estacoes, start=1):
        faltando = campos_obrigatorios - set(estacao.keys())
        if faltando:
            raise ValueError(f"Estação #{i} sem campos obrigatórios: {sorted(faltando)}")


def validar_tx_pattern(tx_pattern: dict) -> None:
    if "angle_deg" not in tx_pattern or "e_rel" not in tx_pattern:
        raise ValueError("tx_pattern deve conter 'angle_deg' e 'e_rel'.")
    if len(tx_pattern["angle_deg"]) != len(tx_pattern["e_rel"]):
        raise ValueError("tx_pattern['angle_deg'] e tx_pattern['e_rel'] devem ter o mesmo tamanho.")


def calcular_interferencia_estacao(estacao: dict, params_rx_sat: dict, tx_pattern: dict) -> dict:
    municipio = estacao["municipio"]
    uf = estacao["uf"]
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
    pol_tx = estacao["pol_tx"]
    b_tx_Hz = float(estacao["b_tx_Hz"])
    eh_dB = float(estacao["Eh_dB"])

    sat_id = params_rx_sat["sat_id"]
    gso_lon_deg = float(params_rx_sat["gso_lon_deg"])
    pol_rx = params_rx_sat["pol_rx"]
    t_sys_K = float(params_rx_sat["t_sys_K"])
    l_rx_dB = float(params_rx_sat["l_rx_dB"])
    g_r_max_dBi = float(params_rx_sat["g_r_max_dBi"])
    psi_b_deg = float(params_rx_sat["psi_b_deg"])
    ln_db = float(params_rx_sat["ln_db"])
    lf_db = float(params_rx_sat["lf_db"])
    benchmark_i_over_n_dB = float(params_rx_sat["benchmark_i_over_n_dB"])
    elev_min_deg = float(params_rx_sat.get("elev_min_deg", 0.0))
    apply_low_elevation_excess_loss = bool(params_rx_sat.get("apply_low_elevation_excess_loss", True))

    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    h_station_m = site_alt_m + ant_height_m
    l_tx_dB = line_att_dB_per_100m * (line_length_m / 100.0) + accessory_losses_dB
    p_tx_dBW = 10.0 * np.log10(p_tx_kW * 1000.0)
    g_t_max_dBi = g_t_max_dBd + 2.15
    erp_max_kW = p_tx_kW * 10.0 ** ((g_t_max_dBd - l_tx_dB) / 10.0)

    tx_f_min_MHz = f_tx_center_MHz - (b_tx_Hz / 1e6) / 2.0
    tx_f_max_MHz = f_tx_center_MHz + (b_tx_Hz / 1e6) / 2.0

    r_station_ecef = geodetic_to_ecef(lat_deg, lon_deg, h_station_m)
    r_sat_ecef = gso_to_ecef(gso_lon_deg)
    los_ecef = r_sat_ecef - r_station_ecef
    d_station_sat_km = np.linalg.norm(los_ecef) / 1000.0

    R_ecef2enu = ecef_to_enu_matrix(lat_deg, lon_deg)
    los_enu = R_ecef2enu @ los_ecef
    east, north, up = los_enu

    az_to_sat_deg = (np.rad2deg(np.arctan2(east, north)) + 360.0) % 360.0
    elev_deg = np.rad2deg(np.arctan2(up, np.hypot(east, north)))

    tx_vertical_offaxis_deg = elev_deg - tilt_deg

    u_sat_to_station_ecef = unit_vector(r_station_ecef - r_sat_ecef)
    u_sat_boresight_ecef = unit_vector(-r_sat_ecef)

    gso_rx_boresight_offaxis_deg = angle_between_vectors_deg(u_sat_boresight_ecef, u_sat_to_station_ecef)

    visible_geom_flag = bool(elev_deg > 0.0)
    visible_flag = bool(elev_deg >= elev_min_deg)

    theta_eval_deg = tx_vertical_offaxis_deg
    theta_eval_abs_deg = abs(theta_eval_deg)

    theta_pattern_min_deg = float(np.min(angle_deg))
    theta_pattern_max_deg = float(np.max(angle_deg))

    pattern_clipped_flag = bool((theta_eval_abs_deg < theta_pattern_min_deg) or (theta_eval_abs_deg > theta_pattern_max_deg))

    theta_eval_used_deg = float(np.clip(theta_eval_abs_deg, theta_pattern_min_deg, theta_pattern_max_deg))

    ev_rel = float(np.interp(theta_eval_used_deg, angle_deg, e_rel))
    ev_rel = max(ev_rel, 1e-12)
    ev_dB = 20.0 * np.log10(ev_rel)

    gt_dir_dBi = g_t_max_dBi + eh_dB + ev_dB

    g_r_dir_dBi = ganho_antena_gso_s672(psi_deg=gso_rx_boresight_offaxis_deg, gmax_dbi=g_r_max_dBi, psi_b_deg=psi_b_deg, ln_db=ln_db, lf_db=lf_db)
    g_r_dir_offset_dB = g_r_max_dBi - g_r_dir_dBi

    p_ant_dBW = p_tx_dBW - l_tx_dB
    n_dBW = -228.6 + 10.0 * np.log10(t_sys_K) + 10.0 * np.log10(b_tx_Hz)

    if visible_flag:
        l_fs_dB = 32.45 + 20.0 * np.log10(f_tx_center_MHz) + 20.0 * np.log10(d_station_sat_km)

        if apply_low_elevation_excess_loss:
            l_low_elev_excess_dB = float(low_elevation_excess_loss_dB(elev_deg))
        else:
            l_low_elev_excess_dB = 0.0

        if np.isinf(l_low_elev_excess_dB):
            l_path_dB = np.nan
            eirp_dir_dBW = np.nan
            i_dBW = np.nan
            i_W = 0.0
            i_over_n_dB = np.nan
            delta_t_over_t_pct = np.nan
            benchmark_ok = False
            visible_flag = False
            visibility_reason = "Descartada pela perda infinita do modelo de baixa elevação."
        else:
            l_path_dB = l_fs_dB + l_atm_dB + l_low_elev_excess_dB
            eirp_dir_dBW = p_ant_dBW + gt_dir_dBi
            i_dBW = eirp_dir_dBW - l_path_dB + g_r_dir_dBi - l_pol_mismatch_dB - l_rx_dB
            i_W = dBW_to_W(i_dBW)
            i_over_n_dB = i_dBW - n_dBW
            delta_t_over_t_pct = 100.0 * (10.0 ** (i_over_n_dB / 10.0))
            benchmark_ok = bool(i_over_n_dB <= benchmark_i_over_n_dB)
            visibility_reason = "Considerada no estudo."
    else:
        l_fs_dB = np.nan
        l_low_elev_excess_dB = np.nan
        l_path_dB = np.nan
        eirp_dir_dBW = np.nan
        i_dBW = np.nan
        i_W = 0.0
        i_over_n_dB = np.nan
        delta_t_over_t_pct = np.nan
        benchmark_ok = False

        if visible_geom_flag and elev_deg < elev_min_deg:
            visibility_reason = f"Geometricamente visível, mas abaixo de elev_min_deg = {elev_min_deg:.2f}°."
        else:
            visibility_reason = "Satélite abaixo do horizonte geométrico."

    return {
        "municipio": municipio,
        "uf": uf,
        "latitude_deg": lat_deg,
        "longitude_deg": lon_deg,
        "frequencia_MHz": f_tx_center_MHz,
        "site_alt_m": site_alt_m,
        "ant_height_m": ant_height_m,
        "h_station_m": h_station_m,
        "p_tx_kW": p_tx_kW,
        "g_t_max_dBd": g_t_max_dBd,
        "g_t_max_dBi": g_t_max_dBi,
        "tilt_deg": tilt_deg,
        "l_atm_dB": l_atm_dB,
        "l_pol_mismatch_dB": l_pol_mismatch_dB,
        "line_length_m": line_length_m,
        "line_att_dB_per_100m": line_att_dB_per_100m,
        "accessory_losses_dB": accessory_losses_dB,
        "l_tx_dB": l_tx_dB,
        "pol_tx": pol_tx,
        "b_tx_Hz": b_tx_Hz,
        "Eh_dB": eh_dB,
        "p_tx_dBW": p_tx_dBW,
        "p_ant_dBW": p_ant_dBW,
        "erp_max_kW": erp_max_kW,
        "tx_f_min_MHz": tx_f_min_MHz,
        "tx_f_max_MHz": tx_f_max_MHz,
        "sat_id": sat_id,
        "gso_lon_deg": gso_lon_deg,
        "pol_rx": pol_rx,
        "t_sys_K": t_sys_K,
        "l_rx_dB": l_rx_dB,
        "g_r_max_dBi": g_r_max_dBi,
        "psi_b_deg": psi_b_deg,
        "ln_db": ln_db,
        "lf_db": lf_db,
        "benchmark_i_over_n_dB": benchmark_i_over_n_dB,
        "elev_min_deg": elev_min_deg,
        "apply_low_elevation_excess_loss": apply_low_elevation_excess_loss,
        "r_station_ecef_x_m": r_station_ecef[0],
        "r_station_ecef_y_m": r_station_ecef[1],
        "r_station_ecef_z_m": r_station_ecef[2],
        "r_sat_ecef_x_m": r_sat_ecef[0],
        "r_sat_ecef_y_m": r_sat_ecef[1],
        "r_sat_ecef_z_m": r_sat_ecef[2],
        "d_station_sat_km": d_station_sat_km,
        "az_to_sat_deg": az_to_sat_deg,
        "elev_deg": elev_deg,
        "tx_vertical_offaxis_deg": tx_vertical_offaxis_deg,
        "theta_eval_deg": theta_eval_deg,
        "theta_eval_abs_deg": theta_eval_abs_deg,
        "theta_eval_used_deg": theta_eval_used_deg,
        "pattern_clipped_flag": pattern_clipped_flag,
        "Ev_rel": ev_rel,
        "Ev_dB": ev_dB,
        "g_t_dir_dBi": gt_dir_dBi,
        "gso_rx_boresight_offaxis_deg": gso_rx_boresight_offaxis_deg,
        "g_r_dir_dBi": g_r_dir_dBi,
        "g_r_dir_offset_dB": g_r_dir_offset_dB,
        "visible_geom_flag": visible_geom_flag,
        "visible_flag": visible_flag,
        "visibility_reason": visibility_reason,
        "l_fs_dB": l_fs_dB,
        "l_low_elev_excess_dB": l_low_elev_excess_dB,
        "l_path_dB": l_path_dB,
        "eirp_dir_dBW": eirp_dir_dBW,
        "i_dBW": i_dBW,
        "i_W": i_W,
        "n_dBW": n_dBW,
        "i_over_n_dB": i_over_n_dB,
        "delta_t_over_t_pct": delta_t_over_t_pct,
        "benchmark_ok": benchmark_ok,
    }
