import socket
import streamlit as st
from pathlib import Path

from core.import_engine import get_configuracao, set_configuracao
from core.plano_corte_engine import (
    init_plano_corte, get_all_config, set_config,
    get_larguras, set_larguras,
    banco_matrizes_existe, tratar_excel_matrizes, importar_matrizes,
    carregar_matrizes,
)

st.set_page_config(page_title="Configuração", layout="wide", page_icon="⚙️")

init_plano_corte()

USUARIO = socket.gethostname()

st.title("Configuração")
st.caption(f"Usuário (nome do PC): **{USUARIO}**")

aba_geral, aba_plano = st.tabs(["Geral", "Plano de Corte"])


# ════════════════════════════════════════════════════════════════════════════════
# ABA 1 — GERAL
# ════════════════════════════════════════════════════════════════════════════════

with aba_geral:
    st.subheader("Diretório de Saída")
    st.markdown("Caminho da pasta onde os arquivos exportados (Excel, etc.) serão salvos.")

    saved_output = get_configuracao(USUARIO, "output_dir") or ""

    novo_output = st.text_input(
        "Caminho de saída",
        value=saved_output,
        placeholder=r"Ex: D:\Exportações\Slitter",
    )

    col_btn, col_status = st.columns([1, 4])
    with col_btn:
        salvar = st.button("💾 Salvar", type="primary", use_container_width=True)

    if salvar:
        caminho = novo_output.strip()
        if not caminho:
            st.error("Informe um caminho válido.")
        else:
            try:
                p = Path(caminho)
                p.mkdir(parents=True, exist_ok=True)
                set_configuracao(USUARIO, "output_dir", str(p))
                st.success(f"Caminho salvo com sucesso: `{p}`")
            except Exception as e:
                st.error(f"Erro ao criar/acessar o diretório: {e}")

    if saved_output:
        p_atual = Path(saved_output)
        existe  = p_atual.exists()
        st.info(
            f"{'✅' if existe else '⚠️'} Caminho atual: `{saved_output}` "
            f"({'existe' if existe else 'diretório não encontrado'})"
        )


# ════════════════════════════════════════════════════════════════════════════════
# ABA 2 — PLANO DE CORTE
# ════════════════════════════════════════════════════════════════════════════════

with aba_plano:

    # ── Importação de Matrizes ────────────────────────────────────────────────

    st.subheader("Importar Banco de Matrizes")
    st.markdown(
        "Carregue o Excel com as colunas: **Código, Matriz, Tipo de material, Produto, Espessura, Desenvolvimento**."
    )

    arquivo = st.file_uploader(
        "Selecione o arquivo Excel de matrizes",
        type=["xlsx", "xls"],
        key="upload_matrizes",
    )

    if arquivo is not None:
        try:
            df_preview = tratar_excel_matrizes(arquivo)
            st.success(f"{len(df_preview)} matrizes válidas encontradas no arquivo.")

            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            col_p1.metric("Total Matrizes",   len(df_preview))
            col_p2.metric("Espessuras",        df_preview["Espessura"].nunique())
            col_p3.metric("Tipos de Material", df_preview["Tipo de material"].nunique())
            col_p4.metric("Matrizes Únicas",   df_preview["Matriz"].nunique())

            with st.expander("Prévia dos dados", expanded=False):
                st.dataframe(df_preview.head(50), use_container_width=True, hide_index=True)

            if st.button("Importar para o banco", type="primary"):
                qtd = importar_matrizes(df_preview)
                st.success(f"✅ {qtd} matrizes importadas com sucesso!")
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

    if banco_matrizes_existe():
        df_atual = carregar_matrizes()
        st.info(
            f"Banco atual: **{len(df_atual)} matrizes**, "
            f"**{df_atual['Espessura'].nunique()} espessuras**, "
            f"**{df_atual['Tipo de material'].nunique()} tipos de material**."
        )
    else:
        st.warning("Nenhuma matriz importada ainda.", icon="⚠️")

    st.divider()

    # ── Parâmetros de Corte ───────────────────────────────────────────────────

    st.subheader("Parâmetros de Corte")

    try:
        cfg = get_all_config()

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Regras de perda (refilo)**")
            nova_perda_min = st.number_input(
                "Perda mínima (%)",
                value=float(cfg["perda_min_pct"]),
                min_value=0.01, max_value=5.0, step=0.01, format="%.2f",
                help="Percentual mínimo de refilo aceito pela regra.",
            )
            nova_perda_max = st.number_input(
                "Perda máxima (%)",
                value=float(cfg["perda_max_pct"]),
                min_value=0.01, max_value=10.0, step=0.01, format="%.2f",
                help="Percentual máximo de refilo aceito pela regra.",
            )
            novo_refilo_ate3 = st.number_input(
                "Refilo mínimo — espessura ≤ 3,0 mm (mm)",
                value=int(cfg["refilo_min_ate_3mm"]),
                min_value=1, max_value=50,
            )
            novo_refilo_acima3 = st.number_input(
                "Refilo mínimo — espessura > 3,0 mm (mm)",
                value=int(cfg["refilo_min_acima_3mm"]),
                min_value=1, max_value=50,
            )

        with col2:
            st.markdown("**Parâmetros da busca**")
            novo_max_comp = st.number_input(
                "Máx. matrizes complementares por combinação",
                value=int(cfg["max_comp_na_combo"]),
                min_value=1, max_value=10,
            )
            novo_peso_pad = st.number_input(
                "Peso padrão da bobina (kg)",
                value=int(cfg["peso_medio_bob_pad"]),
                min_value=100, max_value=100_000, step=100,
            )
            novo_qtd_bob = st.number_input(
                "Quantidade de bobinas padrão",
                value=int(cfg["qtd_bobinas_pad"]),
                min_value=1, max_value=100,
            )

        if st.button("💾 Salvar parâmetros", type="primary", key="btn_salvar_params"):
            set_config("perda_min_pct",        nova_perda_min)
            set_config("perda_max_pct",        nova_perda_max)
            set_config("refilo_min_ate_3mm",   novo_refilo_ate3)
            set_config("refilo_min_acima_3mm", novo_refilo_acima3)
            set_config("max_comp_na_combo",    novo_max_comp)
            set_config("peso_medio_bob_pad",   novo_peso_pad)
            set_config("qtd_bobinas_pad",      novo_qtd_bob)
            st.success("Parâmetros salvos com sucesso!")

    except Exception as e:
        st.error(f"Erro ao carregar parâmetros: {e}")

    st.divider()

    # ── Larguras de Bobina ────────────────────────────────────────────────────

    st.subheader("Larguras de Bobina")
    st.markdown("Larguras disponíveis (mm) testadas na busca de combinações, em ordem crescente.")

    try:
        larguras_atuais = get_larguras()

        larguras_str = st.text_input(
            "Larguras (separadas por vírgula)",
            value=", ".join(str(l) for l in larguras_atuais),
            placeholder="Ex: 1000, 1200, 1250, 1422, 1500",
            help="Informe os valores em mm separados por vírgula.",
        )

        if st.button("💾 Salvar larguras", key="btn_salvar_larguras"):
            try:
                novas = [int(x.strip()) for x in larguras_str.split(",") if x.strip().isdigit()]
                if not novas:
                    st.error("Informe ao menos uma largura válida.")
                else:
                    set_larguras(novas)
                    st.success(f"Larguras salvas: {sorted(novas)}")
                    st.rerun()
            except Exception as ex:
                st.error(f"Erro ao salvar larguras: {ex}")

    except Exception as e:
        st.error(f"Erro ao carregar larguras: {e}")
