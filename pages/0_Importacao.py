import io
import sqlite3

import pandas as pd
import streamlit as st

from core.import_engine import (
    DB_PATH,
    import_op_cronograma_from_files,
    import_necessidade_from_files,
    calcular_necessidade_prod,
)

st.set_page_config(page_title="Importação", layout="wide", page_icon="📂")

# ── Estado de sessão ──────────────────────────────────────────────────────────

if "etapa1_resultado" not in st.session_state:
    st.session_state.etapa1_resultado = None
if "etapa1_baixada" not in st.session_state:
    st.session_state.etapa1_baixada = False
if "etapa2_resultado" not in st.session_state:
    st.session_state.etapa2_resultado = None

# ── Verifica estado do banco ──────────────────────────────────────────────────

def _tabela_existe(nome: str) -> bool:
    if not DB_PATH.exists():
        return False
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)
        )
        return cur.fetchone() is not None


op_existe = _tabela_existe("OP_CRONOGRAMA")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("Importação de Dados")
st.caption(
    "Importe os arquivos exportados do SAP para atualizar as tabelas do sistema."
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 01 — CRONOGRAMA DE PRODUÇÃO (CR-*-EXPORT.xlsx)
# ══════════════════════════════════════════════════════════════════════════════

st.subheader("Etapa 01 — Cronograma de Produção")
st.markdown(
    "Selecione **um ou mais** arquivos `CR-*-EXPORT.xlsx` exportados do SAP. "
    "Cada arquivo corresponde a uma máquina."
)

# Se já existe no banco, oferece opção de pular a importação
if op_existe and not st.session_state.etapa1_baixada:
    st.info(
        "OP_CRONOGRAMA encontrada no banco de dados. "
        "Você pode importar novos arquivos ou prosseguir com os dados existentes."
    )
    if st.button("Usar dados existentes e prosseguir para Etapa 02", key="pular_etapa1"):
        st.session_state.etapa1_baixada = True
        st.rerun()

arquivos_cr = st.file_uploader(
    "Arquivos CR-*-EXPORT.xlsx",
    type=["xlsx"],
    accept_multiple_files=True,
    key="uploader_cr",
)

col_imp1, col_esp1 = st.columns([1, 4])
with col_imp1:
    btn_importar1 = st.button(
        "Importar",
        type="primary",
        use_container_width=True,
        disabled=not arquivos_cr,
        key="btn_importar1",
    )

if btn_importar1 and arquivos_cr:
    with st.spinner("Processando arquivos..."):
        resultado = import_op_cronograma_from_files(arquivos_cr)

    if resultado["status"] == "success":
        st.session_state.etapa1_resultado = resultado
        st.session_state.etapa1_baixada = False  # exige novo download
        st.success(
            f"Importado com sucesso! "
            f"**{resultado['rows']:,} linhas** | "
            f"Máquinas: `{'`, `'.join(resultado['machines'])}`"
        )
    else:
        st.error(resultado["message"])

# ── Resultado + Download ──────────────────────────────────────────────────────

res1 = st.session_state.etapa1_resultado

if res1 and res1["status"] == "success":
    st.markdown("##### Prévia — OP_CRONOGRAMA")

    df_prev = res1["df"].head(100)
    st.dataframe(df_prev, use_container_width=True, height=250, hide_index=True)

    st.markdown(
        "Baixe o arquivo para verificar os dados antes de prosseguir para a Etapa 02."
    )

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        res1["df"].to_excel(writer, sheet_name="OP_CRONOGRAMA", index=False)
    excel_bytes = buf.getvalue()

    if st.download_button(
        label="📥 Baixar OP_CRONOGRAMA.xlsx",
        data=excel_bytes,
        file_name="OP_CRONOGRAMA.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_etapa1",
    ):
        st.session_state.etapa1_baixada = True

    if st.session_state.etapa1_baixada:
        st.success("Download registrado. Etapa 02 desbloqueada.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 02 — DEMAIS ARQUIVOS + CÁLCULO DE NECESSIDADE
# ══════════════════════════════════════════════════════════════════════════════

etapa2_desbloqueada = st.session_state.etapa1_baixada

st.subheader("Etapa 02 — Arquivos de Necessidade")

if not etapa2_desbloqueada:
    st.warning(
        "Complete a Etapa 01 e baixe o arquivo OP_CRONOGRAMA.xlsx para desbloquear esta etapa.",
        icon="🔒",
    )

st.markdown(
    "Selecione os **3 arquivos de uma vez** exportados do SAP: "
    "`ITENS-CRONOGRAMA-EXPORT.xlsx`, `ZPP001-EXPORT.xlsx` e `PROG-EXPORT.xlsx`. "
    "Os dados serão importados e a **tabela de Necessidade será recalculada** automaticamente."
)

arquivos_etapa2 = st.file_uploader(
    "ITENS-CRONOGRAMA · ZPP001 · PROG (selecione os 3 arquivos)",
    type=["xlsx"],
    accept_multiple_files=True,
    key="uploader_etapa2",
    disabled=not etapa2_desbloqueada,
)

# Identifica cada arquivo pelo nome
f_itens = f_zpp = f_prog = None
nomes_invalidos = []

for f in (arquivos_etapa2 or []):
    nome = f.name.upper()
    if "ITENS-CRONOGRAMA" in nome:
        f_itens = f
    elif "ZPP001" in nome:
        f_zpp = f
    elif "PROG" in nome:
        f_prog = f
    else:
        nomes_invalidos.append(f.name)

if nomes_invalidos:
    st.warning(f"Arquivo(s) não reconhecido(s): {', '.join(nomes_invalidos)}")

# Feedback visual do que já foi selecionado
if arquivos_etapa2:
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"{'✅' if f_itens else '⬜'} ITENS-CRONOGRAMA")
    c2.markdown(f"{'✅' if f_zpp   else '⬜'} ZPP001")
    c3.markdown(f"{'✅' if f_prog  else '⬜'} PROG")

todos_selecionados = all([f_itens, f_zpp, f_prog])

col_imp2, col_esp2 = st.columns([1, 4])
with col_imp2:
    btn_importar2 = st.button(
        "Importar e Calcular",
        type="primary",
        use_container_width=True,
        disabled=(not etapa2_desbloqueada or not todos_selecionados),
        key="btn_importar2",
    )

if btn_importar2 and todos_selecionados:
    with st.spinner("Importando arquivos..."):
        res_imp = import_necessidade_from_files(f_itens, f_prog, f_zpp)

    if res_imp["status"] != "success":
        st.error(res_imp["message"])
    else:
        tabelas = res_imp["tables"]
        st.success(
            f"Arquivos importados: "
            f"ITENS_CRONOGRAMA ({tabelas['ITENS_CRONOGRAMA']['rows']:,} linhas) · "
            f"PROG ({tabelas['PROG']['rows']:,} linhas) · "
            f"ZPP001 ({tabelas['ZPP001']['rows']:,} linhas)"
        )

        with st.spinner("Calculando necessidade de produção..."):
            res_calc = calcular_necessidade_prod()

        if res_calc["status"] == "success":
            r = res_calc["resumo"]
            st.session_state.etapa2_resultado = res_calc

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            col_r1.metric("Total itens",      f"{r['status_ok'] + r['status_programar']:,}")
            col_r2.metric("✅ Ok",             f"{r['status_ok']:,}")
            col_r3.metric("🔴 Programar",      f"{r['status_programar']:,}")
            col_r4.metric("SKUs a programar",  f"{r['skus_a_programar']:,}")

            st.success("Necessidade calculada com sucesso!")
            st.page_link("pages/2_Necessidade.py", label="Ver Necessidade de Produção →", icon="📦")
        else:
            st.error(res_calc["message"])
