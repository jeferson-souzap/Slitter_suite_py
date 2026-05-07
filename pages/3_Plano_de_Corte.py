import streamlit as st
import pandas as pd
from datetime import datetime

from core.plano_corte_engine import (
    init_plano_corte, get_config, banco_matrizes_existe,
    get_espessuras, get_tipos_material, get_matrizes_ancora, get_larguras,
    carregar_matrizes,
    encontrar_combinacoes, validar_resultado,
    calcular_peso_medio_bobina, calcular_kg_combinacao, calcular_kg_matriz,
    exportar_excel,
    salvar_hist_plano, get_hist_plano, deletar_hist_plano, limpar_hist_plano,
)

st.set_page_config(page_title="Plano de Corte | Slitter Suite", layout="wide")

init_plano_corte()

_NENHUMA = "— nenhuma —"

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; color: #888; }
.section-title {
    font-size: 0.82rem; font-weight: 600; color: #555;
    text-transform: uppercase; letter-spacing: .06em;
    margin: 0.8rem 0 .3rem;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _exibir_resultados(df_res, largura_usada, ancora, espessura, tipo,
                       qtd_bobinas, peso, limite_cortes, key_prefix=""):
    if df_res.empty:
        st.warning(
            "Nenhuma combinação encontrada. "
            "Tente ampliar o limite de cortes ou verificar os dados importados."
        )
        return

    stats      = validar_resultado(df_res, espessura)
    peso_medio = calcular_peso_medio_bobina(peso, qtd_bobinas)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Combinações",   stats['total'])
    c2.metric("✅ Válidas",     stats['validas'])
    c3.metric("Fora da regra", stats['fora_regra'])
    c4.metric("Largura usada", f"{largura_usada} mm")

    st.divider()

    aba_combos, aba_detalhes = st.tabs(["Combinações", "Detalhes"])

    with aba_combos:
        cols_disp = ['Combinacao', 'N_ancora', 'Total_cortes', 'Soma_cortes_mm', 'Perda_mm', 'Perda_pct', 'Status']
        df_d = df_res[cols_disp].copy()
        df_d['Perda_pct']      = df_d['Perda_pct'].map(lambda x: f"{x:.4f}%")
        df_d['Perda_mm']       = df_d['Perda_mm'].map(lambda x: f"{x:.3f}")
        df_d['Soma_cortes_mm'] = df_d['Soma_cortes_mm'].map(lambda x: f"{x:.3f}")
        df_d.insert(
            len(df_d.columns) - 1, 'KG',
            df_res.apply(
                lambda r: f"{calcular_kg_combinacao(r['Detalhes'], peso_medio, largura_usada, qtd_bobinas):,.0f}",
                axis=1,
            )
        )
        df_d = df_d.rename(columns={
            'Combinacao': 'Combinação', 'N_ancora': 'N Âncora',
            'Total_cortes': 'Total Cortes', 'Soma_cortes_mm': 'Soma (mm)',
            'Perda_mm': 'Perda (mm)', 'Perda_pct': 'Perda (%)', 'KG': 'Qtd. KG',
        })
        st.dataframe(
            df_d, use_container_width=True, hide_index=True,
            column_config={'Status': st.column_config.TextColumn('Status', width='small')},
        )

    with aba_detalhes:
        linhas = []
        for i, row in df_res.iterrows():
            for j, det in enumerate(row['Detalhes']):
                kg_m = calcular_kg_matriz(
                    peso_medio, largura_usada,
                    det['N_cortes'], det['Desenvolvimento_mm'], qtd_bobinas,
                )
                linhas.append({
                    '# Combo':              i + 1,
                    'Papel':                'ÂNCORA' if j == 0 else 'Complementar',
                    'Código':               det['Codigo'],
                    'Espessura (mm)':       espessura,
                    'Matriz':               det['Matriz'],
                    'Tipo de material':     det.get('Tipo_material', ''),
                    'Produto':              det.get('Descri_produto', ''),
                    'Desenvolvimento (mm)': det['Desenvolvimento_mm'],
                    'Nº Cortes':            det['N_cortes'],
                    'Qtd. KG':              round(kg_m, 2),
                })
        st.dataframe(
            pd.DataFrame(linhas), use_container_width=True, hide_index=True,
            column_config={
                '# Combo':              st.column_config.NumberColumn('# Combo', width='small'),
                'Nº Cortes':            st.column_config.NumberColumn('Nº Cortes', width='small'),
                'Qtd. KG':              st.column_config.NumberColumn('Qtd. KG', format='%.2f'),
                'Espessura (mm)':       st.column_config.NumberColumn('Esp. (mm)', format='%.2f'),
                'Desenvolvimento (mm)': st.column_config.NumberColumn('Desenv. (mm)', format='%.3f'),
            },
        )

    ancora_safe  = ancora.replace('/', '_').replace('"', 'in').replace(' ', '_')
    nome_arquivo = (
        f"plano_{ancora_safe}_esp{str(espessura).replace('.', '-')}_"
        f"{tipo.replace(' ', '_')}_L{largura_usada}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    )
    st.download_button(
        label="📥 Exportar Excel",
        data=exportar_excel(df_res, largura_usada, ancora, espessura, tipo, qtd_bobinas, peso, limite_cortes),
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_{key_prefix}",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("Salvar plano escolhido no histórico", expanded=False):
        opcoes = {i + 1: f"#{i + 1} — {row['Combinacao']}" for i, row in df_res.iterrows()}
        col_sel, col_obs = st.columns([1, 2])
        with col_sel:
            combo_num = st.selectbox(
                "Combinação escolhida",
                options=list(opcoes.keys()),
                format_func=lambda k: opcoes[k],
                key=f"sel_{key_prefix}",
            )
        with col_obs:
            obs = st.text_input(
                "Observação (opcional)",
                placeholder="Ex.: aprovado pelo supervisor, lote #123...",
                key=f"obs_{key_prefix}",
            )
        if st.button("Salvar no Histórico", type="primary", key=f"btn_salvar_{key_prefix}"):
            row = df_res.iloc[combo_num - 1]
            kg  = calcular_kg_combinacao(row['Detalhes'], peso_medio, largura_usada, qtd_bobinas)
            salvar_hist_plano({
                'ancora': ancora, 'espessura': espessura, 'tipo_material': tipo,
                'largura_bobina': largura_usada, 'combinacao': row['Combinacao'],
                'n_ancora': int(row['N_ancora']), 'total_cortes': int(row['Total_cortes']),
                'soma_cortes_mm': float(row['Soma_cortes_mm']),
                'perda_mm': float(row['Perda_mm']), 'perda_pct': float(row['Perda_pct']),
                'qtd_kg': round(float(kg), 2), 'status': row['Status'], 'observacao': obs,
            })
            st.success(f"Combinação #{combo_num} salva no histórico.")
            st.rerun()


# ── Cabeçalho ─────────────────────────────────────────────────────────────────

st.title("Plano de Corte")
st.caption("Geração e visualização de combinações de matrizes.")

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

with st.expander("Parâmetros do sistema", expanded=False):
    try:
        perda_min  = get_config("perda_min_pct")
        perda_max  = get_config("perda_max_pct")
        ref_ate3   = get_config("refilo_min_ate_3mm")
        ref_acima3 = get_config("refilo_min_acima_3mm")
        max_combo  = get_config("max_comp_na_combo")
        qtd_bob    = get_config("qtd_bobinas_pad")
        largs      = ", ".join(str(l) for l in get_larguras())
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Perda mín. (%)",    f"{perda_min:.2f}%")
        c2.metric("Perda máx. (%)",    f"{perda_max:.2f}%")
        c3.metric("Refilo ≤ 3 mm",     f"{ref_ate3} mm")
        c4.metric("Refilo > 3 mm",     f"{ref_acima3} mm")
        c5.metric("Máx. matrizes/combo", int(max_combo))
        c6.metric("Qtd. bobinas padrão", int(qtd_bob))
        st.caption(f"Larguras configuradas: **{largs}** mm")
    except Exception:
        st.info("Configure os parâmetros em **⚙️ Configuração → Plano de Corte**.")


# ── Parâmetros da busca ───────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown('<div class="section-title">Parâmetros da busca</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        espessura     = st.selectbox("Espessura (mm)", options=get_espessuras(), key="esp")
        tipo_material = st.selectbox("Tipo de Material", options=get_tipos_material(espessura), key="tipo")

    with col2:
        opcoes_ancora = get_matrizes_ancora(espessura, tipo_material)
        ancora01 = st.selectbox("Âncora 01", options=opcoes_ancora, key="anc01")
        ancora02 = st.selectbox("Âncora 02 (opcional)", options=[_NENHUMA] + opcoes_ancora, key="anc02")
        ancora03 = st.selectbox("Âncora 03 (opcional)", options=[_NENHUMA] + opcoes_ancora, key="anc03")

    with col3:
        max_comp_edit = st.number_input(
            "Máx. matrizes por combinação",
            value=int(get_config("max_comp_na_combo")),
            min_value=1, max_value=10,
        )
        usa_limite   = st.checkbox("Limitar total de cortes", value=False)
        limite_corte = st.number_input(
            "Limite de cortes", value=8, min_value=1, max_value=30,
            disabled=not usa_limite,
        )

    with col4:
        qtd_bobinas = st.number_input(
            "Quantidade de bobinas",
            value=int(get_config("qtd_bobinas_pad")),
            min_value=1, max_value=100,
        )
        peso = st.number_input(
            "Peso total do lote (kg)",
            value=int(get_config("peso_medio_bob_pad")),
            min_value=1000, max_value=500000, step=500,
        )
        largura_sel = st.selectbox(
            "Forçar largura de bobina",
            options=["— automático —"] + get_larguras(),
        )

    st.markdown("<br>", unsafe_allow_html=True)
    gerar = st.button("Gerar Plano de Corte", type="primary", use_container_width=True)


# ── Geração ───────────────────────────────────────────────────────────────────

if gerar:
    limite_final   = limite_corte if usa_limite else None
    larguras_lista = [largura_sel] if isinstance(largura_sel, int) else None

    ancoras_ativas = [ancora01]
    for a in [ancora02, ancora03]:
        if a != _NENHUMA and a not in ancoras_ativas:
            ancoras_ativas.append(a)

    with st.spinner("Buscando combinações..."):
        df_matrizes = carregar_matrizes()
        resultados_ancoras = []
        for ancora in ancoras_ativas:
            res = encontrar_combinacoes(
                df=df_matrizes, espessura=espessura, tipo_material=tipo_material,
                matriz_ancora=ancora, limite_cortes=limite_final,
                larguras=larguras_lista, max_complementares=int(max_comp_edit),
            )
            resultados_ancoras.append((ancora, res))

    st.session_state["plano_resultados"] = resultados_ancoras
    st.session_state["plano_params"] = {
        "espessura": espessura, "tipo_material": tipo_material,
        "limite_corte": limite_final, "qtd_bobinas": qtd_bobinas, "peso": peso,
    }


# ── Resultados ────────────────────────────────────────────────────────────────

if "plano_resultados" in st.session_state and st.session_state["plano_resultados"]:
    p        = st.session_state["plano_params"]
    res_list = st.session_state["plano_resultados"]

    with st.container(border=True):
        if len(res_list) == 1:
            ancora, (df1, l1) = res_list[0]
            st.markdown(f'<div class="section-title">Âncora — {ancora}</div>', unsafe_allow_html=True)
            _exibir_resultados(
                df1, l1, ancora, p['espessura'], p['tipo_material'],
                p['qtd_bobinas'], p['peso'], p['limite_corte'], key_prefix="a1",
            )
        else:
            tab_labels = [f"Âncora {i+1:02d} — {ancora}" for i, (ancora, _) in enumerate(res_list)]
            tabs = st.tabs(tab_labels)
            for i, (tab, (ancora, (df_a, l_a))) in enumerate(zip(tabs, res_list)):
                with tab:
                    _exibir_resultados(
                        df_a, l_a, ancora, p['espessura'], p['tipo_material'],
                        p['qtd_bobinas'], p['peso'], p['limite_corte'], key_prefix=f"a{i+1}",
                    )


# ── Histórico ─────────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown('<div class="section-title">Histórico de Planos Escolhidos</div>', unsafe_allow_html=True)

    df_hist = get_hist_plano()

    if df_hist.empty:
        st.info("Nenhum plano salvo ainda. Use **Salvar no Histórico** após gerar combinações.")
    else:
        df_h = df_hist.rename(columns={
            'id': 'ID', 'salvo_em': 'Salvo em', 'ancora': 'Âncora',
            'espessura': 'Esp. (mm)', 'tipo_material': 'Tipo',
            'largura_bobina': 'Largura (mm)', 'combinacao': 'Combinação',
            'n_ancora': 'N Âncora', 'total_cortes': 'Total Cortes',
            'soma_cortes_mm': 'Soma (mm)', 'perda_mm': 'Perda (mm)',
            'perda_pct': 'Perda (%)', 'qtd_kg': 'Qtd. KG',
            'status': 'Status', 'observacao': 'Observação',
        })
        st.dataframe(
            df_h, use_container_width=True, hide_index=True,
            column_config={
                'ID':         st.column_config.NumberColumn('ID', width='small'),
                'Perda (%)':  st.column_config.NumberColumn('Perda (%)', format='%.4f'),
                'Perda (mm)': st.column_config.NumberColumn('Perda (mm)', format='%.3f'),
                'Soma (mm)':  st.column_config.NumberColumn('Soma (mm)', format='%.3f'),
                'Qtd. KG':    st.column_config.NumberColumn('Qtd. KG', format='%.2f'),
                'Esp. (mm)':  st.column_config.NumberColumn('Esp. (mm)', format='%.2f'),
                'Status':     st.column_config.TextColumn('Status', width='small'),
            },
        )
        col_del, col_limpar, _ = st.columns([1, 1, 4])
        with col_del:
            ids   = df_hist['id'].tolist()
            id_del = st.selectbox("Excluir (ID)", options=ids, format_func=lambda i: f"ID {i}", key="hist_id_del")
            if st.button("Excluir registro", key="btn_del_hist"):
                deletar_hist_plano(id_del)
                st.success(f"ID {id_del} excluído.")
                st.rerun()
        with col_limpar:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Limpar histórico", key="btn_limpar_hist"):
                limpar_hist_plano()
                st.success("Histórico limpo.")
                st.rerun()

st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
