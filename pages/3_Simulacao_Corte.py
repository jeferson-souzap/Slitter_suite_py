import streamlit as st
import pandas as pd
from datetime import datetime

from core.plano_corte_engine import (
    init_plano_corte, get_config, banco_matrizes_existe,
    get_espessuras, get_tipos_material, get_larguras,
    carregar_matrizes,
    simular_com_fixos,
    calcular_peso_medio_bobina, calcular_kg_combinacao, calcular_kg_matriz,
    salvar_hist_simulacao, get_hist_simulacao, get_hist_simulacao_itens,
    deletar_hist_simulacao, limpar_hist_simulacao,
)

st.set_page_config(page_title="Simulação de Corte | Slitter Suite", layout="wide")

init_plano_corte()

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; color: #888; }
.section-title {
    font-size: 0.82rem; font-weight: 600; color: #555;
    text-transform: uppercase; letter-spacing: .06em;
    margin: 0.8rem 0 .3rem;
}
.tag-fixo {
    display: inline-block;
    background: rgba(232,160,32,0.15);
    color: #d4920f;
    border: 1px solid rgba(232,160,32,0.4);
    border-radius: 3px;
    padding: 1px 8px;
    font-size: 0.75rem;
    font-weight: 600;
}
.tag-sug {
    display: inline-block;
    background: rgba(39,174,96,0.12);
    color: #1e9660;
    border: 1px solid rgba(39,174,96,0.35);
    border-radius: 3px;
    padding: 1px 8px;
    font-size: 0.75rem;
    font-weight: 600;
}
.linha-total { font-size: 0.85rem; color: #555; padding: 0.25rem 0; }
.linha-total b { color: #222; }
</style>
""", unsafe_allow_html=True)


# ── Cabeçalho ─────────────────────────────────────────────────────────────────

st.title("Simulação de Corte")
st.caption("Defina os itens fixos e o sistema sugere quais matrizes completam cada largura de bobina.")

if not banco_matrizes_existe():
    st.warning(
        "Nenhuma matriz importada. "
        "Acesse **⚙️ Configuração → Plano de Corte** para importar o banco de matrizes.",
        icon="⚠️",
    )
    st.stop()

espessuras = get_espessuras()
if not espessuras:
    st.warning("Banco de matrizes vazio. Acesse **⚙️ Configuração → Plano de Corte**.", icon="⚠️")
    st.stop()


# ── Filtros de material ───────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown('<div class="section-title">Material</div>', unsafe_allow_html=True)

    col_esp, col_tipo, col_peso, col_bob = st.columns([1, 1, 1, 1])
    with col_esp:
        espessura = st.selectbox("Espessura (mm)", options=get_espessuras(), key="sim_esp")
    with col_tipo:
        tipo_material = st.selectbox("Tipo de Material", options=get_tipos_material(espessura), key="sim_tipo")
    with col_peso:
        peso_total = st.number_input(
            "Peso total do lote (kg)",
            value=int(get_config("peso_medio_bob_pad")),
            min_value=1_000, max_value=500_000, step=500,
        )
    with col_bob:
        qtd_bobinas = st.number_input(
            "Quantidade de bobinas",
            value=int(get_config("qtd_bobinas_pad")),
            min_value=1, max_value=100,
        )

# ── Resetar lista de fixos quando filtro muda ─────────────────────────────────
_filtro_atual = f"{espessura}|{tipo_material}"
if st.session_state.get("sim_filtro") != _filtro_atual:
    st.session_state["sim_filtro"] = _filtro_atual
    st.session_state["sim_fixos"]  = [{"n_cortes": 1}]
    st.session_state.pop("sim_resultado", None)

if "sim_fixos" not in st.session_state:
    st.session_state["sim_fixos"] = [{"n_cortes": 1}]


# ── Carrega matrizes disponíveis ──────────────────────────────────────────────

df_matrizes = carregar_matrizes()
mask_mat    = (df_matrizes["Espessura"] == espessura) & (df_matrizes["Tipo de material"] == tipo_material)
df_mat_fil  = (
    df_matrizes[mask_mat]
    .groupby("Matriz")["Desenvolvimento"]
    .mean()
    .reset_index()
    .rename(columns={"Desenvolvimento": "Dev_mm"})
    .sort_values("Dev_mm", ascending=False)
    .reset_index(drop=True)
)

if df_mat_fil.empty:
    st.warning("Nenhuma matriz encontrada para espessura + tipo selecionados.")
    st.stop()

opcoes    = df_mat_fil["Matriz"].tolist()
dev_map   = dict(zip(df_mat_fil["Matriz"], df_mat_fil["Dev_mm"]))
label_map = {m: f"{m}  ({dev_map[m]:.1f} mm)" for m in opcoes}


# ── Itens Fixos ───────────────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown(
        '<div class="section-title">Itens Fixos — o que você já sabe que vai cortar</div>',
        unsafe_allow_html=True,
    )

    hc1, hc2, hc3, hc4, _ = st.columns([4, 1.6, 1.2, 1.6, 0.45])
    hc1.caption("Matriz")
    hc2.caption("Desenv. (mm)")
    hc3.caption("Nº Cortes")
    hc4.caption("Subtotal (mm)")

    to_remove      = None
    soma_acumulada = 0.0

    for i, item in enumerate(st.session_state["sim_fixos"]):
        c1, c2, c3, c4, c5 = st.columns([4, 1.6, 1.2, 1.6, 0.45])

        with c1:
            saved = item.get("matriz")
            idx   = opcoes.index(saved) if saved in opcoes else 0
            mat   = st.selectbox(
                "mat", options=opcoes, format_func=lambda m: label_map[m],
                index=idx, key=f"sim_mat_{i}", label_visibility="collapsed",
            )
            st.session_state["sim_fixos"][i]["matriz"] = mat

        dev = dev_map.get(mat, 0.0)
        c2.markdown(f"**{dev:.3f}**")

        with c3:
            n = st.number_input(
                "n", value=int(item.get("n_cortes", 1)),
                min_value=1, max_value=99, key=f"sim_n_{i}",
                label_visibility="collapsed",
            )
            st.session_state["sim_fixos"][i]["n_cortes"] = n

        subtotal        = dev * n
        soma_acumulada += subtotal
        c4.markdown(f"**{subtotal:.3f}**")

        with c5:
            if len(st.session_state["sim_fixos"]) > 1:
                if st.button("✕", key=f"sim_rem_{i}", help="Remover linha"):
                    to_remove = i

    if to_remove is not None:
        st.session_state["sim_fixos"].pop(to_remove)
        st.rerun()

    st.divider()
    _, _, _, tc_val, _ = st.columns([4, 1.6, 1.2, 1.6, 0.45])
    tc_val.markdown(
        f'<div class="linha-total">Total fixo: <b>{soma_acumulada:.3f} mm</b></div>',
        unsafe_allow_html=True,
    )


# ── Opções da busca ───────────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown('<div class="section-title">Opções da busca</div>', unsafe_allow_html=True)

    oc1, oc2, oc3 = st.columns([1, 1, 1])
    with oc1:
        max_comp_edit = st.number_input(
            "Máx. matrizes sugeridas por combinação",
            value=int(get_config("max_comp_na_combo")),
            min_value=1, max_value=8,
        )
    with oc2:
        usa_limite   = st.checkbox("Limitar total de cortes", value=False)
        limite_corte = st.number_input(
            "Limite de cortes", value=10, min_value=1, max_value=50,
            disabled=not usa_limite,
        )
    with oc3:
        largura_opc = ["— todas as larguras —"] + get_larguras()
        largura_sel = st.selectbox("Testar apenas esta largura", options=largura_opc)

col_add, col_sim = st.columns([1, 3])
with col_add:
    if st.button("+ Adicionar Item Fixo", use_container_width=True):
        st.session_state["sim_fixos"].append({"n_cortes": 1})
        st.rerun()
with col_sim:
    simular_btn = st.button("Simular", type="primary", use_container_width=True)


# ── Execução ──────────────────────────────────────────────────────────────────

if simular_btn:
    itens = [
        {"matriz": item["matriz"], "n_cortes": int(item["n_cortes"])}
        for item in st.session_state["sim_fixos"]
        if item.get("matriz")
    ]
    if not itens:
        st.error("Adicione ao menos um item fixo antes de simular.")
        st.stop()

    larguras_forcar = [largura_sel] if isinstance(largura_sel, int) else None
    limite_final    = limite_corte if usa_limite else None

    with st.spinner("Buscando combinações..."):
        df_sim = simular_com_fixos(
            df=df_matrizes, espessura=espessura, tipo_material=tipo_material,
            itens_fixos=itens, limite_cortes=limite_final,
            larguras=larguras_forcar, max_complementares=int(max_comp_edit),
        )

    st.session_state["sim_resultado"] = df_sim
    st.session_state["sim_params"]    = {
        "espessura": espessura, "tipo_material": tipo_material,
        "peso_total": peso_total, "qtd_bobinas": qtd_bobinas,
        "soma_fixa": soma_acumulada, "limite": limite_final,
    }


# ── Resultados ────────────────────────────────────────────────────────────────

if "sim_resultado" in st.session_state:
    df_res = st.session_state["sim_resultado"]
    p      = st.session_state["sim_params"]

    with st.container(border=True):
        st.markdown('<div class="section-title">Resultados</div>', unsafe_allow_html=True)

        if df_res.empty:
            st.warning(
                "Nenhuma combinação encontrada. "
                "Tente aumentar o máx. de matrizes sugeridas ou remover o limite de cortes."
            )
        else:
            peso_medio = calcular_peso_medio_bobina(p["peso_total"], p["qtd_bobinas"])

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Combinações",       len(df_res))
            mc2.metric("✅ Válidas",          int((df_res["Status"] == "✓ Válida").sum()))
            mc3.metric("Fora da regra",      int((df_res["Status"] != "✓ Válida").sum()))
            mc4.metric("Larguras testadas",  int(df_res["Largura_bobina"].nunique()))

            st.divider()

            aba_combos, aba_detalhes = st.tabs(["Combinações sugeridas", "Detalhes"])

            with aba_combos:
                df_disp = df_res[["Largura_bobina", "Combinacao", "Total_cortes",
                                   "Soma_cortes_mm", "Perda_mm", "Perda_pct", "Status"]].copy()
                df_disp["KG"] = df_res.apply(
                    lambda r: f"{calcular_kg_combinacao(r['Detalhes'], peso_medio, r['Largura_bobina'], p['qtd_bobinas']):,.0f}",
                    axis=1,
                )
                df_disp["Perda_pct"]      = df_disp["Perda_pct"].map(lambda x: f"{x:.4f}%")
                df_disp["Perda_mm"]       = df_disp["Perda_mm"].map(lambda x: f"{x:.3f}")
                df_disp["Soma_cortes_mm"] = df_disp["Soma_cortes_mm"].map(lambda x: f"{x:.3f}")
                df_disp = df_disp.rename(columns={
                    "Largura_bobina": "Largura (mm)", "Combinacao": "Combinação",
                    "Total_cortes": "Total Cortes", "Soma_cortes_mm": "Soma (mm)",
                    "Perda_mm": "Perda (mm)", "Perda_pct": "Perda (%)", "KG": "Qtd. KG",
                })
                st.dataframe(
                    df_disp, use_container_width=True, hide_index=True,
                    column_config={
                        "Largura (mm)": st.column_config.NumberColumn("Largura (mm)", width="small"),
                        "Status":       st.column_config.TextColumn("Status", width="small"),
                        "Total Cortes": st.column_config.NumberColumn("Total Cortes", width="small"),
                    },
                )

            with aba_detalhes:
                linhas = []
                for i, row in df_res.iterrows():
                    larg = row["Largura_bobina"]
                    for det in row["Detalhes"]:
                        kg = calcular_kg_matriz(
                            peso_medio, larg,
                            det["N_cortes"], det["Desenvolvimento_mm"], p["qtd_bobinas"],
                        )
                        linhas.append({
                            "# Combo":              i + 1,
                            "Largura (mm)":         larg,
                            "Papel":                det.get("Papel", ""),
                            "Código":               det.get("Codigo", ""),
                            "Matriz":               det["Matriz"],
                            "Espessura (mm)":       p["espessura"],
                            "Tipo":                 det.get("Tipo_material", ""),
                            "Produto":              det.get("Descri_produto", ""),
                            "Desenvolvimento (mm)": det["Desenvolvimento_mm"],
                            "Nº Cortes":            det["N_cortes"],
                            "Qtd. KG":              round(kg, 2),
                        })
                st.dataframe(
                    pd.DataFrame(linhas), use_container_width=True, hide_index=True,
                    column_config={
                        "# Combo":              st.column_config.NumberColumn("# Combo", width="small"),
                        "Largura (mm)":         st.column_config.NumberColumn("Largura (mm)", width="small"),
                        "Papel":                st.column_config.TextColumn("Papel", width="small"),
                        "Nº Cortes":            st.column_config.NumberColumn("Nº Cortes", width="small"),
                        "Espessura (mm)":       st.column_config.NumberColumn("Esp. (mm)", format="%.2f"),
                        "Desenvolvimento (mm)": st.column_config.NumberColumn("Desenv. (mm)", format="%.3f"),
                        "Qtd. KG":              st.column_config.NumberColumn("Qtd. KG", format="%.2f"),
                    },
                )
                st.markdown(
                    '<span class="tag-fixo">FIXO</span> item definido pelo usuário &nbsp;&nbsp;'
                    '<span class="tag-sug">SUGERIDO</span> complementar encontrado pelo sistema',
                    unsafe_allow_html=True,
                )

            # ── Salvar no histórico ───────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("Salvar plano escolhido no histórico", expanded=False):
                opcoes_combo = {}
                for i, row in df_res.iterrows():
                    kg_tot = calcular_kg_combinacao(
                        row["Detalhes"], peso_medio, row["Largura_bobina"], p["qtd_bobinas"]
                    )
                    opcoes_combo[i + 1] = (
                        f"#{i+1}  │  {row['Largura_bobina']} mm  │  "
                        f"perda {row['Perda_pct']:.4f}%  │  {row['Status']}  │  {kg_tot:,.0f} kg"
                    )

                col_sel, col_obs = st.columns([1, 2])
                with col_sel:
                    combo_num = st.selectbox(
                        "Combinação escolhida",
                        options=list(opcoes_combo.keys()),
                        format_func=lambda k: opcoes_combo[k],
                        key="sim_sel_combo",
                    )
                with col_obs:
                    obs = st.text_input(
                        "Observação (opcional)",
                        placeholder="Ex.: aprovado pelo supervisor, OP-2025-001...",
                        key="sim_obs",
                    )

                row_sel   = df_res.iloc[combo_num - 1]
                larg_sel  = row_sel["Largura_bobina"]

                itens_prev = []
                for det in row_sel["Detalhes"]:
                    kg_i = calcular_kg_matriz(
                        peso_medio, larg_sel,
                        det["N_cortes"], det["Desenvolvimento_mm"], p["qtd_bobinas"],
                    )
                    itens_prev.append({
                        "papel":              det.get("Papel", ""),
                        "matriz":             det["Matriz"],
                        "codigo":             det.get("Codigo", ""),
                        "tipo_material":      det.get("Tipo_material", ""),
                        "descricao":          det.get("Descri_produto", ""),
                        "espessura":          p["espessura"],
                        "desenvolvimento_mm": round(det["Desenvolvimento_mm"], 4),
                        "n_cortes":           int(det["N_cortes"]),
                        "subtotal_mm":        round(det["Subtotal_mm"], 4),
                        "qtd_kg":             round(kg_i, 4),
                    })

                df_prev = pd.DataFrame(itens_prev)[
                    ["papel", "matriz", "codigo", "desenvolvimento_mm", "n_cortes", "subtotal_mm", "qtd_kg"]
                ].rename(columns={
                    "papel": "Papel", "matriz": "Matriz", "codigo": "Código",
                    "desenvolvimento_mm": "Desenv. (mm)", "n_cortes": "Nº Cortes",
                    "subtotal_mm": "Subtotal (mm)", "qtd_kg": "KG",
                })

                st.caption(
                    f"Combinação #{combo_num}  —  Largura {larg_sel} mm  —  "
                    f"Perda {row_sel['Perda_pct']:.4f}%  —  {row_sel['Status']}"
                )
                st.dataframe(
                    df_prev, use_container_width=True, hide_index=True,
                    column_config={
                        "Papel":        st.column_config.TextColumn("Papel", width="small"),
                        "Nº Cortes":    st.column_config.NumberColumn("Nº Cortes", width="small"),
                        "Desenv. (mm)": st.column_config.NumberColumn("Desenv. (mm)", format="%.3f"),
                        "Subtotal (mm)":st.column_config.NumberColumn("Subtotal (mm)", format="%.3f"),
                        "KG":           st.column_config.NumberColumn("KG", format="%.4f"),
                    },
                )

                kg_total_prev = sum(i["qtd_kg"] for i in itens_prev)
                st.markdown(
                    f'<div class="linha-total">'
                    f'KG total: <b>{kg_total_prev:,.2f} kg</b> &nbsp;|&nbsp; '
                    f'Perda: <b>{row_sel["Perda_mm"]:.3f} mm ({row_sel["Perda_pct"]:.4f}%)</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Salvar no Histórico", type="primary", key="sim_btn_salvar"):
                    num_fixos     = sum(1 for d in row_sel["Detalhes"] if d.get("Papel") == "FIXO")
                    num_sugeridos = sum(1 for d in row_sel["Detalhes"] if d.get("Papel") == "SUGERIDO")
                    novo_id = salvar_hist_simulacao({
                        "espessura": p["espessura"], "tipo_material": p["tipo_material"],
                        "largura_bobina": int(larg_sel), "combinacao": row_sel["Combinacao"],
                        "total_cortes": int(row_sel["Total_cortes"]),
                        "soma_cortes_mm": float(row_sel["Soma_cortes_mm"]),
                        "perda_mm": float(row_sel["Perda_mm"]),
                        "perda_pct": float(row_sel["Perda_pct"]),
                        "qtd_kg_total": round(kg_total_prev, 4),
                        "status": row_sel["Status"], "qtd_bobinas": int(p["qtd_bobinas"]),
                        "peso_lote_kg": float(p["peso_total"]),
                        "num_fixos": num_fixos, "num_sugeridos": num_sugeridos, "observacao": obs,
                    }, itens_prev)
                    st.success(f"Plano #{combo_num} salvo no histórico com ID {novo_id}.")
                    st.rerun()


# ── Histórico de Simulações ───────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<div class="section-title">Histórico de Simulações Salvas</div>', unsafe_allow_html=True)

    df_hist = get_hist_simulacao()

    if df_hist.empty:
        st.info("Nenhuma simulação salva ainda. Use **Salvar no Histórico** acima.")
    else:
        df_hd = df_hist[[
            "id", "salvo_em", "espessura", "tipo_material", "largura_bobina",
            "total_cortes", "perda_mm", "perda_pct", "qtd_kg_total",
            "num_fixos", "num_sugeridos", "status", "qtd_bobinas", "peso_lote_kg", "observacao",
        ]].rename(columns={
            "id": "ID", "salvo_em": "Salvo em", "espessura": "Esp. (mm)",
            "tipo_material": "Tipo", "largura_bobina": "Largura (mm)",
            "total_cortes": "Total Cortes", "perda_mm": "Perda (mm)",
            "perda_pct": "Perda (%)", "qtd_kg_total": "KG Total",
            "num_fixos": "Itens Fixos", "num_sugeridos": "Sugeridos",
            "status": "Status", "qtd_bobinas": "Bobinas",
            "peso_lote_kg": "Peso Lote (kg)", "observacao": "Observação",
        })
        st.dataframe(
            df_hd, use_container_width=True, hide_index=True,
            column_config={
                "ID":             st.column_config.NumberColumn("ID", width="small"),
                "Esp. (mm)":      st.column_config.NumberColumn("Esp. (mm)", format="%.2f"),
                "Perda (mm)":     st.column_config.NumberColumn("Perda (mm)", format="%.3f"),
                "Perda (%)":      st.column_config.NumberColumn("Perda (%)", format="%.4f"),
                "KG Total":       st.column_config.NumberColumn("KG Total", format="%.2f"),
                "Peso Lote (kg)": st.column_config.NumberColumn("Peso Lote (kg)", format="%.0f"),
                "Status":         st.column_config.TextColumn("Status", width="small"),
                "Itens Fixos":    st.column_config.NumberColumn("Fixos", width="small"),
                "Sugeridos":      st.column_config.NumberColumn("Sugeridos", width="small"),
            },
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">Itens detalhados de um plano salvo</div>', unsafe_allow_html=True)

        ids_disponiveis = df_hist["id"].tolist()
        col_id, _ = st.columns([1, 3])
        with col_id:
            id_detalhe = st.selectbox(
                "Selecionar plano (ID)",
                options=ids_disponiveis,
                format_func=lambda i: (
                    f"ID {i}  —  "
                    + df_hist.loc[df_hist["id"] == i, "salvo_em"].iloc[0]
                    + "  —  "
                    + df_hist.loc[df_hist["id"] == i, "tipo_material"].iloc[0]
                ),
                key="hist_id_det",
            )

        df_itens = get_hist_simulacao_itens(id_detalhe)
        if not df_itens.empty:
            row_h = df_hist[df_hist["id"] == id_detalhe].iloc[0]
            st.caption(
                f"ID {id_detalhe}  —  {row_h['salvo_em']}  —  "
                f"{row_h['espessura']} mm  —  {row_h['tipo_material']}  —  "
                f"Largura {row_h['largura_bobina']} mm  —  "
                f"Perda {row_h['perda_pct']:.4f}%  —  {row_h['status']}"
            )
            if row_h["observacao"]:
                st.caption(f"Obs.: {row_h['observacao']}")

            st.dataframe(
                df_itens[[
                    "papel", "matriz", "codigo", "tipo_material", "descricao",
                    "espessura", "desenvolvimento_mm", "n_cortes", "subtotal_mm", "qtd_kg",
                ]].rename(columns={
                    "papel": "Papel", "matriz": "Matriz", "codigo": "Código",
                    "tipo_material": "Tipo", "descricao": "Produto",
                    "espessura": "Esp. (mm)", "desenvolvimento_mm": "Desenv. (mm)",
                    "n_cortes": "Nº Cortes", "subtotal_mm": "Subtotal (mm)", "qtd_kg": "Qtd. KG",
                }),
                use_container_width=True, hide_index=True,
                column_config={
                    "Papel":        st.column_config.TextColumn("Papel", width="small"),
                    "Esp. (mm)":    st.column_config.NumberColumn("Esp. (mm)", format="%.2f"),
                    "Desenv. (mm)": st.column_config.NumberColumn("Desenv. (mm)", format="%.3f"),
                    "Subtotal (mm)":st.column_config.NumberColumn("Subtotal (mm)", format="%.3f"),
                    "Qtd. KG":      st.column_config.NumberColumn("Qtd. KG", format="%.4f"),
                    "Nº Cortes":    st.column_config.NumberColumn("Nº Cortes", width="small"),
                },
            )
            total_kg_itens = df_itens["qtd_kg"].sum()
            st.markdown(
                f'<div class="linha-total">'
                f'KG total: <b>{total_kg_itens:,.4f} kg</b> &nbsp;|&nbsp; '
                f'Total cortes: <b>{row_h["total_cortes"]}</b> &nbsp;|&nbsp; '
                f'Fixos: <b>{row_h["num_fixos"]}</b>  Sugeridos: <b>{row_h["num_sugeridos"]}</b>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_del, col_limpar, _ = st.columns([1, 1, 4])
        with col_del:
            id_deletar = st.selectbox(
                "Excluir registro (ID)", options=ids_disponiveis,
                format_func=lambda i: f"ID {i}", key="hist_id_del",
            )
            if st.button("Excluir registro", key="btn_del_sim"):
                deletar_hist_simulacao(id_deletar)
                st.success(f"ID {id_deletar} excluído.")
                st.rerun()
        with col_limpar:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Limpar histórico", key="btn_limpar_sim"):
                limpar_hist_simulacao()
                st.success("Histórico limpo.")
                st.rerun()

st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
