import numpy as np
import pandas as pd
from .budget import W_to_dBW


def resumir_agregado_por_frequencia(df_resultados: pd.DataFrame) -> pd.DataFrame:
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return pd.DataFrame()

    linhas = []
    for freq_mhz, grupo in df_vis.groupby("frequencia_MHz", dropna=False):
        i_agg_W = grupo["i_W"].sum()
        i_agg_dBW = W_to_dBW(i_agg_W)
        n_dBW = float(grupo["n_dBW"].iloc[0])
        i_over_n_agg_dB = i_agg_dBW - n_dBW
        delta_t_over_t_agg_pct = 100.0 * (10.0 ** (i_over_n_agg_dB / 10.0))
        idx_pior = grupo["i_dBW"].idxmax()
        pior = grupo.loc[idx_pior]
        linhas.append({
            "frequencia_MHz": freq_mhz,
            "n_estacoes_no_grupo": int(len(grupo)),
            "i_agg_W": i_agg_W,
            "i_agg_dBW": i_agg_dBW,
            "n_dBW": n_dBW,
            "i_over_n_agg_dB": i_over_n_agg_dB,
            "delta_t_over_t_agg_pct": delta_t_over_t_agg_pct,
            "pior_estacao_municipio": pior["municipio"],
            "pior_estacao_uf": pior["uf"],
            "pior_estacao_i_dBW": pior["i_dBW"],
        })
    return pd.DataFrame(linhas).sort_values(by="frequencia_MHz").reset_index(drop=True)


def resumir_agregado_total(df_resultados: pd.DataFrame) -> pd.DataFrame:
    df_vis = df_resultados[df_resultados["visible_flag"]].copy()
    if df_vis.empty:
        return pd.DataFrame([
            {
                "n_estacoes_visiveis": 0,
                "i_agg_total_W": 0.0,
                "i_agg_total_dBW": -np.inf,
                "n_dBW": np.nan,
                "i_over_n_agg_total_dB": np.nan,
                "delta_t_over_t_agg_total_pct": np.nan,
                "observacao": "Nenhuma estação considerada visível no estudo.",
            }
        ])

    i_agg_total_W = df_vis["i_W"].sum()
    i_agg_total_dBW = W_to_dBW(i_agg_total_W)
    n_dBW = float(df_vis["n_dBW"].iloc[0])
    i_over_n_agg_total_dB = i_agg_total_dBW - n_dBW
    delta_t_over_t_agg_total_pct = 100.0 * (10.0 ** (i_over_n_agg_total_dB / 10.0))

    return pd.DataFrame([
        {
            "n_estacoes_visiveis": int(len(df_vis)),
            "i_agg_total_W": i_agg_total_W,
            "i_agg_total_dBW": i_agg_total_dBW,
            "n_dBW": n_dBW,
            "i_over_n_agg_total_dB": i_over_n_agg_total_dB,
            "delta_t_over_t_agg_total_pct": delta_t_over_t_agg_total_pct,
            "observacao": "Cenário cocanal: soma linear de todas as contribuições consideradas visíveis.",
        }
    ])
