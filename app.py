from pathlib import Path
import io
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from config.defaults import params_tx_default, params_rx_sat, tx_pattern, estacoes_exemplo
from core.budget import validar_estacoes, validar_tx_pattern, expandir_estacoes_com_defaults, calcular_interferencia_estacao
from core.aggregate import resumir_agregado_por_frequencia, resumir_agregado_total
from core.sweep import calcular_i_agg_total_e_in, build_longitude_grid, extrair_faixas_contiguas

st.set_page_config(page_title="Interferência agregada em satélite GSO", layout="wide")
st.title("Simulação de interferência agregada de estações de radiodifusão em satélite GSO")
# st.caption("Aplicativo Streamlit construído a partir da lógica dos scripts de cálculo e de varredura de longitude GSO.")


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=';', decimal='.', encoding='utf-8-sig').encode('utf-8-sig')


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
        p["benchmark_i_over_n_dB"] = st.number_input("I/N máximo de proteção[dB]", value=float(p["benchmark_i_over_n_dB"]))
        p["elev_min_deg"] = st.number_input("Elevação mínima adotada [graus]", value=float(p["elev_min_deg"]))
        p["apply_low_elevation_excess_loss"] = st.checkbox("Aplicar perda extra em baixa elevação", value=bool(p["apply_low_elevation_excess_loss"]))
    return p


def rodar_cenario(df_estacoes_edit, params_tx_ui, params_rx_ui):
    estacoes = df_estacoes_edit.to_dict(orient="records")
    validar_estacoes(estacoes)
    validar_tx_pattern(tx_pattern)
    estacoes_expandidas = expandir_estacoes_com_defaults(estacoes, params_tx_ui)
    resultados = [calcular_interferencia_estacao(estacao=e, params_rx_sat=params_rx_ui, tx_pattern=tx_pattern) for e in estacoes_expandidas]
    df_estacoes = pd.DataFrame(estacoes_expandidas)
    df_resultados = pd.DataFrame(resultados)
    df_resultados = df_resultados.sort_values(by=["visible_flag", "i_dBW"], ascending=[False, False], na_position="last").reset_index(drop=True)
    df_agregado_freq = resumir_agregado_por_frequencia(df_resultados)
    df_agregado_total = resumir_agregado_total(df_resultados)
    return df_estacoes, df_resultados, df_agregado_freq, df_agregado_total


def plot_top_in(df_resultados: pd.DataFrame):
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return None
    df_top = df_vis.sort_values(by="i_over_n_dB", ascending=False).head(min(10, len(df_vis))).iloc[::-1].copy()
    labels = [f"{m}/{uf}" for m, uf in zip(df_top["municipio"], df_top["uf"])]
    fig, ax = plt.subplots(figsize=(10, max(6, 0.42*len(df_top)+1.5)))
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
    df_top = df_vis.sort_values(by="i_dBW", ascending=False).head(min(10, len(df_vis))).iloc[::-1].copy()
    labels = [f"{m}/{uf}" for m, uf in zip(df_top["municipio"], df_top["uf"])]
    fig, ax = plt.subplots(figsize=(10, max(6, 0.42*len(df_top)+1.5)))
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
    df_ord["i_agg_cumul_dBW"] = df_ord["i_agg_cumul_W"].apply(lambda x: -float('inf') if x <= 0 else 10.0 * np.log10(x))
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


def rodar_varredura(estacoes_df, params_tx_ui, params_rx_ui, lon_min_deg, lon_max_deg, lon_step_deg, g_r_list):
    estacoes = estacoes_df.to_dict(orient="records")
    validar_estacoes(estacoes)
    validar_tx_pattern(tx_pattern)
    estacoes_expandidas = expandir_estacoes_com_defaults(estacoes, params_tx_ui)

    lons = build_longitude_grid(lon_min_deg, lon_max_deg, lon_step_deg)
    rows = []
    for g_r in g_r_list:
        for lon in lons:
            res = calcular_i_agg_total_e_in(estacoes_expandidas, params_rx_ui, tx_pattern, gso_lon_deg=float(lon), g_r_max_dBi=float(g_r))
            rows.append({
                "gso_lon_deg": float(lon),
                "g_r_max_dBi": float(g_r),
                "n_estacoes_visiveis": res["n_estacoes_visiveis"],
                "i_agg_total_dBW": res["i_agg_total_dBW"],
                "i_over_n_agg_total_dB": res["i_over_n_agg_total_dB"],
                "benchmark_i_over_n_dB": float(params_rx_ui["benchmark_i_over_n_dB"]),
                "atende_criterio": bool(pd.notna(res["i_over_n_agg_total_dB"]) and (res["i_over_n_agg_total_dB"] <= float(params_rx_ui["benchmark_i_over_n_dB"]))),
            })
    df_scan = pd.DataFrame(rows)
    df_ranges = extrair_faixas_contiguas(df_scan, lon_step_deg)
    return df_scan, df_ranges


