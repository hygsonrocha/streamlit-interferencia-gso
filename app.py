from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from config.defaults import (
    params_tx_default,
    params_rx_sat,
    estacoes_exemplo,
    TX_VERTICAL_HPBW_TARGET_DEG,
    GSO_LON_MIN_DEG,
    GSO_LON_MAX_DEG,
    GSO_LON_STEP_DEG,
)
from core.antenna import (
    ganho_antena_gso_s672,
    build_tx_pattern_analytic,
    build_rx_pattern_s672,
    resolve_psi_b_deg,
)
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


def carregar_readme_text() -> str:
    readme_path = Path(__file__).resolve().parent / "README.md"
    if readme_path.exists():
        try:
            return readme_path.read_text(encoding="utf-8")
        except Exception:
            return "Não foi possível ler o arquivo README.md."
    return "README.md não encontrado."


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
        "b_tx_Hz",
        "b_rx_Hz",
        "b_ov_Hz",
        "az_to_sat_deg",
        "elev_deg",
        "theta_eval_used_deg",
        "gso_rx_boresight_offaxis_deg",
        "g_t_dir_dBd",
        "erp_dir_kW",
        "eirp_dir_dBW",
        "eirp_density_dBW_per_Hz",
        "i_density_dBW_per_Hz",
        "i_dBW",
        "n0_dBW_per_Hz",
        "n_dBW",
        "i0_over_n0_dB",
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
        "b_tx_Hz": "Banda TX [Hz]",
        "b_rx_Hz": "Banda RX [Hz]",
        "b_ov_Hz": "Banda sobreposta [Hz]",
        "az_to_sat_deg": "Azimute ao satélite [°]",
        "elev_deg": "Elevação [°]",
        "theta_eval_used_deg": "Ângulo no diagrama vertical [°]",
        "gso_rx_boresight_offaxis_deg": "Off-axis RX satélite [°]",
        "g_t_dir_dBd": "Ganho TX na direção do satélite [dBd]",
        "erp_dir_kW": "ERP na direção do satélite [kW]",
        "eirp_dir_dBW": "EIRP na direção do satélite [dBW]",
        "eirp_density_dBW_per_Hz": "Densidade de EIRP [dBW/Hz]",
        "i_density_dBW_per_Hz": "Densidade interferente no satélite [dBW/Hz]",
        "i_dBW": "Potência interferente no satélite, I [dBW]",
        "n0_dBW_per_Hz": "Densidade de ruído, N0 [dBW/Hz]",
        "n_dBW": "Ruído no receptor, N [dBW]",
        "i0_over_n0_dB": "I0/N0 [dB]",
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
        "Densidade de EIRP [dBW/Hz]",
        "Densidade interferente no satélite [dBW/Hz]",
        "Potência interferente no satélite, I [dBW]",
        "Densidade de ruído, N0 [dBW/Hz]",
        "Ruído no receptor, N [dBW]",
        "I0/N0 [dB]",
        "I/N [dB]",
        "ΔT/T [%]",
    ]
    num_cols_int_like = ["Banda TX [Hz]", "Banda RX [Hz]", "Banda sobreposta [Hz]"]

    for c in num_cols_round_3:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(3)

    for c in num_cols_round_2:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    for c in num_cols_int_like:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(0)

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
        "benchmark_i_over_n_dB": "Alvo agregado de I/N [dB]",
        "atende_criterio": "Atende ao critério",
    }
    df = df.rename(columns=rename_map)

    for c in [
        "Longitude GSO [°]",
        "Ganho RX máximo [dBi]",
        "I agregado total [dBW]",
        "I/N agregado total [dB]",
        "Alvo agregado de I/N [dB]",
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
        "benchmark_i_over_n_dB": "Alvo agregado de I/N [dB]",
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
        "Alvo agregado de I/N [dB]",
        "Passo [°]",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)

    return df


