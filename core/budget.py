import numpy as np
from .geometry import geodetic_to_ecef, gso_to_ecef, ecef_to_enu_matrix, unit_vector, angle_between_vectors_deg
from .antenna import ganho_antena_gso_s672, low_elevation_excess_loss_dB, resolve_psi_b_deg


DBD_TO_DBI = 2.15


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

    if not estacoes:
        raise ValueError("A lista de estações está vazia.")

    for i, estacao in enumerate(estacoes, start=1):
        faltando = campos_obrigatorios - set(estacao.keys())
        if faltando:
            raise ValueError(f"Estação #{i} sem campos obrigatórios: {sorted(faltando)}")

        municipio = str(estacao["municipio"]).strip()
        uf = str(estacao["uf"]).strip()

        if not municipio:
            raise ValueError(f"Estação #{i} com 'municipio' vazio.")
        if not uf:
            raise ValueError(f"Estação #{i} com 'uf' vazio.")

        try:
            lat = float(estacao["latitude_deg"])
            lon = float(estacao["longitude_deg"])
            freq = float(estacao["frequencia_MHz"])
        except Exception as e:
            raise ValueError(f"Estação #{i} contém latitude/longitude/frequência inválidas: {e}")

        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Estação #{i} com latitude fora do intervalo [-90, 90].")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Estação #{i} com longitude fora do intervalo [-180, 180].")
        if freq <= 0.0:
            raise ValueError(f"Estação #{i} com frequência não positiva.")



def validar_tx_pattern(tx_pattern: dict) -> None:
    if "angle_deg" not in tx_pattern or "e_rel" not in tx_pattern:
        raise ValueError("tx_pattern deve conter 'angle_deg' e 'e_rel'.")

    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    if len(angle_deg) != len(e_rel):
        raise ValueError("tx_pattern['angle_deg'] e tx_pattern['e_rel'] devem ter o mesmo tamanho.")
    if len(angle_deg) == 0:
        raise ValueError("tx_pattern não pode ser vazio.")
    if np.any(np.diff(angle_deg) < 0):
        raise ValueError("'angle_deg' deve estar em ordem crescente.")
    if np.any(e_rel <= 0):
        raise ValueError("'e_rel' deve conter apenas valores positivos.")


def resolver_metricas_tx_estacao(estacao: dict) -> dict:
    tx_input_mode = str(estacao.get("tx_input_mode", "potencia_tx")).strip().lower()

    g_t_max_dBd = float(estacao["g_t_max_dBd"])
    line_length_m = float(estacao.get("line_length_m", 0.0))
    line_att_dB_per_100m = float(estacao.get("line_att_dB_per_100m", 0.0))
    accessory_losses_dB = float(estacao.get("accessory_losses_dB", 0.0))
    l_tx_dB = line_att_dB_per_100m * (line_length_m / 100.0) + accessory_losses_dB

    if tx_input_mode == "erp_max_direta":
        erp_max_input_kW = float(estacao["erp_max_input_kW"])
        if erp_max_input_kW <= 0.0:
            raise ValueError("erp_max_input_kW deve ser positivo.")

        erp_max_dBW = 10.0 * np.log10(erp_max_input_kW * 1000.0)
        p_ant_dBW = erp_max_dBW - g_t_max_dBd
        p_tx_dBW = p_ant_dBW + l_tx_dB
        p_tx_kW = dBW_to_W(p_tx_dBW) / 1000.0
        erp_max_kW = erp_max_input_kW
    elif tx_input_mode == "potencia_tx":
        p_tx_kW = float(estacao["p_tx_kW"])
        if p_tx_kW <= 0.0:
            raise ValueError("p_tx_kW deve ser positivo.")

        p_tx_dBW = 10.0 * np.log10(p_tx_kW * 1000.0)
        p_ant_dBW = p_tx_dBW - l_tx_dB
        erp_max_dBW = p_ant_dBW + g_t_max_dBd
        erp_max_kW = dBW_to_W(erp_max_dBW) / 1000.0
    else:
        raise ValueError("tx_input_mode inválido. Use 'potencia_tx' ou 'erp_max_direta'.")

    return {
        "tx_input_mode": tx_input_mode,
        "l_tx_dB": l_tx_dB,
        "p_tx_kW": p_tx_kW,
        "erp_max_input_kW": float(estacao.get("erp_max_input_kW", erp_max_kW)),
        "p_tx_dBW": p_tx_dBW,
        "p_ant_dBW": p_ant_dBW,
        "erp_max_dBW": erp_max_dBW,
        "erp_max_kW": erp_max_kW,
    }



def calcular_metricas_estacao_modelo(params_tx: dict) -> dict:
    return resolver_metricas_tx_estacao(params_tx)



