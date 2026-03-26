from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from config.defaults import params_tx_default, params_rx_sat, tx_pattern, estacoes_exemplo
from core.antenna import ganho_antena_gso_s672
from core.budget import (
    validar_estacoes,
    validar_tx_pattern,
    expandir_estacoes_com_defaults,
    calcular_interferencia_estacao,
    calcular_metricas_estacao_modelo,
)
from core.aggregate import resumir_agregado_por_frequencia, resumir_agregado_total
from core.sweep import calcular_i_agg_total_e_in, build_longitude_grid, extrair_faixas_contiguas

st.set_page_config(page_title="Interferência agregada em satélite GSO", layout="wide")
st.title("Simulação de interferência agregada de estações de TV digital em satélites GSO")


# ============================================================
# Utilitários
# ============================================================

def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=";", decimal=".").encode("utf-8-sig")


def ler_csv_estacoes(source) -> pd.DataFrame:
    df = pd.read_csv(source, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def carregar_estacoes_padrao_df() -> pd.DataFrame:
    csv_path = Path(__file__).resolve().parent / "data" / "estacoes_exemplo.csv"
    if csv_path.exists():
        try:
            return ler_csv_estacoes(csv_path)
        except Exception:
            pass
    return pd.DataFrame(estacoes_exemplo)


def format_bool_series(series: pd.Series) -> pd.Series:
    return series.map(lambda x: "Sim" if bool(x) else "Não")


def formatar_resultados_para_exibicao(df_resultados: pd.DataFrame) -> pd.DataFrame:
    if df_resultados.empty:
        return df_resultados.copy()

    df = df_resultados.copy()

    cols = [
        "municipio",
        "uf",
        "frequencia_MHz",
        "az_to_sat_deg",
        "elev_deg",
        "theta_eval_used_deg",
        "gso_rx_boresight_offaxis_deg",
        "g_t_dir_dBd",
        "erp_dir_kW",
        "eirp_dir_dBW",
        "i_dBW",
        "n_dBW",
        "i_over_n_dB",
        "delta_t_over_t_pct",
        "visible_flag",
        "visibility_reason",
    ]
    cols = [c for c in cols if c in df.columns]
    df = df[cols].copy()

    rename_map = {
        "municipio": "Município",
        "uf": "UF",
        "frequencia_MHz": "Frequência [MHz]",
        "az_to_sat_deg": "Azimute ao satélite [°]",
        "elev_deg": "Elevação [°]",
        "theta_eval_used_deg": "Ângulo no diagrama vertical [°]",
        "gso_rx_boresight_offaxis_deg": "Off-axis RX satélite [°]",
        "g_t_dir_dBd": "Ganho TX na direção do satélite [dBd]",
        "erp_dir_kW": "ERP na direção do satélite [kW]",
        "eirp_dir_dBW": "EIRP na direção do satélite [dBW]",
        "i_dBW": "Potência interferente no satélite, I [dBW]",
        "n_dBW": "Ruído no receptor, N [dBW]",
        "i_over_n_dB": "I/N [dB]",
        "delta_t_over_t_pct": "ΔT/T [%]",
        "visible_flag": "Visível",
        "visibility_reason": "Observação",
    }
    df = df.rename(columns=rename_map)

    num_cols_round_3 = ["Frequência [MHz]"]
    num_cols_round_2 = [
        "Azimute ao satélite [°]",
        "Elevação [°]",
        "Ângulo no diagrama vertical [°]",
        "Off-axis RX satélite [°]",
        "Ganho TX na direção do satélite [dBd]",
        "ERP na direção do satélite [kW]",
        "EIRP na direção do satélite [dBW]",
        "Potência interferente no satélite, I [dBW]",
        "Ruído no receptor, N [dBW]",
        "I/N [dB]",
        "ΔT/T [%]",
    ]

    for c in num_cols_round_3:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(3)

    for c in num_cols_round_2:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    if "Visível" in df.columns:
        df["Visível"] = format_bool_series(df["Visível"])

    return df


def formatar_agregado_freq_para_exibicao(df_agregado_freq: pd.DataFrame) -> pd.DataFrame:
    if df_agregado_freq.empty:
        return df_agregado_freq.copy()

    df = df_agregado_freq.copy()
    rename_map = {
        "frequencia_MHz": "Frequência [MHz]",
        "n_estacoes_no_grupo": "Nº de estações visíveis",
        "i_agg_W": "I agregado [W]",
        "i_agg_dBW": "I agregado [dBW]",
        "n_dBW": "N [dBW]",
        "i_over_n_agg_dB": "I/N agregado [dB]",
        "delta_t_over_t_agg_pct": "ΔT/T agregado [%]",
        "pior_estacao_municipio": "Pior estação (município)",
        "pior_estacao_uf": "Pior estação (UF)",
        "pior_estacao_i_dBW": "Pior estação - I [dBW]",
    }
    df = df.rename(columns=rename_map)

    for c in [
        "Frequência [MHz]",
        "I agregado [W]",
        "I agregado [dBW]",
        "N [dBW]",
        "I/N agregado [dB]",
        "ΔT/T agregado [%]",
        "Pior estação - I [dBW]",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    return df


def formatar_agregado_total_para_exibicao(df_agregado_total: pd.DataFrame) -> pd.DataFrame:
    if df_agregado_total.empty:
        return df_agregado_total.copy()

    df = df_agregado_total.copy()
    rename_map = {
        "n_estacoes_visiveis": "Nº de estações visíveis",
        "i_agg_total_W": "I agregado total [W]",
        "i_agg_total_dBW": "I agregado total [dBW]",
        "n_dBW": "N [dBW]",
        "i_over_n_agg_total_dB": "I/N agregado total [dB]",
        "delta_t_over_t_agg_total_pct": "ΔT/T agregado total [%]",
        "observacao": "Observação",
    }
    df = df.rename(columns=rename_map)

    for c in [
        "I agregado total [W]",
        "I agregado total [dBW]",
        "N [dBW]",
        "I/N agregado total [dB]",
        "ΔT/T agregado total [%]",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    return df


def formatar_varredura_para_exibicao(df_scan: pd.DataFrame) -> pd.DataFrame:
    if df_scan.empty:
        return df_scan.copy()

    df = df_scan.copy()
    rename_map = {
        "gso_lon_deg": "Longitude GSO [°]",
        "g_r_max_dBi": "Ganho RX máximo [dBi]",
        "n_estacoes_visiveis": "Nº de estações visíveis",
        "i_agg_total_dBW": "I agregado total [dBW]",
        "i_over_n_agg_total_dB": "I/N agregado total [dB]",
        "benchmark_i_over_n_dB": "Benchmark de I/N [dB]",
        "atende_criterio": "Atende ao critério",
    }
    df = df.rename(columns=rename_map)

    for c in [
        "Longitude GSO [°]",
        "Ganho RX máximo [dBi]",
        "I agregado total [dBW]",
        "I/N agregado total [dB]",
        "Benchmark de I/N [dB]",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    if "Atende ao critério" in df.columns:
        df["Atende ao critério"] = format_bool_series(df["Atende ao critério"])

    return df


def formatar_faixas_para_exibicao(df_ranges: pd.DataFrame) -> pd.DataFrame:
    if df_ranges.empty:
        return df_ranges.copy()

    df = df_ranges.copy()
    rename_map = {
        "g_r_max_dBi": "Ganho RX máximo [dBi]",
        "lon_ini_deg": "Longitude inicial [°]",
        "lon_fim_deg": "Longitude final [°]",
        "n_pontos": "Nº de pontos",
        "largura_deg_amostrada": "Largura amostrada [°]",
        "i_over_n_min_dB_na_faixa": "I/N mínimo na faixa [dB]",
        "i_over_n_max_dB_na_faixa": "I/N máximo na faixa [dB]",
        "benchmark_i_over_n_dB": "Benchmark de I/N [dB]",
        "lon_step_deg": "Passo [°]",
        "observacao": "Observação",
    }
    df = df.rename(columns=rename_map)

    for c in [
        "Ganho RX máximo [dBi]",
        "Longitude inicial [°]",
        "Longitude final [°]",
        "Largura amostrada [°]",
        "I/N mínimo na faixa [dB]",
        "I/N máximo na faixa [dB]",
        "Benchmark de I/N [dB]",
        "Passo [°]",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    return df


# ============================================================
# Controles laterais
# ============================================================

def montar_params_tx_ui():
    with st.sidebar:
        st.header("Parâmetros da estação de TV")
        p = dict(params_tx_default)
        p["site_alt_m"] = st.number_input("Altitude do local [m]", value=float(p["site_alt_m"]))
        p["ant_height_m"] = st.number_input("Altura da antena [m]", value=float(p["ant_height_m"]))
        p["p_tx_kW"] = st.number_input("Potência TX [kW]", value=float(p["p_tx_kW"]), min_value=0.001)
        p["g_t_max_dBd"] = st.number_input("Ganho TX máximo [dBd]", value=float(p["g_t_max_dBd"]))
        p["tilt_deg"] = st.number_input("Tilt [graus]", value=float(p["tilt_deg"]))
        p["l_atm_dB"] = st.number_input("Perda adicional de percurso [dB]", value=float(p["l_atm_dB"]))
        p["l_pol_mismatch_dB"] = st.number_input("Perda de polarização [dB]", value=float(p["l_pol_mismatch_dB"]))
        p["line_length_m"] = st.number_input("Comprimento da linha [m]", value=float(p["line_length_m"]), min_value=0.0)
        p["line_att_dB_per_100m"] = st.number_input("Atenuação da linha [dB/100m]", value=float(p["line_att_dB_per_100m"]), min_value=0.0)
        p["accessory_losses_dB"] = st.number_input("Perdas acessórias [dB]", value=float(p["accessory_losses_dB"]), min_value=0.0)
        p["pol_tx"] = st.selectbox("Polarização TX", options=["horizontal", "vertical", "eliptica", "circular"], index=0)
        p["b_tx_Hz"] = st.number_input("Banda do interferente [Hz]", value=float(p["b_tx_Hz"]), min_value=1.0, step=1000000.0)
        p["Eh_dB"] = st.number_input("Discriminação horizontal adicional [dB]", value=float(p["Eh_dB"]))
    return p


def montar_params_rx_ui():
    with st.sidebar:
        st.header("Parâmetros do satélite GSO")
        p = dict(params_rx_sat)
        p["sat_id"] = st.text_input("ID do satélite", value=str(p["sat_id"]))
        p["gso_lon_deg"] = st.number_input("Longitude orbital GSO [graus]", value=float(p["gso_lon_deg"]))
        p["pol_rx"] = st.text_input("Polarização RX", value=str(p["pol_rx"]))
        p["t_sys_K"] = st.number_input("T_sys [K]", value=float(p["t_sys_K"]), min_value=1.0)
        p["l_rx_dB"] = st.number_input("Perdas RX [dB]", value=float(p["l_rx_dB"]))
        p["g_r_max_dBi"] = st.number_input("Ganho máximo RX [dBi]", value=float(p["g_r_max_dBi"]))
        p["psi_b_deg"] = st.number_input("Semi-largura de feixe psi_b [graus]", value=float(p["psi_b_deg"]), min_value=1e-6)
        p["ln_db"] = st.selectbox("ln_db", options=[-20.0, -25.0], index=0 if float(p["ln_db"]) == -20.0 else 1)
        p["lf_db"] = st.number_input("lf_db [dBi]", value=float(p["lf_db"]))
        p["benchmark_i_over_n_dB"] = st.number_input("I/N máximo de proteção [dB]", value=float(p["benchmark_i_over_n_dB"]))
        p["elev_min_deg"] = st.number_input("Elevação mínima adotada [graus]", value=float(p["elev_min_deg"]))
        p["apply_low_elevation_excess_loss"] = st.checkbox(
            "Aplicar perda extra em baixa elevação",
            value=bool(p["apply_low_elevation_excess_loss"]),
        )
    return p


# ============================================================
# Núcleo do app
# ============================================================

def rodar_cenario(df_estacoes_edit, params_tx_ui, params_rx_ui):
    estacoes = df_estacoes_edit.to_dict(orient="records")
    validar_estacoes(estacoes)
    validar_tx_pattern(tx_pattern)

    estacoes_expandidas = expandir_estacoes_com_defaults(estacoes, params_tx_ui)
    resultados = [
        calcular_interferencia_estacao(estacao=e, params_rx_sat=params_rx_ui, tx_pattern=tx_pattern)
        for e in estacoes_expandidas
    ]

    df_estacoes = pd.DataFrame(estacoes_expandidas)
    df_resultados = pd.DataFrame(resultados)

    df_resultados = df_resultados.sort_values(
        by=["visible_flag", "i_dBW"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)

    df_agregado_freq = resumir_agregado_por_frequencia(df_resultados)
    df_agregado_total = resumir_agregado_total(df_resultados)

    return df_estacoes, df_resultados, df_agregado_freq, df_agregado_total


def rodar_varredura(estacoes_df, params_tx_ui, params_rx_ui, lon_min_deg, lon_max_deg, lon_step_deg, g_r_list):
    estacoes = estacoes_df.to_dict(orient="records")
    validar_estacoes(estacoes)
    validar_tx_pattern(tx_pattern)

    estacoes_expandidas = expandir_estacoes_com_defaults(estacoes, params_tx_ui)

    lons = build_longitude_grid(lon_min_deg, lon_max_deg, lon_step_deg)
    rows = []

    for g_r in g_r_list:
        for lon in lons:
            res = calcular_i_agg_total_e_in(
                estacoes_expandidas,
                params_rx_ui,
                tx_pattern,
                gso_lon_deg=float(lon),
                g_r_max_dBi=float(g_r),
            )

            rows.append({
                "gso_lon_deg": float(lon),
                "g_r_max_dBi": float(g_r),
                "n_estacoes_visiveis": res["n_estacoes_visiveis"],
                "i_agg_total_dBW": res["i_agg_total_dBW"],
                "i_over_n_agg_total_dB": res["i_over_n_agg_total_dB"],
                "benchmark_i_over_n_dB": float(params_rx_ui["benchmark_i_over_n_dB"]),
                "atende_criterio": bool(
                    pd.notna(res["i_over_n_agg_total_dB"])
                    and (res["i_over_n_agg_total_dB"] <= float(params_rx_ui["benchmark_i_over_n_dB"]))
                ),
            })

    df_scan = pd.DataFrame(rows)
    df_ranges = extrair_faixas_contiguas(df_scan, lon_step_deg)
    return df_scan, df_ranges


# ============================================================
# Gráficos
# ============================================================

def plot_top_in(df_resultados: pd.DataFrame):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return None

    df_top = (
        df_vis.sort_values(by="i_over_n_dB", ascending=False)
        .head(min(10, len(df_vis)))
        .iloc[::-1]
        .copy()
    )

    labels = [f"{m}/{uf}" for m, uf in zip(df_top["municipio"], df_top["uf"])]

    fig, ax = plt.subplots(figsize=(10, max(6, 0.42 * len(df_top) + 1.5)))
    ax.barh(labels, df_top["i_over_n_dB"])
    ax.axvline(float(df_top["benchmark_i_over_n_dB"].iloc[0]), linestyle="--")
    ax.set_xlabel("I/N [dB]")
    ax.set_ylabel("Estação")
    ax.set_title(f"Top {len(df_top)} piores casos individuais por I/N")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_top_i(df_resultados: pd.DataFrame):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return None

    df_top = (
        df_vis.sort_values(by="i_dBW", ascending=False)
        .head(min(10, len(df_vis)))
        .iloc[::-1]
        .copy()
    )

    labels = [f"{m}/{uf}" for m, uf in zip(df_top["municipio"], df_top["uf"])]

    fig, ax = plt.subplots(figsize=(10, max(6, 0.42 * len(df_top) + 1.5)))
    ax.barh(labels, df_top["i_dBW"])
    ax.set_xlabel("Potência interferente no satélite, I [dBW]")
    ax.set_ylabel("Estação")
    ax.set_title(f"Top {len(df_top)} piores casos individuais por potência interferente")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_crescimento(df_resultados: pd.DataFrame):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return None

    df_ord = df_vis.sort_values(by="i_dBW", ascending=False).reset_index(drop=True)
    df_ord["i_agg_cumul_W"] = df_ord["i_W"].cumsum()
    df_ord["i_agg_cumul_dBW"] = -np.inf

    mask = df_ord["i_agg_cumul_W"] > 0
    df_ord.loc[mask, "i_agg_cumul_dBW"] = 10.0 * np.log10(df_ord.loc[mask, "i_agg_cumul_W"])

    x = np.arange(1, len(df_ord) + 1)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x, df_ord["i_agg_cumul_dBW"])
    ax.set_xlabel("Número de estações acumuladas (do pior caso para o menor)")
    ax.set_ylabel("Interferência agregada acumulada [dBW]")
    ax.set_title("Crescimento do agregado cocanal")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_agregado_vs_benchmark(df_resultados: pd.DataFrame, df_agregado_total: pd.DataFrame):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty or df_agregado_total.empty:
        return None

    pior_individual_in = float(df_vis["i_over_n_dB"].max())
    agregado_in = float(df_agregado_total["i_over_n_agg_total_dB"].iloc[0])
    benchmark = float(df_vis["benchmark_i_over_n_dB"].iloc[0])

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(["Pior individual", "Agregado cocanal"], [pior_individual_in, agregado_in])
    ax.axhline(benchmark, linestyle="--")
    ax.set_ylabel("I/N [dB]")
    ax.set_title("Comparação entre pior caso individual e agregado cocanal")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_varredura(df_scan: pd.DataFrame):
    if df_scan.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    for g_r, grupo in df_scan.groupby("g_r_max_dBi", sort=True):
        grupo = grupo.sort_values("gso_lon_deg")
        ax.plot(grupo["gso_lon_deg"], grupo["i_over_n_agg_total_dB"], label=f"g_r_max={g_r:.1f} dBi")

    ax.axhline(float(df_scan["benchmark_i_over_n_dB"].iloc[0]), linestyle="--")
    ax.set_xlabel("Longitude GSO [graus]")
    ax.set_ylabel("I/N agregado total [dB]")
    ax.set_title("Varredura de longitude orbital GSO")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_diagrama_vertical_tv_linear(params_tx_ui, tx_pattern, df_resultados=None):
    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    ev_dB = 20.0 * np.log10(np.maximum(e_rel, 1e-12))
    g_dir_dBd = float(params_tx_ui["g_t_max_dBd"]) + float(params_tx_ui["Eh_dB"]) + ev_dB
    g_dir_linear = 10.0 ** (g_dir_dBd / 10.0)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(angle_deg, g_dir_linear, label="Ganho TV no plano vertical [linear]")

    if df_resultados is not None and not df_resultados.empty:
        df_vis = df_resultados[df_resultados["visible_flag"]].copy()
        if not df_vis.empty and "theta_eval_used_deg" in df_vis.columns and "g_t_dir_dBd" in df_vis.columns:
            y_pts = 10.0 ** (df_vis["g_t_dir_dBd"] / 10.0)
            ax.scatter(
                df_vis["theta_eval_used_deg"],
                y_pts,
                marker="o",
                label="Pontos das estações visíveis",
                alpha=0.8,
            )

    ax.set_xlabel("Ângulo no diagrama vertical [°]")
    ax.set_ylabel("Ganho linear [rel. ao dipolo]")
    ax.set_title("Diagrama vertical da antena de TV — escala linear")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_diagrama_vertical_tv_db(params_tx_ui, tx_pattern, df_resultados=None):
    angle_deg = np.asarray(tx_pattern["angle_deg"], dtype=float)
    e_rel = np.asarray(tx_pattern["e_rel"], dtype=float)

    ev_dB = 20.0 * np.log10(np.maximum(e_rel, 1e-12))
    g_dir_dBd = float(params_tx_ui["g_t_max_dBd"]) + float(params_tx_ui["Eh_dB"]) + ev_dB

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(angle_deg, g_dir_dBd, label="Ganho TV no plano vertical [dBd]")

    if df_resultados is not None and not df_resultados.empty:
        df_vis = df_resultados[df_resultados["visible_flag"]].copy()
        if not df_vis.empty and "theta_eval_used_deg" in df_vis.columns and "g_t_dir_dBd" in df_vis.columns:
            ax.scatter(
                df_vis["theta_eval_used_deg"],
                df_vis["g_t_dir_dBd"],
                marker="o",
                label="Pontos das estações visíveis",
                alpha=0.8,
            )

    ax.set_xlabel("Ângulo no diagrama vertical [°]")
    ax.set_ylabel("Ganho na direção do satélite [dBd]")
    ax.set_title("Diagrama vertical da antena de TV — escala dB")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_diagrama_satelite_linear(params_rx_ui, df_resultados=None):
    psi_deg = np.linspace(0.0, 180.0, 2001)
    g_r_dBi = ganho_antena_gso_s672(
        psi_deg=psi_deg,
        gmax_dbi=float(params_rx_ui["g_r_max_dBi"]),
        psi_b_deg=float(params_rx_ui["psi_b_deg"]),
        ln_db=float(params_rx_ui["ln_db"]),
        lf_db=float(params_rx_ui["lf_db"]),
    )
    g_r_linear = 10.0 ** (g_r_dBi / 10.0)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(psi_deg, g_r_linear, label="Ganho RX do satélite [linear]")

    if df_resultados is not None and not df_resultados.empty:
        df_vis = df_resultados[df_resultados["visible_flag"]].copy()
        if not df_vis.empty and "gso_rx_boresight_offaxis_deg" in df_vis.columns and "g_r_dir_dBi" in df_vis.columns:
            y_pts = 10.0 ** (df_vis["g_r_dir_dBi"] / 10.0)
            ax.scatter(
                df_vis["gso_rx_boresight_offaxis_deg"],
                y_pts,
                marker="o",
                label="Pontos das estações visíveis",
                alpha=0.8,
            )

    ax.set_xlabel("Off-axis do satélite [°]")
    ax.set_ylabel("Ganho linear [rel. à isotrópica]")
    ax.set_title("Diagrama do satélite GSO — escala linear")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_diagrama_satelite_db(params_rx_ui, df_resultados=None):
    psi_deg = np.linspace(0.0, 180.0, 2001)
    g_r_dBi = ganho_antena_gso_s672(
        psi_deg=psi_deg,
        gmax_dbi=float(params_rx_ui["g_r_max_dBi"]),
        psi_b_deg=float(params_rx_ui["psi_b_deg"]),
        ln_db=float(params_rx_ui["ln_db"]),
        lf_db=float(params_rx_ui["lf_db"]),
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(psi_deg, g_r_dBi, label="Ganho RX do satélite [dBi]")

    if df_resultados is not None and not df_resultados.empty:
        df_vis = df_resultados[df_resultados["visible_flag"]].copy()
        if not df_vis.empty and "gso_rx_boresight_offaxis_deg" in df_vis.columns and "g_r_dir_dBi" in df_vis.columns:
            ax.scatter(
                df_vis["gso_rx_boresight_offaxis_deg"],
                df_vis["g_r_dir_dBi"],
                marker="o",
                label="Pontos das estações visíveis",
                alpha=0.8,
            )

    ax.set_xlabel("Off-axis do satélite [°]")
    ax.set_ylabel("Ganho RX [dBi]")
    ax.set_title("Diagrama do satélite GSO — escala dB")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


# ============================================================
# Estado inicial
# ============================================================

if "df_estacoes_base" not in st.session_state:
    st.session_state["df_estacoes_base"] = carregar_estacoes_padrao_df()

if "scenario_outputs" not in st.session_state:
    st.session_state["scenario_outputs"] = None

if "sweep_outputs" not in st.session_state:
    st.session_state["sweep_outputs"] = None


# ============================================================
# Sidebar
# ============================================================

params_tx_ui = montar_params_tx_ui()
params_rx_ui = montar_params_rx_ui()

with st.sidebar:
    st.header("Estações (CSV)")
    uploaded_file = st.file_uploader("Enviar arquivo CSV de estações", type=["csv"], key="stations_upload")

    if uploaded_file is not None:
        if st.button("Usar CSV enviado"):
            try:
                uploaded_file.seek(0)
                df_upload = ler_csv_estacoes(uploaded_file)
                st.session_state["df_estacoes_base"] = df_upload.copy()
                st.success("CSV carregado com sucesso.")
            except Exception as e:
                st.error(f"Falha ao ler o CSV: {e}")

    if st.button("Restaurar estações padrão"):
        st.session_state["df_estacoes_base"] = carregar_estacoes_padrao_df()
        st.success("Estações padrão restauradas.")

    st.download_button(
        "Baixar template CSV",
        data=dataframe_to_csv_bytes(carregar_estacoes_padrao_df()),
        file_name="template_estacoes.csv",
        mime="text/csv",
    )

    st.caption("Colunas esperadas: municipio, uf, latitude_deg, longitude_deg, frequencia_MHz")


# ============================================================
# Área principal
# ============================================================

metricas_modelo = calcular_metricas_estacao_modelo(params_tx_ui)

col_left, col_right = st.columns([4, 1])

with col_left:
    st.subheader("Estações de radiodifusão")
    df_estacoes_edit = st.data_editor(
        st.session_state["df_estacoes_base"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_estacoes_principal",
    )
    st.session_state["df_estacoes_base"] = df_estacoes_edit.copy()

with col_right:
    st.subheader("Estação modelo")
    st.metric("ERP máxima [kW]", f"{metricas_modelo['erp_max_kW']:.2f}")
    st.caption("Calculada a partir da potência, perdas de linha e ganho máximo da antena.")

tab1, tab2, tab3 = st.tabs(["Cenário único", "Varredura de longitude GSO", "Diagramas das antenas"])

with tab1:
    st.caption(
        "Obs.: o resumo agregado total representa um cenário estritamente cocanal "
        "apenas quando todas as estações estão na mesma frequência."
    )

    if st.button("Rodar simulação", type="primary"):
        try:
            df_estacoes, df_resultados, df_agregado_freq, df_agregado_total = rodar_cenario(
                df_estacoes_edit,
                params_tx_ui,
                params_rx_ui,
            )

            st.session_state["scenario_outputs"] = {
                "df_estacoes": df_estacoes,
                "df_resultados": df_resultados,
                "df_agregado_freq": df_agregado_freq,
                "df_agregado_total": df_agregado_total,
            }
            st.success("Simulação concluída.")

        except Exception as e:
            st.exception(e)

    scenario_outputs = st.session_state.get("scenario_outputs")
    if scenario_outputs is not None:
        df_resultados = scenario_outputs["df_resultados"]
        df_agregado_freq = scenario_outputs["df_agregado_freq"]
        df_agregado_total = scenario_outputs["df_agregado_total"]

        freqs = sorted(df_resultados["frequencia_MHz"].dropna().unique())
        if len(freqs) > 1:
            st.warning(
                "Há múltiplas frequências na entrada. O resumo agregado total deixa de representar "
                "um cenário estritamente cocanal. Prefira também analisar o resumo agregado por frequência."
            )

        col1, col2, col3 = st.columns(3)
        col1.metric("Estações visíveis", int(df_agregado_total["n_estacoes_visiveis"].iloc[0]))
        col2.metric("I agregado total [dBW]", f"{df_agregado_total['i_agg_total_dBW'].iloc[0]:.2f}")
        col3.metric(
            "I/N agregado [dB]",
            f"{df_agregado_total['i_over_n_agg_total_dB'].iloc[0]:.2f}"
            if pd.notna(df_agregado_total["i_over_n_agg_total_dB"].iloc[0])
            else "nan",
        )

        agg_in = (
            float(df_agregado_total["i_over_n_agg_total_dB"].iloc[0])
            if pd.notna(df_agregado_total["i_over_n_agg_total_dB"].iloc[0])
            else None
        )
        benchmark = float(params_rx_ui["benchmark_i_over_n_dB"])

        if agg_in is not None:
            if agg_in <= benchmark:
                st.success("O agregado atende ao benchmark preliminar.")
            else:
                st.error("O agregado excede o benchmark preliminar.")

        st.subheader("Resultados por estação")
        st.dataframe(formatar_resultados_para_exibicao(df_resultados), use_container_width=True)

        st.subheader("Resumo agregado por frequência")
        st.dataframe(formatar_agregado_freq_para_exibicao(df_agregado_freq), use_container_width=True)

        st.subheader("Resumo agregado total")
        st.dataframe(formatar_agregado_total_para_exibicao(df_agregado_total), use_container_width=True)

        fig1 = plot_top_in(df_resultados)
        if fig1 is not None:
            st.pyplot(fig1)

        fig2 = plot_top_i(df_resultados)
        if fig2 is not None:
            st.pyplot(fig2)

        fig3 = plot_crescimento(df_resultados)
        if fig3 is not None:
            st.pyplot(fig3)

        fig4 = plot_agregado_vs_benchmark(df_resultados, df_agregado_total)
        if fig4 is not None:
            st.pyplot(fig4)

        st.download_button(
            "Baixar resultados por estação (CSV)",
            dataframe_to_csv_bytes(df_resultados),
            file_name="resultados_por_estacao.csv",
            mime="text/csv",
        )
        st.download_button(
            "Baixar resumo agregado por frequência (CSV)",
            dataframe_to_csv_bytes(df_agregado_freq),
            file_name="resumo_agregado_por_frequencia.csv",
            mime="text/csv",
        )
        st.download_button(
            "Baixar resumo agregado total (CSV)",
            dataframe_to_csv_bytes(df_agregado_total),
            file_name="resumo_agregado_total.csv",
            mime="text/csv",
        )

with tab2:
    colA, colB, colC = st.columns(3)
    lon_min_deg = colA.number_input("Longitude mínima [graus]", value=-141.0)
    lon_max_deg = colB.number_input("Longitude máxima [graus]", value=46.0)
    lon_step_deg = colC.number_input("Passo [graus]", value=1.0, min_value=0.1)
    g_r_list_str = st.text_input("Lista de ganhos RX máximos [dBi]", value="18,23,35")

    if st.button("Rodar varredura GSO"):
        try:
            g_r_list = [float(x.strip()) for x in g_r_list_str.split(",") if x.strip()]

            df_scan, df_ranges = rodar_varredura(
                df_estacoes_edit,
                params_tx_ui,
                params_rx_ui,
                lon_min_deg,
                lon_max_deg,
                lon_step_deg,
                g_r_list,
            )

            st.session_state["sweep_outputs"] = {
                "df_scan": df_scan,
                "df_ranges": df_ranges,
            }
            st.success("Varredura concluída.")

        except Exception as e:
            st.exception(e)

    sweep_outputs = st.session_state.get("sweep_outputs")
    if sweep_outputs is not None:
        df_scan = sweep_outputs["df_scan"]
        df_ranges = sweep_outputs["df_ranges"]

        st.dataframe(formatar_varredura_para_exibicao(df_scan), use_container_width=True)

        st.subheader("Faixas contíguas que atendem ao critério")
        st.dataframe(formatar_faixas_para_exibicao(df_ranges), use_container_width=True)

        fig_scan = plot_varredura(df_scan)
        if fig_scan is not None:
            st.pyplot(fig_scan)

        st.download_button(
            "Baixar varredura (CSV)",
            dataframe_to_csv_bytes(df_scan),
            file_name="varredura_longitude_gso.csv",
            mime="text/csv",
        )
        st.download_button(
            "Baixar faixas contíguas (CSV)",
            dataframe_to_csv_bytes(df_ranges),
            file_name="faixas_contiguas_gso.csv",
            mime="text/csv",
        )

with tab3:
    st.subheader("Diagramas de antena")

    scenario_outputs = st.session_state.get("scenario_outputs")
    df_resultados_pattern = None if scenario_outputs is None else scenario_outputs["df_resultados"]

    col_tv, col_sat = st.columns(2)

    with col_tv:
        st.markdown("### Antena de TV")
        st.caption("Acima: ganho em escala linear. Abaixo: ganho em dB, usando o diagrama vertical proxy adotado no modelo.")

        fig_tv_lin = plot_diagrama_vertical_tv_linear(params_tx_ui, tx_pattern, df_resultados_pattern)
        st.pyplot(fig_tv_lin)

        fig_tv_db = plot_diagrama_vertical_tv_db(params_tx_ui, tx_pattern, df_resultados_pattern)
        st.pyplot(fig_tv_db)

    with col_sat:
        st.markdown("### Antena do satélite GSO")
        st.caption("Acima: ganho em escala linear. Abaixo: ganho em dB, conforme o modelo RX adotado no estudo.")

        fig_sat_lin = plot_diagrama_satelite_linear(params_rx_ui, df_resultados_pattern)
        st.pyplot(fig_sat_lin)

        fig_sat_db = plot_diagrama_satelite_db(params_rx_ui, df_resultados_pattern)
        st.pyplot(fig_sat_db)

    st.info(
        "Se a simulação do cenário único já tiver sido rodada, os diagramas mostram também os pontos "
        "correspondentes às estações visíveis sobre as curvas."
    )