def build_tx_pattern_from_params(params_tx_ui: dict) -> dict:
    tx_pattern = build_tx_pattern_analytic(
        n_levels=int(params_tx_ui["tx_n_levels"]),
        d_lambda=float(params_tx_ui["tx_d_lambda"]),
        use_binomial=bool(params_tx_ui["tx_use_binomial"]),
        beta_tilt_deg=float(params_tx_ui["tx_beta_tilt_deg"]),
        target_hpbw_deg=TX_VERTICAL_HPBW_TARGET_DEG,
    )
    validar_tx_pattern(tx_pattern)
    return tx_pattern


def build_rx_pattern_from_params(params_rx_ui: dict) -> dict:
    return build_rx_pattern_s672(
        gmax_dbi=float(params_rx_ui["g_r_max_dBi"]),
        psi_b_deg=params_rx_ui.get("psi_b_deg"),
        eta_ap=float(params_rx_ui.get("eta_ap", 0.60)),
        ln_db=float(params_rx_ui["ln_db"]),
        lf_db=float(params_rx_ui["lf_db"]),
    )


def rx_psi_b_used_from_params(params_rx_ui: dict) -> float:
    return resolve_psi_b_deg(
        gmax_dbi=float(params_rx_ui["g_r_max_dBi"]),
        psi_b_deg=params_rx_ui.get("psi_b_deg"),
        eta_ap=float(params_rx_ui.get("eta_ap", 0.60)),
    )

def get_tx_mode_options():
    return {
        "Potência TX + perdas + ganho": "potencia_tx",
        "ERP máxima direta": "erp_max_direta",
    }



# ============================================================
# Controles laterais
# ============================================================

def montar_params_tx_ui():
    with st.sidebar:
        st.header("Parâmetros da estação de TV")
        p = dict(params_tx_default)
        p["site_alt_m"] = st.number_input("Altitude do local [m]", value=float(p["site_alt_m"]))
        p["ant_height_m"] = st.number_input("Altura da antena [m]", value=float(p["ant_height_m"]))

        tx_mode_options = get_tx_mode_options()
        tx_mode_labels = list(tx_mode_options.keys())
        tx_mode_values = list(tx_mode_options.values())
        default_tx_mode = str(p.get("tx_input_mode", "potencia_tx"))
        if default_tx_mode not in tx_mode_values:
            default_tx_mode = "potencia_tx"
        selected_tx_mode_label = st.selectbox(
            "Modo de entrada TX",
            options=tx_mode_labels,
            index=tx_mode_values.index(default_tx_mode),
        )
        p["tx_input_mode"] = tx_mode_options[selected_tx_mode_label]

        if p["tx_input_mode"] == "potencia_tx":
            p["p_tx_kW"] = st.number_input("Potência TX [kW]", value=float(p["p_tx_kW"]), min_value=0.001)
        else:
            p["erp_max_input_kW"] = st.number_input(
                "ERP máxima direta [kW]",
                value=float(p.get("erp_max_input_kW", 1.0)),
                min_value=1e-6,
                format="%.6f",
            )
            st.caption("Neste modo, a ERP máxima é a entrada principal. As perdas de linha abaixo são usadas apenas para retrocalcular a potência equivalente antes da antena.")

        p["g_t_max_dBd"] = st.number_input("Ganho TX máximo [dBd]", value=float(p["g_t_max_dBd"]))
        p["tilt_deg"] = st.number_input("Downtilt mecânico [graus, positivo para baixo]", value=float(p["tilt_deg"]))
        p["l_atm_dB"] = st.number_input("Perda adicional de percurso [dB]", value=float(p["l_atm_dB"]))
        p["l_pol_mismatch_dB"] = st.number_input("Perda de polarização [dB]", value=float(p["l_pol_mismatch_dB"]))
        p["line_length_m"] = st.number_input("Comprimento da linha [m]", value=float(p["line_length_m"]), min_value=0.0)
        p["line_att_dB_per_100m"] = st.number_input("Atenuação da linha [dB/100m]", value=float(p["line_att_dB_per_100m"]), min_value=0.0)
        p["accessory_losses_dB"] = st.number_input("Perdas acessórias [dB]", value=float(p["accessory_losses_dB"]), min_value=0.0)
        p["pol_tx"] = st.selectbox("Polarização TX", options=["horizontal", "vertical", "eliptica", "circular"], index=0)
        p["b_tx_Hz"] = st.number_input("Banda TX [Hz]", value=float(p["b_tx_Hz"]), min_value=1.0, step=1000000.0)
        p["Eh_dB"] = st.number_input("Discriminação horizontal adicional [dB]", value=float(p["Eh_dB"]))

        st.markdown("### Modelo analítico da antena TX")
        p["tx_n_levels"] = st.selectbox(
            "Níveis verticais da antena TX",
            options=sorted(TX_VERTICAL_HPBW_TARGET_DEG.keys()),
            index=sorted(TX_VERTICAL_HPBW_TARGET_DEG.keys()).index(int(p["tx_n_levels"])),
        )
        p["tx_d_lambda"] = st.number_input(
            "Espaçamento vertical d/λ",
            value=float(p["tx_d_lambda"]),
            min_value=0.01,
            step=0.05,
            format="%.2f",
        )
        p["tx_use_binomial"] = st.checkbox(
            "Usar pesos binomiais (null-filling simples)",
            value=bool(p["tx_use_binomial"]),
        )
        p["tx_beta_tilt_deg"] = st.number_input(
            "Tilt elétrico β [graus]",
            value=float(p["tx_beta_tilt_deg"]),
            step=0.1,
            format="%.2f",
        )
    return p