def calcular_banda_sobreposta_hz(
    f_tx_center_MHz: float,
    b_tx_Hz: float,
    f_rx_center_MHz: float,
    b_rx_Hz: float,
) -> float:
    if b_tx_Hz <= 0.0 or b_rx_Hz <= 0.0:
        raise ValueError("b_tx_Hz e b_rx_Hz devem ser positivos.")

    tx_half_bw_MHz = (b_tx_Hz / 1e6) / 2.0
    rx_half_bw_MHz = (b_rx_Hz / 1e6) / 2.0

    tx_f_min_MHz = f_tx_center_MHz - tx_half_bw_MHz
    tx_f_max_MHz = f_tx_center_MHz + tx_half_bw_MHz
    rx_f_min_MHz = f_rx_center_MHz - rx_half_bw_MHz
    rx_f_max_MHz = f_rx_center_MHz + rx_half_bw_MHz

    overlap_MHz = min(tx_f_max_MHz, rx_f_max_MHz) - max(tx_f_min_MHz, rx_f_min_MHz)
    return max(0.0, overlap_MHz * 1e6)



def calcular_interferencia_estacao(estacao: dict, params_rx_sat: dict, tx_pattern: dict) -> dict:
    municipio = estacao["municipio"]
    uf = estacao["uf"]
    lat_deg = float(estacao["latitude_deg"])
    lon_deg = float(estacao["longitude_deg"])

    f_tx_center_MHz = float(estacao["frequencia_MHz"])
    site_alt_m = float(estacao["site_alt_m"])
    ant_height_m = float(estacao["ant_height_m"])
    tx_metricas = resolver_metricas_tx_estacao(estacao)
    p_tx_kW = float(tx_metricas["p_tx_kW"])
    g_t_max_dBd = float(estacao["g_t_max_dBd"])
    tilt_deg = float(estacao["tilt_deg"])
    l_atm_dB = float(estacao["l_atm_dB"])
    l_pol_mismatch_dB = float(estacao["l_pol_mismatch_dB"])

    line_length_m = float(estacao["line_length_m"])
    line_att_dB_per_100m = float(estacao["line_att_dB_per_100m"])
    accessory_losses_dB = float(estacao["accessory_losses_dB"])
    pol_tx = estacao["pol_tx"]
    b_tx_Hz = float(estacao["b_tx_Hz"])
    horizontal_discrimination_loss_dB = float(estacao["Eh_dB"])

    sat_id = params_rx_sat["sat_id"]
    gso_lon_deg = float(params_rx_sat["gso_lon_deg"])
    pol_rx = params_rx_sat["pol_rx"]
    t_sys_K = float(params_rx_sat["t_sys_K"])
    b_rx_Hz = float(params_rx_sat["b_rx_Hz"])
    f_rx_center_MHz = float(params_rx_sat.get("f_rx_center_MHz", f_tx_center_MHz))
    l_rx_dB = float(params_rx_sat["l_rx_dB"])
    g_r_max_dBi = float(params_rx_sat["g_r_max_dBi"])
    eta_ap = float(params_rx_sat.get("eta_ap", 0.60))
    psi_b_deg = resolve_psi_b_deg(
        gmax_dbi=float(params_rx_sat["g_r_max_dBi"]),
        psi_b_deg=params_rx_sat.get("psi_b_deg"),
        eta_ap=eta_ap,
    )
    ln_db = float(params_rx_sat["ln_db"])
    lf_db = float(params_rx_sat["lf_db"])
    single_entry_limit_i_over_n_dB = float(
        params_rx_sat.get("single_entry_limit_i_over_n_dB", params_rx_sat["benchmark_i_over_n_dB"])
    )
    elev_min_deg = float(params_rx_sat.get("elev_min_deg", 0.0))
    apply_low_elevation_excess_loss = bool(params_rx_sat.get("apply_low_elevation_excess_loss", True))

    if b_tx_Hz <= 0.0:
        raise ValueError("b_tx_Hz deve ser positivo.")
    if b_rx_Hz <= 0.0:
        raise ValueError("b_rx_Hz deve ser positivo.")
    if t_sys_K <= 0.0:
        raise ValueError("t_sys_K deve ser positivo.")
    if elev_min_deg < 0.0:
        raise ValueError("elev_min_deg não pode ser negativo. Use 0° ou maior.")

    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    h_station_m = site_alt_m + ant_height_m

    l_tx_dB = float(tx_metricas["l_tx_dB"])
    p_tx_dBW = float(tx_metricas["p_tx_dBW"])
    p_ant_dBW = float(tx_metricas["p_ant_dBW"])
    erp_max_dBW = float(tx_metricas["erp_max_dBW"])
    erp_max_kW = float(tx_metricas["erp_max_kW"])

    tx_f_min_MHz = f_tx_center_MHz - (b_tx_Hz / 1e6) / 2.0
    tx_f_max_MHz = f_tx_center_MHz + (b_tx_Hz / 1e6) / 2.0
    rx_f_min_MHz = f_rx_center_MHz - (b_rx_Hz / 1e6) / 2.0
    rx_f_max_MHz = f_rx_center_MHz + (b_rx_Hz / 1e6) / 2.0

    r_station_ecef = geodetic_to_ecef(lat_deg, lon_deg, h_station_m)
    r_sat_ecef = gso_to_ecef(gso_lon_deg)
    los_ecef = r_sat_ecef - r_station_ecef
    d_station_sat_km = np.linalg.norm(los_ecef) / 1000.0

    if d_station_sat_km <= 0.0:
        raise ValueError("A distância estação-satélite deve ser positiva.")

    R_ecef2enu = ecef_to_enu_matrix(lat_deg, lon_deg)
    los_enu = R_ecef2enu @ los_ecef
    east, north, up = los_enu

    az_to_sat_deg = (np.rad2deg(np.arctan2(east, north)) + 360.0) % 360.0
    elev_deg = np.rad2deg(np.arctan2(up, np.hypot(east, north)))

    # Convenção adotada neste arquivo: tilt_deg é downtilt positivo.
    tx_vertical_offaxis_deg = elev_deg + tilt_deg

    u_sat_to_station_ecef = unit_vector(r_station_ecef - r_sat_ecef)
    u_sat_boresight_ecef = unit_vector(-r_sat_ecef)
    gso_rx_boresight_offaxis_deg = angle_between_vectors_deg(u_sat_boresight_ecef, u_sat_to_station_ecef)

    visible_geom_flag = bool(elev_deg > 0.0)
    visible_flag = bool(visible_geom_flag and (elev_deg >= elev_min_deg))

    theta_eval_deg = tx_vertical_offaxis_deg
    theta_eval_abs_deg = abs(theta_eval_deg)

    theta_pattern_min_deg = float(np.min(angle_deg))
    theta_pattern_max_deg = float(np.max(angle_deg))

    pattern_clipped_flag = bool((theta_eval_abs_deg < theta_pattern_min_deg) or (theta_eval_abs_deg > theta_pattern_max_deg))
    theta_eval_used_deg = float(np.clip(theta_eval_abs_deg, theta_pattern_min_deg, theta_pattern_max_deg))

    ev_rel = float(np.interp(theta_eval_used_deg, angle_deg, e_rel))
    ev_rel = max(ev_rel, 1e-12)
    ev_dB = 20.0 * np.log10(ev_rel)

    # O ganho direcional é formado em dBd e então convertido para dBi.
    g_t_dir_dBd = g_t_max_dBd - horizontal_discrimination_loss_dB + ev_dB
    g_t_dir_dBi = g_t_dir_dBd + DBD_TO_DBI
    g_t_max_dBi = g_t_max_dBd + DBD_TO_DBI

    g_r_dir_dBi = ganho_antena_gso_s672(
        psi_deg=gso_rx_boresight_offaxis_deg,
        gmax_dbi=g_r_max_dBi,
        psi_b_deg=psi_b_deg,
        eta_ap=eta_ap,
        ln_db=ln_db,
        lf_db=lf_db,
    )
    g_r_dir_offset_dB = g_r_max_dBi - g_r_dir_dBi

    eirp_dir_dBW = p_ant_dBW + g_t_dir_dBi
    erp_dir_dBW = p_ant_dBW + g_t_dir_dBd
    erp_dir_kW = dBW_to_W(erp_dir_dBW) / 1000.0

    b_ov_Hz = calcular_banda_sobreposta_hz(
        f_tx_center_MHz=f_tx_center_MHz,
        b_tx_Hz=b_tx_Hz,
        f_rx_center_MHz=f_rx_center_MHz,
        b_rx_Hz=b_rx_Hz,
    )
    spectral_overlap_flag = bool(b_ov_Hz > 0.0)

    n0_dBW_per_Hz = -228.6 + 10.0 * np.log10(t_sys_K)
    n_dBW = n0_dBW_per_Hz + 10.0 * np.log10(b_rx_Hz)

    if visible_flag:
        l_fs_dB = 32.45 + 20.0 * np.log10(f_tx_center_MHz) + 20.0 * np.log10(d_station_sat_km)

        if apply_low_elevation_excess_loss:
            l_low_elev_excess_dB = float(low_elevation_excess_loss_dB(elev_deg))
        else:
            l_low_elev_excess_dB = 0.0

        if np.isinf(l_low_elev_excess_dB):
            l_path_dB = np.nan
            eirp_density_dBW_per_Hz = np.nan
            i_density_dBW_per_Hz = np.nan
            i_dBW = np.nan
            i_W = 0.0
            i_over_n_dB = np.nan
            i0_over_n0_dB = np.nan
            delta_t_over_t_pct = np.nan
            benchmark_ok = False
            visible_flag = False
            visibility_reason = "Descartada pela perda infinita do modelo de baixa elevação."
        else:
            l_path_dB = l_fs_dB + l_atm_dB + l_low_elev_excess_dB
            eirp_density_dBW_per_Hz = eirp_dir_dBW - 10.0 * np.log10(b_tx_Hz)

            if spectral_overlap_flag:
                i_density_dBW_per_Hz = (
                    eirp_density_dBW_per_Hz
                    - l_path_dB
                    + g_r_dir_dBi
                    - l_pol_mismatch_dB
                    - l_rx_dB
                )
                i_dBW = i_density_dBW_per_Hz + 10.0 * np.log10(b_ov_Hz)
                i_W = dBW_to_W(i_dBW)
                i_over_n_dB = i_dBW - n_dBW
                i0_over_n0_dB = i_density_dBW_per_Hz - n0_dBW_per_Hz
                delta_t_over_t_pct = 100.0 * (10.0 ** (i_over_n_dB / 10.0))
                benchmark_ok = bool(i_over_n_dB <= single_entry_limit_i_over_n_dB)
                visibility_reason = "Considerada no estudo."
            else:
                i_density_dBW_per_Hz = np.nan
                i_dBW = -np.inf
                i_W = 0.0
                i_over_n_dB = -np.inf
                i0_over_n0_dB = np.nan
                delta_t_over_t_pct = 0.0
                benchmark_ok = True
                visibility_reason = "Geometricamente visível, mas sem sobreposição espectral com o receptor."
    else:
        l_fs_dB = np.nan
        l_low_elev_excess_dB = np.nan
        l_path_dB = np.nan
        eirp_density_dBW_per_Hz = np.nan
        i_density_dBW_per_Hz = np.nan
        i_dBW = np.nan
        i_W = 0.0
        i_over_n_dB = np.nan
        i0_over_n0_dB = np.nan
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
        "b_rx_Hz": b_rx_Hz,
        "b_ov_Hz": b_ov_Hz,
        "Eh_dB": horizontal_discrimination_loss_dB,
        "horizontal_discrimination_loss_dB": horizontal_discrimination_loss_dB,
        "p_tx_dBW": p_tx_dBW,
        "p_ant_dBW": p_ant_dBW,
        "erp_max_dBW": erp_max_dBW,
        "erp_max_kW": erp_max_kW,
        "tx_f_min_MHz": tx_f_min_MHz,
        "tx_f_max_MHz": tx_f_max_MHz,
        "f_rx_center_MHz": f_rx_center_MHz,
        "rx_f_min_MHz": rx_f_min_MHz,
        "rx_f_max_MHz": rx_f_max_MHz,
        "sat_id": sat_id,
        "gso_lon_deg": gso_lon_deg,
        "pol_rx": pol_rx,
        "t_sys_K": t_sys_K,
        "l_rx_dB": l_rx_dB,
        "g_r_max_dBi": g_r_max_dBi,
        "eta_ap": eta_ap,
        "psi_b_deg": psi_b_deg,
        "ln_db": ln_db,
        "lf_db": lf_db,
        "single_entry_limit_i_over_n_dB": single_entry_limit_i_over_n_dB,
        "benchmark_i_over_n_dB": single_entry_limit_i_over_n_dB,
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
        "g_t_dir_dBi": g_t_dir_dBi,
        "g_t_dir_dBd": g_t_dir_dBd,
        "gso_rx_boresight_offaxis_deg": gso_rx_boresight_offaxis_deg,
        "g_r_dir_dBi": g_r_dir_dBi,
        "g_r_dir_offset_dB": g_r_dir_offset_dB,
        "visible_geom_flag": visible_geom_flag,
        "visible_flag": visible_flag,
        "spectral_overlap_flag": spectral_overlap_flag,
        "visibility_reason": visibility_reason,
        "l_fs_dB": l_fs_dB,
        "l_low_elev_excess_dB": l_low_elev_excess_dB,
        "l_path_dB": l_path_dB,
        "eirp_dir_dBW": eirp_dir_dBW,
        "eirp_density_dBW_per_Hz": eirp_density_dBW_per_Hz,
        "erp_dir_dBW": erp_dir_dBW,
        "erp_dir_kW": erp_dir_kW,
        "n0_dBW_per_Hz": n0_dBW_per_Hz,
        "i_density_dBW_per_Hz": i_density_dBW_per_Hz,
        "i_dBW": i_dBW,
        "i_W": i_W,
        "n_dBW": n_dBW,
        "i_over_n_dB": i_over_n_dB,
        "i0_over_n0_dB": i0_over_n0_dB,
        "i_over_n0_dBHz": i0_over_n0_dB,
        "delta_t_over_t_pct": delta_t_over_t_pct,
        "benchmark_ok": benchmark_ok,
    }
