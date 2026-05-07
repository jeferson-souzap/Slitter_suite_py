import io
import socket
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path

from core.import_engine import (
    DB_PATH, get_metadata, calcular_necessidade_prod,
    get_configuracao,
)

st.set_page_config(page_title="Necessidade de Produção", layout="wide")

# ── Estilos ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; color: #888; }
.card-programar [data-testid="stMetricValue"] { color: #e74c3c; }
.card-ok       [data-testid="stMetricValue"] { color: #27ae60; }
.section-title { font-size: 0.85rem; font-weight: 600; color: #555;
                 text-transform: uppercase; letter-spacing: .06em;
                 margin: 1rem 0 .4rem; }
div[data-testid="stDataFrameResizable"] { border: 1px solid #e0e0e0; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Labels amigáveis ──────────────────────────────────────────────────────────

LABELS_NEC = {
    "ordem":              "Ordem",
    "maquina":            "Máquina",
    "descricao_pai":      "Prod. Final",
    "material":           "Material",
    "descricao":          "Fita",
    "espessura":          "Esp. (mm)",
    "largura":            "Larg. (mm)",
    "tipo_aco":           "Tipo Aço",
    "tipo_material":      "Tipo Mat.",
    "matriz":             "Matriz",
    "data_sequenciamento":"Data Seq.",
    "qtd_pendente":       "Qtd Pend.",
    "utilizacao_livre":   "Estoque",
    "qtd_programada":     "Programado",
    "saldo_inicial":      "Saldo Ini.",
    "demanda_acumulada":  "Dem. Acum.",
    "saldo_projetado":    "Saldo Proj.",
    "status":             "Status",
    "fecha_sozinho":      "Fecha Sozinho",
}

LABELS_RES = {
    "espessura":          "Esp. (mm)",
    "tipo_aco":           "Tipo Aço",
    "tipo_material":      "Tipo Mat.",
    "material":           "Material",
    "descricao":          "Fita",
    "maquinas":           "Máquinas",
    "descricao_pai":      "Prod. Final",
    "matriz":             "Matriz",
    "qtd_demanda_total":  "Demanda Total",
    "utilizacao_livre":   "Estoque",
    "qtd_programada":     "Programado",
    "saldo_inicial":      "Saldo Ini.",
    "qtd_a_programar":    "A Programar",
}

# ── Carregamento ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_data():
    if not DB_PATH.exists():
        return None, None
    with sqlite3.connect(DB_PATH) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "NECESSIDADE" not in tables or "RESUMO_DETALHADO" not in tables:
            return None, None
        nec = pd.read_sql("SELECT * FROM NECESSIDADE",      conn)
        res = pd.read_sql("SELECT * FROM RESUMO_DETALHADO", conn)
    return nec, res


def fmt_kg(v: float) -> str:
    return f"{v:,.0f} kg"


def _gerar_excel(df_nec: pd.DataFrame, df_res: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_nec.rename(columns=LABELS_NEC).to_excel(writer, sheet_name="Necessidade",      index=False)
        df_res.rename(columns=LABELS_RES).to_excel(writer, sheet_name="Resumo Detalhado", index=False)
    return buf.getvalue()


def _salvar_excel_disco(dados: bytes) -> str | None:
    usuario = socket.gethostname()
    output_dir = get_configuracao(usuario, "output_dir")
    if not output_dir:
        return None
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    nome = f"Necessidade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    destino = p / nome
    destino.write_bytes(dados)
    return str(destino)


# ── Header ────────────────────────────────────────────────────────────────────

st.title("Necessidade de Produção")

meta = get_metadata()
col_h1, col_h2, col_h3, col_h4 = st.columns([3, 2, 1, 1])

with col_h2:
    ts = meta.get("NECESSIDADE", "—")
    st.caption(f"Atualizado em: **{ts}**")

with col_h3:
    if st.button("Recalcular", use_container_width=True):
        with st.spinner("Calculando..."):
            result = calcular_necessidade_prod()
        if result["status"] == "success":
            st.cache_data.clear()
            st.success("Recalculado com sucesso!")
            st.rerun()
        else:
            st.error(result["message"])

# ── Dados ─────────────────────────────────────────────────────────────────────

df_nec, df_res = load_data()

if df_nec is None:
    st.warning(
        "Dados não encontrados. Execute os passos 01, 02 e 03 "
        "para gerar as tabelas de necessidade.",
        icon="⚠️",
    )
    st.stop()

# botão de exportar Excel (renderizado após dados carregados)
with col_h4:
    excel_bytes = _gerar_excel(df_nec, df_res)
    nome_arquivo = f"Necessidade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        label="📥 Exportar Excel",
        data=excel_bytes,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    if st.button("💾 Salvar no disco", use_container_width=True):
        caminho = _salvar_excel_disco(excel_bytes)
        if caminho:
            st.success(f"Salvo em: `{caminho}`")
        else:
            st.warning("Configure o diretório de saída na página ⚙️ Configuração.")

# ── Abas ─────────────────────────────────────────────────────────────────────

aba_nec, aba_res, aba_ind = st.tabs([
    "📋 Necessidade",
    "📊 Resumo Detalhado",
    "📈 Indicadores",
])

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 1 — NECESSIDADE
# ═══════════════════════════════════════════════════════════════════════════════

with aba_nec:

    # ── Filtros ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=True):
        fc1, fc2, fc3, fc4, fc5 = st.columns(5)

        opt_maq  = sorted(df_nec["maquina"].dropna().unique())
        opt_sta  = sorted(df_nec["status"].dropna().unique())
        opt_esp  = sorted(df_nec["espessura"].dropna().unique())
        opt_aco  = sorted(df_nec["tipo_aco"].dropna().unique())
        opt_mat  = sorted(df_nec["tipo_material"].dropna().unique())

        sel_maq = fc1.multiselect("Máquina",       opt_maq,  placeholder="Todas", key="nec_maq")
        sel_sta = fc2.multiselect("Status",         opt_sta,  placeholder="Todos", key="nec_sta")
        sel_esp = fc3.multiselect("Espessura (mm)", opt_esp,  placeholder="Todas", key="nec_esp")
        sel_aco = fc4.multiselect("Tipo de Aço",   opt_aco,  placeholder="Todos", key="nec_aco")
        sel_mat = fc5.multiselect("Tipo Material",  opt_mat,  placeholder="Todos", key="nec_mat")

    df_f = df_nec.copy()
    if sel_maq: df_f = df_f[df_f["maquina"].isin(sel_maq)]
    if sel_sta: df_f = df_f[df_f["status"].isin(sel_sta)]
    if sel_esp: df_f = df_f[df_f["espessura"].isin(sel_esp)]
    if sel_aco: df_f = df_f[df_f["tipo_aco"].isin(sel_aco)]
    if sel_mat: df_f = df_f[df_f["tipo_material"].isin(sel_mat)]

    # ── Cards ─────────────────────────────────────────────────────────────────
    total      = len(df_f)
    n_ok       = (df_f["status"] == "Ok").sum()
    n_prog     = (df_f["status"] == "Programar").sum()
    cobertura  = round(n_ok / total * 100, 1) if total else 0
    qtd_pend   = df_f["qtd_pendente"].sum()
    qtd_prog_k = df_f[df_f["status"] == "Programar"]["qtd_pendente"].sum()

    ca1, ca2, ca3, ca4, ca5, ca6 = st.columns(6)
    ca1.metric("Total Itens",      f"{total:,}")
    ca2.metric("✅ Ok",             f"{n_ok:,}")
    ca3.metric("🔴 Programar",      f"{n_prog:,}")
    ca4.metric("Cobertura",        f"{cobertura:.1f}%")
    ca5.metric("Demanda Total",    fmt_kg(qtd_pend))
    ca6.metric("Demanda Crítica",  fmt_kg(qtd_prog_k))

    st.divider()

    # ── Tabela ────────────────────────────────────────────────────────────────
    st.markdown(f'<div class="section-title">{len(df_f)} itens</div>', unsafe_allow_html=True)

    df_show = df_f.rename(columns=LABELS_NEC)

    status_col = "Status"
    st.dataframe(
        df_show,
        use_container_width=True,
        height=500,
        column_config={
            "Status": st.column_config.TextColumn(
                "Status",
                help="Ok = estoque suficiente | Programar = necessita compra/produção",
            ),
            "Qtd Pend.":    st.column_config.NumberColumn("Qtd Pend.",   format="%,.0f"),
            "Estoque":      st.column_config.NumberColumn("Estoque",     format="%,.0f"),
            "Programado":   st.column_config.NumberColumn("Programado",  format="%,.0f"),
            "Saldo Ini.":   st.column_config.NumberColumn("Saldo Ini.",  format="%,.0f"),
            "Dem. Acum.":   st.column_config.NumberColumn("Dem. Acum.", format="%,.0f"),
            "Saldo Proj.":  st.column_config.NumberColumn("Saldo Proj.", format="%,.0f"),
        },
        hide_index=True,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 2 — RESUMO DETALHADO
# ═══════════════════════════════════════════════════════════════════════════════

with aba_res:

    # ── Filtros ───────────────────────────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=True):
        rf1, rf2, rf3 = st.columns(3)

        r_esp = rf1.multiselect("Espessura (mm)", sorted(df_res["espessura"].dropna().unique()), placeholder="Todas", key="res_esp")
        r_aco = rf2.multiselect("Tipo de Aço",   sorted(df_res["tipo_aco"].dropna().unique()),   placeholder="Todos", key="res_aco")
        r_mat = rf3.multiselect("Tipo Material",  sorted(df_res["tipo_material"].dropna().unique()), placeholder="Todos", key="res_mat")

    df_rf = df_res.copy()
    if r_esp: df_rf = df_rf[df_rf["espessura"].isin(r_esp)]
    if r_aco: df_rf = df_rf[df_rf["tipo_aco"].isin(r_aco)]
    if r_mat: df_rf = df_rf[df_rf["tipo_material"].isin(r_mat)]

    # ── Cards ─────────────────────────────────────────────────────────────────
    skus      = len(df_rf)
    total_kp  = df_rf["qtd_a_programar"].sum()
    maior     = df_rf["qtd_a_programar"].max() if skus else 0
    media     = df_rf["qtd_a_programar"].mean() if skus else 0

    rb1, rb2, rb3, rb4 = st.columns(4)
    rb1.metric("SKUs a Programar",     f"{skus:,}")
    rb2.metric("Total a Programar",    fmt_kg(total_kp))
    rb3.metric("Maior Demanda",        fmt_kg(maior))
    rb4.metric("Média por SKU",        fmt_kg(media))

    st.divider()

    # ── Tabela ────────────────────────────────────────────────────────────────
    st.markdown(f'<div class="section-title">{skus} SKUs</div>', unsafe_allow_html=True)

    st.dataframe(
        df_rf.rename(columns=LABELS_RES),
        use_container_width=True,
        height=500,
        column_config={
            "Demanda Total": st.column_config.NumberColumn("Demanda Total", format="%,.0f"),
            "Estoque":       st.column_config.NumberColumn("Estoque",       format="%,.0f"),
            "Programado":    st.column_config.NumberColumn("Programado",    format="%,.0f"),
            "Saldo Ini.":    st.column_config.NumberColumn("Saldo Ini.",    format="%,.0f"),
            "A Programar":   st.column_config.NumberColumn("A Programar",   format="%,.0f"),
        },
        hide_index=True,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ABA 3 — INDICADORES
# ═══════════════════════════════════════════════════════════════════════════════

with aba_ind:

    # ── KPIs de topo ──────────────────────────────────────────────────────────
    total_all     = len(df_nec)
    n_ok_all      = (df_nec["status"] == "Ok").sum()
    n_prog_all    = (df_nec["status"] == "Programar").sum()
    cob_all       = round(n_ok_all / total_all * 100, 1) if total_all else 0
    total_dem     = df_nec["qtd_pendente"].sum()
    total_est     = df_nec["utilizacao_livre"].sum()
    total_ap      = df_res["qtd_a_programar"].sum()
    n_fecha       = df_nec[df_nec["fecha_sozinho"] != ""]["material"].nunique()
    mat_critic    = df_res.nlargest(1, "qtd_a_programar")["descricao"].values[0] if len(df_res) else "—"
    cobertura_est = round(total_est / total_dem * 100, 1) if total_dem else 0

    ka1, ka2, ka3, ka4, ka5 = st.columns(5)
    ka1.metric("Taxa de Cobertura",    f"{cob_all:.1f}%",
               help="% de itens com saldo projetado positivo")
    ka2.metric("Ruptura (Programar)",  f"{n_prog_all:,}",
               delta=f"-{n_prog_all}", delta_color="inverse")
    ka3.metric("Total a Programar",    fmt_kg(total_ap))
    ka4.metric("Cobertura Estoque",    f"{cobertura_est:.1f}%",
               help="Estoque disponível / Demanda total")
    ka5.metric("Fitas Fecha Sozinho",  f"{n_fecha}",
               help="Materiais que preenchem sozinhos 1000, 1200 ou 1500 mm")

    st.divider()

    # ── Linha 1: Distribuição por espessura + Status por máquina ─────────────
    col_g1, col_g2 = st.columns([1, 1])

    with col_g1:
        st.markdown('<div class="section-title">Qtd a Programar por Espessura</div>', unsafe_allow_html=True)
        esp_grp = (
            df_res
            .groupby("espessura", dropna=False)
            .agg(qtd=("qtd_a_programar", "sum"), skus=("material", "count"))
            .reset_index()
            .sort_values("espessura")
        )
        fig_esp = px.bar(
            esp_grp, x="espessura", y="qtd",
            text="skus",
            labels={"espessura": "Espessura (mm)", "qtd": "Qtd (kg)", "skus": "SKUs"},
            color="qtd",
            color_continuous_scale="Reds",
        )
        fig_esp.update_traces(texttemplate="%{text} SKUs", textposition="outside")
        fig_esp.update_layout(
            coloraxis_showscale=False,
            margin=dict(t=20, b=10),
            height=320,
            yaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig_esp, use_container_width=True)

    with col_g2:
        st.markdown('<div class="section-title">Status por Máquina</div>', unsafe_allow_html=True)
        maq_status = (
            df_nec
            .groupby(["maquina", "status"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        fig_maq = px.bar(
            maq_status, x="maquina", y="count", color="status",
            barmode="group",
            color_discrete_map={"Ok": "#27ae60", "Programar": "#e74c3c"},
            labels={"maquina": "Máquina", "count": "Itens", "status": "Status"},
        )
        fig_maq.update_layout(
            margin=dict(t=20, b=10),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_maq, use_container_width=True)

    # ── Linha 2: Top 10 críticos + Estoque vs Demanda por tipo de aço ────────
    col_g3, col_g4 = st.columns([1, 1])

    with col_g3:
        st.markdown('<div class="section-title">Top 10 Materiais Críticos</div>', unsafe_allow_html=True)
        top10 = df_res.nlargest(10, "qtd_a_programar")[["descricao", "espessura", "qtd_a_programar"]].copy()
        top10["label"] = top10["descricao"].str[:35] + " (" + top10["espessura"].astype(str) + ")"
        fig_top = px.bar(
            top10.sort_values("qtd_a_programar"),
            x="qtd_a_programar", y="label",
            orientation="h",
            color="qtd_a_programar",
            color_continuous_scale="OrRd",
            labels={"qtd_a_programar": "A Programar (kg)", "label": ""},
        )
        fig_top.update_layout(
            coloraxis_showscale=False,
            margin=dict(t=20, b=10, l=10),
            height=350,
            xaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig_top, use_container_width=True)

    with col_g4:
        st.markdown('<div class="section-title">Estoque vs Demanda por Tipo de Aço</div>', unsafe_allow_html=True)
        aco_grp = (
            df_nec
            .groupby("tipo_aco", dropna=False)
            .agg(demanda=("qtd_pendente", "sum"), estoque=("utilizacao_livre", "first"))
            .reset_index()
        )
        fig_aco = go.Figure()
        fig_aco.add_trace(go.Bar(
            name="Demanda",
            x=aco_grp["tipo_aco"], y=aco_grp["demanda"],
            marker_color="#3498db",
        ))
        fig_aco.add_trace(go.Bar(
            name="Estoque",
            x=aco_grp["tipo_aco"], y=aco_grp["estoque"],
            marker_color="#2ecc71",
        ))
        fig_aco.update_layout(
            barmode="group",
            margin=dict(t=20, b=10),
            height=350,
            yaxis_tickformat=",.0f",
            xaxis_title="Tipo de Aço",
            yaxis_title="kg",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_aco, use_container_width=True)

    # ── Linha 3: Distribuição por tipo de material + Fitas que fecham sozinho ─
    col_g5, col_g6 = st.columns([1, 1])

    with col_g5:
        st.markdown('<div class="section-title">Composição da Demanda por Tipo de Material</div>', unsafe_allow_html=True)
        mat_grp = (
            df_res
            .groupby("tipo_material", dropna=False)["qtd_a_programar"]
            .sum()
            .reset_index()
            .sort_values("qtd_a_programar", ascending=False)
        )
        fig_mat = px.pie(
            mat_grp, names="tipo_material", values="qtd_a_programar",
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_mat.update_traces(textposition="outside", textinfo="percent+label")
        fig_mat.update_layout(margin=dict(t=20, b=10), height=320, showlegend=False)
        st.plotly_chart(fig_mat, use_container_width=True)

    with col_g6:
        st.markdown('<div class="section-title">Fitas que Fecham Sozinhas (bobina padrão)</div>', unsafe_allow_html=True)
        df_fecha = (
            df_nec[df_nec["fecha_sozinho"] != ""][["material", "descricao", "largura", "fecha_sozinho"]]
            .drop_duplicates("material")
            .rename(columns={"descricao": "Fita", "largura": "Larg. (mm)", "fecha_sozinho": "Bobinas"})
        )
        if df_fecha.empty:
            st.info("Nenhum material fecha sozinho nas larguras padrão.")
        else:
            st.dataframe(
                df_fecha[["Fita", "Larg. (mm)", "Bobinas"]],
                use_container_width=True,
                height=300,
                hide_index=True,
            )
