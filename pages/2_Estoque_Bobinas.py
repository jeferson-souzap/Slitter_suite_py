import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

from core.import_engine import DB_PATH, get_metadata, import_estoque_bobinas

st.set_page_config(page_title="Estoque de Bobinas", layout="wide", page_icon="🪣")

# ── Estilos ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; color: #888; }
.section-title { font-size: 0.85rem; font-weight: 600; color: #555;
                 text-transform: uppercase; letter-spacing: .06em;
                 margin: 1rem 0 .4rem; }
div[data-testid="stDataFrameResizable"] { border: 1px solid #e0e0e0; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Labels ────────────────────────────────────────────────────────────────────

LABELS = {
    "data_importacao":    "Data Import.",
    "material":           "Material",
    "descricao":          "Descrição",
    "quantidade":         "Qtd",
    "lote":               "Lote",
    "unid_medida":        "UM",
    "posicao_deposito":   "Posição Dep.",
    "data_em":            "Data EM",
    "tipo_estoque":       "Tipo Estoque",
    "denom_tipo_estoque": "Denom. Tipo Estoque",
    "ordem_cliente":      "Ordem Cliente",
    "tipo_deposito":      "Tipo Depósito",
    "tipo":               "Tipo",
    "tipo_material":      "Tipo Mat.",
    "tipo_aco":           "Tipo Aço",
    "espessura":          "Esp. (mm)",
    "largura":            "Larg. (mm)",
    "fora_padrao":        "Fora Padrão",
    "dias_estoque":       "Dias Estoque",
    "status_90":          "Status 90d",
}

COLUNAS_VISIVEIS = [
    "data_importacao", "material", "descricao", "tipo_material", "tipo_aco",
    "espessura", "largura", "fora_padrao", "quantidade", "lote",
    "posicao_deposito", "data_em", "dias_estoque", "status_90",
    "tipo_estoque", "denom_tipo_estoque",
]


# ── Carregamento ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_data(data_ref: str) -> pd.DataFrame | None:
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as conn:
        tabelas = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "ESTOQUE_BOBINAS" not in tabelas:
            return None
        return pd.read_sql(
            "SELECT * FROM ESTOQUE_BOBINAS WHERE data_importacao = ?",
            conn,
            params=(data_ref,),
        )


@st.cache_data(show_spinner=False)
def load_datas_disponiveis() -> list[str]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        tabelas = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "ESTOQUE_BOBINAS" not in tabelas:
            return []
        cur = conn.execute(
            "SELECT DISTINCT data_importacao FROM ESTOQUE_BOBINAS ORDER BY data_importacao DESC"
        )
        return [r[0] for r in cur.fetchall()]


# ── Header ────────────────────────────────────────────────────────────────────

st.title("Estoque de Bobinas")

meta = get_metadata()
ts_meta = meta.get("ESTOQUE_BOBINAS", "—")

col_h1, col_h2 = st.columns([4, 1])
with col_h2:
    st.caption(f"Última importação: **{ts_meta}**")

# ── Importação ────────────────────────────────────────────────────────────────

datas_init = load_datas_disponiveis()

with st.expander("📥 Importar arquivo EWMW-EXPORT.xlsx", expanded=not bool(datas_init)):
    st.markdown(
        "Selecione o arquivo `EWMW-EXPORT.xlsx` exportado do SAP. "
        "Cada importação é acumulada por data — reimportações no mesmo dia substituem a anterior."
    )
    arquivo = st.file_uploader(
        "EWMW-EXPORT.xlsx",
        type=["xlsx"],
        key="uploader_ewmw",
    )

    col_b, col_esp = st.columns([1, 4])
    with col_b:
        btn_imp = st.button(
            "Importar",
            type="primary",
            use_container_width=True,
            disabled=not arquivo,
        )

    if btn_imp and arquivo:
        with st.spinner("Importando..."):
            resultado = import_estoque_bobinas(arquivo)

        if resultado["status"] == "success":
            st.cache_data.clear()
            st.success(
                f"Importado com sucesso! "
                f"**{resultado['rows']:,} registros** — {resultado['data_importacao']}"
            )
            st.rerun()
        else:
            st.error(resultado.get("message", "Erro desconhecido."))

# ── Seleção de data ───────────────────────────────────────────────────────────

datas = load_datas_disponiveis()

if not datas:
    st.warning("Nenhum dado importado ainda. Use o painel acima para importar.", icon="⚠️")
    st.stop()

hoje_str = date.today().isoformat()

col_d1, col_d2, col_d3 = st.columns([2, 2, 4])
with col_d1:
    data_sel = st.selectbox(
        "Data de referência",
        options=datas,
        index=0,
        format_func=lambda d: f"{'🟢 Hoje — ' if d == hoje_str else ''}{d}",
    )

df = load_data(data_sel)

if df is None or df.empty:
    st.info("Sem dados para a data selecionada.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────

total     = len(df)
qtd_total = df["quantidade"].sum()
n_90      = (df["status_90"] == "90+").sum()
n_bb      = (df["tipo_material"] == "BB").sum()
n_fp      = df["fora_padrao"].astype(bool).sum()
pct_90    = round(n_90 / total * 100, 1) if total else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Registros",   f"{total:,}")
k2.metric("Quantidade Total",  f"{qtd_total:,.0f}")
k3.metric("Bobinas (BB)",      f"{n_bb:,}")
k4.metric("🔴 Estoque > 90d",  f"{n_90:,}", delta=f"{pct_90:.1f}%", delta_color="inverse")
k5.metric("Fora Padrão (XFP)", f"{n_fp:,}")

st.divider()

# ── Filtros ───────────────────────────────────────────────────────────────────

with st.expander("🔍 Filtros", expanded=True):
    f1, f2, f3, f4, f5 = st.columns(5)

    opt_tm  = sorted(df["tipo_material"].dropna().unique())
    opt_ta  = sorted(df["tipo_aco"].dropna().unique())
    opt_esp = sorted(df["espessura"].dropna().unique())
    opt_s90 = sorted(df["status_90"].dropna().unique())

    sel_tm  = f1.multiselect("Tipo Material", opt_tm,  placeholder="Todos", key="f_tm")
    sel_ta  = f2.multiselect("Tipo Aço",      opt_ta,  placeholder="Todos", key="f_ta")
    sel_esp = f3.multiselect("Espessura",     opt_esp, placeholder="Todas", key="f_esp")
    sel_s90 = f4.multiselect("Status 90d",   opt_s90, placeholder="Todos", key="f_s90")
    sel_fp  = f5.selectbox("Padrão / XFP", ["Todos", "Fora Padrão", "Padrão"], key="f_fp")

df_f = df.copy()
if sel_tm:  df_f = df_f[df_f["tipo_material"].isin(sel_tm)]
if sel_ta:  df_f = df_f[df_f["tipo_aco"].isin(sel_ta)]
if sel_esp: df_f = df_f[df_f["espessura"].isin(sel_esp)]
if sel_s90: df_f = df_f[df_f["status_90"].isin(sel_s90)]
if sel_fp == "Fora Padrão": df_f = df_f[df_f["fora_padrao"].astype(bool)]
if sel_fp == "Padrão":      df_f = df_f[~df_f["fora_padrao"].astype(bool)]

# ── Tabela ────────────────────────────────────────────────────────────────────

cols_existentes = [c for c in COLUNAS_VISIVEIS if c in df_f.columns]
df_show = df_f[cols_existentes].rename(columns=LABELS)

st.markdown(
    f'<div class="section-title">{len(df_show):,} registros</div>',
    unsafe_allow_html=True,
)

st.dataframe(
    df_show,
    use_container_width=True,
    height=520,
    hide_index=True,
    column_config={
        "Qtd":          st.column_config.NumberColumn("Qtd",          format="%,.0f"),
        "Esp. (mm)":    st.column_config.NumberColumn("Esp. (mm)",    format="%.2f"),
        "Larg. (mm)":   st.column_config.NumberColumn("Larg. (mm)",   format="%.1f"),
        "Dias Estoque": st.column_config.NumberColumn("Dias Estoque", format="%,.0f"),
        "Status 90d":   st.column_config.TextColumn("Status 90d"),
        "Fora Padrão":  st.column_config.CheckboxColumn("Fora Padrão"),
    },
)
