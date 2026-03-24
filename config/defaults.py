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
    "gso_lon_deg": -50.0,
    "pol_rx": "M",
    "t_sys_K": 700.0,
    "l_rx_dB": 0.0,
    "g_r_max_dBi": 23.0,
    "psi_b_deg": 1.1,
    "ln_db": -20.0,
    "lf_db": 0.0,
    "benchmark_i_over_n_dB": -12.2,
    "elev_min_deg": 0.0,
    "apply_low_elevation_excess_loss": True,
}

tx_pattern = {
    "angle_deg": np.array([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90], dtype=float),
    "e_rel": np.array([1.00, 0.92, 0.55, 0.20, 0.03, 0.20, 0.16, 0.08, 0.03, 0.08, 0.10, 0.06, 0.03, 0.015, 0.008, 0.005], dtype=float),
}

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