def montar_params_rx_ui():
    with st.sidebar:
        st.header("Parâmetros do satélite GSO")
        p = dict(params_rx_sat)
        p["sat_id"] = st.text_input("ID do satélite", value=str(p["sat_id"]))
        p["gso_lon_deg"] = st.number_input("Longitude orbital GSO [graus]", value=float(p["gso_lon_deg"]))
        p["pol_rx"] = st.text_input("Polarização RX", value=str(p["pol_rx"]))
        p["t_sys_K"] = st.number_input("T_sys [K]", value=float(p["t_sys_K"]), min_value=1.0)
        p["f_rx_center_MHz"] = st.number_input("Frequência central RX [MHz]", value=float(p["f_rx_center_MHz"]))
        p["b_rx_Hz"] = st.number_input("Banda RX [Hz]", value=float(p["b_rx_Hz"]), min_value=1.0, step=1000000.0)
        p["l_rx_dB"] = st.number_input("Perdas RX [dB]", value=float(p["l_rx_dB"]))
        p["g_r_max_dBi"] = st.number_input("Ganho máximo RX [dBi]", value=float(p["g_r_max_dBi"]))
        p["eta_ap"] = st.number_input("Eficiência de abertura η_ap", value=float(p.get("eta_ap", 0.60)), min_value=0.01, max_value=1.0, step=0.01, format="%.2f")

        psi_b_auto_default = p.get("psi_b_deg") is None
        psi_b_auto = st.checkbox("Calcular psi_b automaticamente a partir de G_max e η_ap", value=psi_b_auto_default)
        if psi_b_auto:
            p["psi_b_deg"] = None
            st.caption(f"psi_b usado no padrão RX = {rx_psi_b_used_from_params(p):.3f}°")
        else:
            psi_b_initial = p.get("psi_b_deg")
            if psi_b_initial is None:
                psi_b_initial = rx_psi_b_used_from_params(p)
            p["psi_b_deg"] = st.number_input("Semi-largura de feixe psi_b [graus]", value=float(psi_b_initial), min_value=1e-6)

        p["ln_db"] = st.selectbox("ln_db", options=[-20.0, -25.0], index=0 if float(p["ln_db"]) == -20.0 else 1)
        p["lf_db"] = st.number_input("lf_db [dBi]", value=float(p["lf_db"]))
        p["single_entry_limit_i_over_n_dB"] = st.number_input(
            "Limite de I/N single-entry [dB]",
            value=float(p.get("single_entry_limit_i_over_n_dB", p["benchmark_i_over_n_dB"])),
        )
        p["aggregate_target_i_over_n_dB"] = st.number_input(
            "Alvo de I/N agregado [dB]",
            value=float(p.get("aggregate_target_i_over_n_dB", p["benchmark_i_over_n_dB"])),
        )
        p["benchmark_i_over_n_dB"] = float(p["aggregate_target_i_over_n_dB"])
        p["elev_min_deg"] = st.number_input("Elevação mínima adotada [graus]", value=float(p["elev_min_deg"]), min_value=0.0)
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
    tx_pattern = build_tx_pattern_from_params(params_tx_ui)

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
    tx_pattern = build_tx_pattern_from_params(params_tx_ui)

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
                "benchmark_i_over_n_dB": float(res.get("aggregate_target_i_over_n_dB", params_rx_ui["aggregate_target_i_over_n_dB"])),
                "atende_criterio": bool(
                    pd.notna(res["i_over_n_agg_total_dB"])
                    and (res["i_over_n_agg_total_dB"] <= float(res.get("aggregate_target_i_over_n_dB", params_rx_ui["aggregate_target_i_over_n_dB"])))
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


def plot_agregado_vs_benchmark(df_resultados: pd.DataFrame, df_agregado_total: pd.DataFrame, aggregate_target_i_over_n_dB: float):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty or df_agregado_total.empty:
        return None

    pior_individual_in = float(df_vis["i_over_n_dB"].max())
    agregado_in = float(df_agregado_total["i_over_n_agg_total_dB"].iloc[0])
    benchmark = float(aggregate_target_i_over_n_dB)

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
    g_dir_dBd = float(params_tx_ui["g_t_max_dBd"]) - float(params_tx_ui["Eh_dB"]) + ev_dB
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
    g_dir_dBd = float(params_tx_ui["g_t_max_dBd"]) - float(params_tx_ui["Eh_dB"]) + ev_dB

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
    rx_pattern = build_rx_pattern_from_params(params_rx_ui)
    psi_deg = np.asarray(rx_pattern["angle_deg"], dtype=float)
    g_r_dBi = np.asarray(rx_pattern["gain_dbi"], dtype=float)
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
    rx_pattern = build_rx_pattern_from_params(params_rx_ui)
    psi_deg = np.asarray(rx_pattern["angle_deg"], dtype=float)
    g_r_dBi = np.asarray(rx_pattern["gain_dbi"], dtype=float)

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
    if str(params_tx_ui.get("tx_input_mode", "potencia_tx")) == "erp_max_direta":
        st.caption("Entrada direta de ERP máxima. A potência TX equivalente é retrocalculada a partir das perdas e do ganho máximo.")
    else:
        st.caption("Calculada a partir da potência, perdas de linha e ganho máximo da antena.")

tab1, tab2, tab3, tab4 = st.tabs([
    "Cenário único",
    "Varredura de longitude GSO",
    "Diagramas das antenas",
    "Metodologia e ajuda",
])

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
        benchmark = float(params_rx_ui["aggregate_target_i_over_n_dB"])

        if agg_in is not None:
            if agg_in <= benchmark:
                st.success("O agregado atende ao alvo de I/N agregado.")
            else:
                st.error("O agregado excede o alvo de I/N agregado.")

        st.caption(
            f"Critérios em uso: single-entry = {float(params_rx_ui['single_entry_limit_i_over_n_dB']):.2f} dB; "
            f"agregado = {float(params_rx_ui['aggregate_target_i_over_n_dB']):.2f} dB."
        )

        st.subheader("Resultados por estação")

        df_view = formatar_resultados_para_exibicao(df_resultados)

        colunas_executivas = [
            "Município",
            "UF",
            "Frequência [MHz]",
            "Elevação [°]",
            "Ganho TX na direção do satélite [dBd]",
            "ERP na direção do satélite [kW]",
            "Potência interferente no satélite, I [dBW]",
            "Ruído no receptor, N [dBW]",
            "I/N [dB]",
            "Visível",
            "Observação",
        ]
        colunas_executivas = [c for c in colunas_executivas if c in df_view.columns]

        st.markdown("**Visão executiva**")
        st.dataframe(df_view[colunas_executivas], use_container_width=True)

        colunas_detalhadas = [
            "Município",
            "UF",
            "Banda TX [Hz]",
            "Banda RX [Hz]",
            "Banda sobreposta [Hz]",
            "Densidade de EIRP [dBW/Hz]",
            "Densidade interferente no satélite [dBW/Hz]",
            "Densidade de ruído, N0 [dBW/Hz]",
            "I0/N0 [dB]",
        ]
        colunas_detalhadas = [c for c in colunas_detalhadas if c in df_view.columns]

        with st.expander("Abrir grandezas espectrais e bandas", expanded=False):
            st.dataframe(df_view[colunas_detalhadas], use_container_width=True)

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

        fig4 = plot_agregado_vs_benchmark(
            df_resultados,
            df_agregado_total,
            float(params_rx_ui["aggregate_target_i_over_n_dB"]),
        )
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
    lon_min_deg = colA.number_input("Longitude mínima [graus]", value=float(GSO_LON_MIN_DEG))
    lon_max_deg = colB.number_input("Longitude máxima [graus]", value=float(GSO_LON_MAX_DEG))
    lon_step_deg = colC.number_input("Passo [graus]", value=float(GSO_LON_STEP_DEG), min_value=0.1)
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
        tx_pattern_current = build_tx_pattern_from_params(params_tx_ui)
        st.caption(r"Acima: ganho em escala linear. Abaixo: ganho em dB, usando o modelo analítico vertical $E_{TX}(\theta)=E_{elem}(\theta)\,AF_N(\theta)$." )

        fig_tv_lin = plot_diagrama_vertical_tv_linear(params_tx_ui, tx_pattern_current, df_resultados_pattern)
        st.pyplot(fig_tv_lin)

        fig_tv_db = plot_diagrama_vertical_tv_db(params_tx_ui, tx_pattern_current, df_resultados_pattern)
        st.pyplot(fig_tv_db)

        st.caption(
            f"HPBW do padrão TX selecionado: {float(tx_pattern_current['selected_hpbw_deg']):.2f}°. "
            f"q = {float(tx_pattern_current['q_element']):.4f}; d/λ = {float(tx_pattern_current['d_lambda']):.2f}; "
            f"pesos = {'binomial' if bool(tx_pattern_current['use_binomial']) else 'uniformes'}."
        )
        st.dataframe(pd.DataFrame(tx_pattern_current["calibration_report"]), use_container_width=True, hide_index=True)

    with col_sat:
        st.markdown("### Antena do satélite GSO")
        rx_pattern_current = build_rx_pattern_from_params(params_rx_ui)
        st.caption("Acima: ganho em escala linear. Abaixo: ganho em dB, conforme o envelope simplificado inspirado na ITU-R S.672-4.")

        fig_sat_lin = plot_diagrama_satelite_linear(params_rx_ui, df_resultados_pattern)
        st.pyplot(fig_sat_lin)

        fig_sat_db = plot_diagrama_satelite_db(params_rx_ui, df_resultados_pattern)
        st.pyplot(fig_sat_db)

        psi_b_source = "calculado" if rx_pattern_current["psi_b_deg_input"] is None else "explícito"
        st.caption(
            f"psi_b usado: {float(rx_pattern_current['psi_b_deg_used']):.3f}° ({psi_b_source}); "
            f"η_ap = {float(rx_pattern_current['eta_ap']):.2f}; "
            f"ln = {float(rx_pattern_current['ln_db']):.1f} dB; "
            f"lf = {float(rx_pattern_current['lf_db']):.1f} dBi."
        )

    st.info(
        "Se a simulação do cenário único já tiver sido rodada, os diagramas mostram também os pontos "
        "correspondentes às estações visíveis sobre as curvas."
    )

with tab4:
    st.subheader("Metodologia e ajuda")

    st.markdown("""
Este aplicativo realiza uma **estimativa da interferência agregada** de estações de TV digital em satélites geoestacionários, no sentido **Terra → espaço**.

Nesta aba, você encontra:
- um resumo da metodologia;
- as principais hipóteses adotadas;
- as limitações do modelo;
- e o conteúdo completo do `README.md`.
""")

    st.markdown("### Resumo rápido")

    st.markdown("""
**Cálculo por estação**
- calcula a geometria estação–satélite;
- calcula o ganho da antena de TV na direção do satélite;
- calcula o ganho RX do satélite;
- calcula a perda de espaço livre, com possibilidade de incluir uma perda adicional simplificada em baixa elevação;
- calcula a densidade espectral de potência interferente na entrada do receptor;
- integra essa densidade na banda efetivamente sobreposta entre transmissor e receptor;
- calcula o ruído térmico na banda do receptor;
- calcula $I/N$ e $\\Delta T/T$.

**Agregação**
- soma as contribuições das estações visíveis em unidade linear;
- converte o agregado para dBW;
- compara o resultado com o critério de proteção adotado.

**Varredura de longitude GSO**
- repete o cálculo para diferentes longitudes orbitais;
- permite identificar faixas de longitude que atendem ao critério de proteção.
""")

    st.markdown("### Hipóteses principais")

    st.markdown("""
- satélite GSO ideal;
- análise estática;
- foco em interferência agregada cocanal;
- ganho da antena de TV estimado a partir de um modelo analítico vertical com fator de elemento e fator de arranjo calibrado pelos valores de HPBW do datasheet;
- ganho RX do satélite obtido a partir de um modelo baseado na Recomendação ITU-R S.672-4;
- polarização tratada por perda global de mismatch;
- possibilidade de aplicar uma perda adicional em baixa elevação;
- cálculo da interferência a partir da densidade espectral de potência interferente integrada na banda efetivamente sobreposta;
- cálculo de ruído na banda do receptor.
""")

    st.markdown("### Limitações")

    st.markdown("""
- não há modelagem explícita separada de polarização H/V;
- o diagrama horizontal detalhado da antena de TV não é tratado explicitamente;
- o agregado total só é estritamente cocanal se todas as estações estiverem na mesma frequência;
- trata-se de uma ferramenta de estudo preliminar, não de uma análise regulatória definitiva.
""")

    st.markdown("### Observação sobre banda e cálculo de $I/N$")

    st.markdown("""
O modelo atual trata explicitamente:

- a largura de banda do transmissor, $B_{tx}$;
- a largura de banda do receptor, $B_{rx}$;
- e a banda efetivamente sobreposta, $B_{ov}$.

A potência interferente é obtida a partir da densidade espectral de potência interferente e da banda efetivamente sobreposta entre os dois sistemas.

O ruído térmico é calculado na banda do receptor:

$$
N = -228{,}6 + 10\\log_{10}(T_{sys}) + 10\\log_{10}(B_{rx})
$$

A densidade de ruído é:

$$
N_0 = -228{,}6 + 10\\log_{10}(T_{sys})
$$

Em termos gerais, a relação entre interferência e ruído pode ser escrita como:

$$
\\frac{I}{N} = \\frac{I_0}{N_0} \\cdot \\frac{B_{ov}}{B_{rx}}
$$

Assim, quando:

$$
B_{tx} = B_{rx}
$$

o modelo se reduz naturalmente ao caso cocanal homogêneo mais simples.
""")

    with st.expander("Abrir documentação completa (README.md)", expanded=False):
        st.markdown(carregar_readme_text())