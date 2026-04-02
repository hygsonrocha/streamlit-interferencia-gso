import numpy as np

params_tx_default = {
    "site_alt_m": 1140.9,
    "ant_height_m": 159.0,
    "p_tx_kW": 16.0,
    "g_t_max_dBd": 5.1,
    "tilt_deg": 0.0,
    "l_atm_dB": 0.0,
    "l_pol_mismatch_dB": 3.0,
    "line_length_m": 200.0,
    "line_att_dB_per_100m": 0.93,
    "accessory_losses_dB": 2.0,
    "pol_tx": "horizontal",
    "b_tx_Hz": 6_000_000.0,
    "Eh_dB": 0.0,
}

params_rx_sat = {
    "sat_id": "SECOMSAT-5-30W",
    "gso_lon_deg": -30.0,
    "pol_rx": "M",
    "t_sys_K": 700.0,
    "f_rx_center_MHz": 300.0,
    "b_rx_Hz": 6_000_000.0,
    "l_rx_dB": 0.0,
    "g_r_max_dBi": 23.0,
    "psi_b_deg": 1.1,
    "ln_db": -20.0,
    "lf_db": 0.0,
    "benchmark_i_over_n_dB": -12.2,
    "elev_min_deg": 0.0,
    "apply_low_elevation_excess_loss": True,
}


def build_tx_pattern_bt1195_fig19():
    """
    Padrão vertical proxy em alta resolução, compatível com a Figura 19 da Rec. ITU-R BT.1195-1.

    Observações:
    - os pontos de controle abaixo foram ajustados para reproduzir visualmente o formato da figura;
    - o padrão é normalizado em campo: E/Emax;
    - a malha final é densa (0,1°), para deixar o gráfico do app suave.
    """

    ctrl_angle_deg = np.array([
         0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,
        11,  12,  13,  14,  15,  16,  17,  18,  19,  20,
        21,  22,  23,  24,  25,  26,  27,  28,  29,  30,
        31,  32,  33,  34,  35,  36,  37,  38,  39,  40,
        42,  44,  46,  48,  50,  52,  55,  60,  65,  70,  75,  80,  85,  90
    ], dtype=float)

    ctrl_e_rel = np.array([
        1.00, 0.995, 0.985, 0.970, 0.950, 0.920, 0.880, 0.830, 0.770, 0.700, 0.620,
        0.540, 0.460, 0.380, 0.300, 0.220, 0.150, 0.090, 0.040, 0.030, 0.050,
        0.090, 0.140, 0.180, 0.195, 0.200, 0.195, 0.185, 0.165, 0.130, 0.090,
        0.040, 0.030, 0.070, 0.130, 0.180, 0.198, 0.200, 0.188, 0.165, 0.140,
        0.090, 0.045, 0.030, 0.055, 0.080, 0.100, 0.105, 0.090, 0.070, 0.050, 0.035, 0.025, 0.020, 0.018
    ], dtype=float)

    angle_deg = np.arange(0.0, 90.0 + 0.1, 0.1, dtype=float)
    e_rel = np.interp(angle_deg, ctrl_angle_deg, ctrl_e_rel)
    e_rel = np.clip(e_rel, 1e-6, 1.0)

    return {
        "angle_deg": angle_deg,
        "e_rel": e_rel,
    }



tx_pattern = build_tx_pattern_bt1195_fig19()

FREQ_INTERF_MHZ = 300.0

estacoes_exemplo = [
    {"municipio": "Florianópolis", "uf": "SC", "latitude_deg": -27.590000, "longitude_deg": -48.534167, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Curitiba", "uf": "PR", "latitude_deg": -25.399722, "longitude_deg": -49.287778, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Manaus", "uf": "AM", "latitude_deg": -3.119167, "longitude_deg": -60.016667, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Maceió", "uf": "AL", "latitude_deg": -9.640556, "longitude_deg": -35.736389, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "São Gonçalo", "uf": "RJ", "latitude_deg": -22.950000, "longitude_deg": -43.229722, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "São Paulo", "uf": "SP", "latitude_deg": -23.567781, "longitude_deg": -46.650000, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Rio de Janeiro", "uf": "RJ", "latitude_deg": -22.949169, "longitude_deg": -43.228889, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "São Caetano do Sul", "uf": "SP", "latitude_deg": -23.554722, "longitude_deg": -46.664444, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "São José do Rio Preto", "uf": "SP", "latitude_deg": -20.833000, "longitude_deg": -49.357919, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Brasília", "uf": "DF", "latitude_deg": -15.691944, "longitude_deg": -47.853611, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Fortaleza", "uf": "CE", "latitude_deg": -3.747222, "longitude_deg": -38.502500, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Belém", "uf": "PA", "latitude_deg": -1.456667, "longitude_deg": -48.490278, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Ribeirão Preto", "uf": "SP", "latitude_deg": -21.156111, "longitude_deg": -47.837781, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Belo Horizonte", "uf": "MG", "latitude_deg": -19.970833, "longitude_deg": -43.929722, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Campinas", "uf": "SP", "latitude_deg": -22.943889, "longitude_deg": -47.030831, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Maringá", "uf": "PR", "latitude_deg": -23.428611, "longitude_deg": -51.959444, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Presidente Prudente", "uf": "SP", "latitude_deg": -22.123056, "longitude_deg": -51.386667, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Vitória", "uf": "ES", "latitude_deg": -20.308889, "longitude_deg": -40.340000, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Goiânia", "uf": "GO", "latitude_deg": -16.664444, "longitude_deg": -49.345278, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Santa Rosa", "uf": "RS", "latitude_deg": -27.842781, "longitude_deg": -54.476939, "frequencia_MHz": FREQ_INTERF_MHZ},
    {"municipio": "Santa Cruz do Sul", "uf": "RS", "latitude_deg": -29.728056, "longitude_deg": -52.410278, "frequencia_MHz": FREQ_INTERF_MHZ},
]