def plot_varredura(df_scan: pd.DataFrame):
    if df_scan.empty:
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    for g_r, grupo in df_scan.groupby("g_r_max_dBi", sort=True):
        ax.plot(grupo["gso_lon_deg"], grupo["i_over_n_agg_total_dB"], label=f"g_r_max={g_r:.1f} dBi")
    ax.axhline(float(df_scan["benchmark_i_over_n_dB"].iloc[0]), linestyle="--")
    ax.set_xlabel("Longitude GSO [graus]")
    ax.set_ylabel("I/N agregado total [dB]")
    ax.set_title("Varredura de longitude orbital GSO")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


params_tx_ui = montar_params_tx_ui()
params_rx_ui = montar_params_rx_ui()

tab1, tab2 = st.tabs(["Cenário único", "Varredura de longitude GSO"])

with tab1:
    st.subheader("Estações de radiodifusão")
    df_estacoes_edit = st.data_editor(pd.DataFrame(estacoes_exemplo), num_rows="dynamic", use_container_width=True)

    if st.button("Rodar simulação", type="primary"):
        try:
            df_estacoes, df_resultados, df_agregado_freq, df_agregado_total = rodar_cenario(df_estacoes_edit, params_tx_ui, params_rx_ui)

            st.success("Simulação concluída.")

            col1, col2, col3 = st.columns(3)
            col1.metric("Estações visíveis", int(df_agregado_total["n_estacoes_visiveis"].iloc[0]))
            col2.metric("I agregado total [dBW]", f"{df_agregado_total['i_agg_total_dBW'].iloc[0]:.2f}")
            col3.metric("I/N agregado [dB]", f"{df_agregado_total['i_over_n_agg_total_dB'].iloc[0]:.2f}" if pd.notna(df_agregado_total['i_over_n_agg_total_dB'].iloc[0]) else "nan")

            agg_in = float(df_agregado_total["i_over_n_agg_total_dB"].iloc[0]) if pd.notna(df_agregado_total["i_over_n_agg_total_dB"].iloc[0]) else None
            benchmark = float(params_rx_ui["benchmark_i_over_n_dB"])
            if agg_in is not None:
                if agg_in <= benchmark:
                    st.success("O agregado atende ao benchmark preliminar.")
                else:
                    st.error("O agregado excede o benchmark preliminar.")

            st.subheader("Resultados por estação")
            st.dataframe(df_resultados, use_container_width=True)

            st.subheader("Resumo agregado por frequência")
            st.dataframe(df_agregado_freq, use_container_width=True)

            st.subheader("Resumo agregado total")
            st.dataframe(df_agregado_total, use_container_width=True)

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

            st.download_button("Baixar resultados por estação (CSV)", dataframe_to_csv_bytes(df_resultados), file_name="resultados_por_estacao.csv", mime="text/csv")
            st.download_button("Baixar resumo agregado por frequência (CSV)", dataframe_to_csv_bytes(df_agregado_freq), file_name="resumo_agregado_por_frequencia.csv", mime="text/csv")
            st.download_button("Baixar resumo agregado total (CSV)", dataframe_to_csv_bytes(df_agregado_total), file_name="resumo_agregado_total.csv", mime="text/csv")

        except Exception as e:
            st.exception(e)

with tab2:
    st.subheader("Estações usadas na varredura")
    df_estacoes_scan = st.data_editor(pd.DataFrame(estacoes_exemplo), num_rows="dynamic", use_container_width=True, key="scan_editor")

    colA, colB, colC = st.columns(3)
    lon_min_deg = colA.number_input("Longitude mínima [graus]", value=-141.0)
    lon_max_deg = colB.number_input("Longitude máxima [graus]", value=46.0)
    lon_step_deg = colC.number_input("Passo [graus]", value=1.0, min_value=0.1)
    g_r_list_str = st.text_input("Lista de ganhos RX máximos [dBi]", value="18,23,35")

    if st.button("Rodar varredura GSO"):
        try:
            g_r_list = [float(x.strip()) for x in g_r_list_str.split(",") if x.strip()]
            df_scan, df_ranges = rodar_varredura(df_estacoes_scan, params_tx_ui, params_rx_ui, lon_min_deg, lon_max_deg, lon_step_deg, g_r_list)
            st.success("Varredura concluída.")
            st.dataframe(df_scan, use_container_width=True)
            st.subheader("Faixas contíguas que atendem ao critério")
            st.dataframe(df_ranges, use_container_width=True)
            fig_scan = plot_varredura(df_scan)
            if fig_scan is not None:
                st.pyplot(fig_scan)
            st.download_button("Baixar varredura (CSV)", dataframe_to_csv_bytes(df_scan), file_name="varredura_longitude_gso.csv", mime="text/csv")
            st.download_button("Baixar faixas contíguas (CSV)", dataframe_to_csv_bytes(df_ranges), file_name="faixas_contiguas_gso.csv", mime="text/csv")
        except Exception as e:
            st.exception(e)
