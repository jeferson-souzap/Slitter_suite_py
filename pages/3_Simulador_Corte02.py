import streamlit as st
import pandas as pd
import numpy as np
from itertools import product as iprod
from datetime import datetime

from core.plano_corte_engine import (
    init_plano_corte, banco_matrizes_existe, carregar_matrizes,
    get_larguras, get_config,
)

st.set_page_config(
    page_title="Simulador de Corte 02 | Slitter Suite",
    layout="wide",
    page_icon="🎯",
)

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
.tag-item {
    display: inline-block;
    background: rgba(59,130,246,0.15); color: #2563eb;
    border: 1px solid rgba(59,130,246,0.4);
    border-radius: 3px; padding: 1px 8px;
    font-size: 0.75rem; font-weight: 600;
}
.tag-comp {
    display: inline-block;
    background: rgba(39,174,96,0.12); color: #1e9660;
    border: 1px solid rgba(39,174,96,0.35);
    border-radius: 3px; padding: 1px 8px;
    font-size: 0.75rem; font-weight: 600;
}
.linha-total { font-size: 0.85rem; color: #555; padding: 0.25rem 0; }
.linha-total b { color: #222; }
</style>
""", unsafe_allow_html=True)


# ── Constantes ────────────────────────────────────────────────────────────────

PESO_BOBINA_KG = 12_000   # 12 toneladas de referência
MAX_CORTES_POR_ITEM = 8   # limite para controle do espaço de busca


# ── Cabeçalho ─────────────────────────────────────────────────────────────────

st.title("🎯 Simulador de Corte 02")
st.caption(
    "Informe os códigos dos itens e a necessidade em KG. "
    "O sistema gera planos de corte que atendem essas necessidades usando bobinas de "
    f"**{PESO_BOBINA_KG:,} kg (12 ton)**."
)

if not banco_matrizes_existe():
    st.warning(
        "Nenhuma matriz importada. "
        "Acesse **⚙️ Configuração → Plano de Corte** para importar o banco de matrizes.",
        icon="⚠️",
    )
    st.stop()

df_matrizes = carregar_matrizes()


# ── Algoritmo ─────────────────────────────────────────────────────────────────

def _cfg_local() -> dict:
    return {
        'perda_min_pct':        get_config('perda_min_pct'),         # ex: 0.67  (%)
        'perda_max_pct':        get_config('perda_max_pct'),         # ex: 1.70  (%)
        'refilo_min_ate_3mm':   get_config('refilo_min_ate_3mm'),    # mm
        'refilo_min_acima_3mm': get_config('refilo_min_acima_3mm'),  # mm
    }


def _refilo_min(itens: list, cfg: dict) -> float:
    esp_max = max(i['espessura'] for i in itens)
    return float(cfg['refilo_min_ate_3mm'] if esp_max <= 3.0 else cfg['refilo_min_acima_3mm'])


def _label_plano(itens_plano: list) -> str:
    partes = []
    for it in itens_plano:
        partes.append(f"{it['n_cortes']}×{it['codigo']}({it['desenvolvimento']:.1f}mm)")
    return "  +  ".join(partes)


def buscar_por_largura(itens_sel: list, largura: int, cfg: dict,
                       itens_compl: list = None) -> list:
    """
    Encontra todos os planos de corte válidos para os itens selecionados
    dentro de uma largura de bobina.
    Retorna lista de dicts de plano.
    """
    refilo_min = _refilo_min(itens_sel, cfg)
    pmin_mm    = largura * cfg['perda_min_pct']  / 100.0
    pmax_mm    = largura * cfg['perda_max_pct']  / 100.0
    n          = len(itens_sel)

    max_cada = [
        min(MAX_CORTES_POR_ITEM, int(largura / i['desenvolvimento']))
        for i in itens_sel
    ]

    resultados = []

    for cortes in iprod(*[range(0, m + 1) for m in max_cada]):
        if all(c == 0 for c in cortes):
            continue
        soma = sum(cortes[i] * itens_sel[i]['desenvolvimento'] for i in range(n))
        if soma > largura:
            continue
        perda = largura - soma
        if perda < refilo_min:
            continue
        perda_pct = perda / largura * 100.0

        base_items = []
        for i, c in enumerate(cortes):
            if c > 0:
                dev = itens_sel[i]['desenvolvimento']
                base_items.append({
                    'codigo':        itens_sel[i]['codigo'],
                    'label':         itens_sel[i]['label'],
                    'desenvolvimento': dev,
                    'n_cortes':      c,
                    'subtotal_mm':   round(c * dev, 3),
                    'kg':            round(PESO_BOBINA_KG / largura * c * dev, 1),
                    'papel':         'ITEM',
                })

        status = "✓ Válida" if pmin_mm <= perda <= pmax_mm else "Fora da regra"

        plano_base = {
            'largura':          largura,
            'itens':            base_items,
            'soma_mm':          round(soma, 3),
            'perda_mm':         round(perda, 3),
            'perda_pct':        round(perda_pct, 4),
            'status':           status,
            'tem_complementar': False,
        }
        resultados.append(plano_base)

        # ── Tentar preencher sobra com complementares ─────────────────────────
        if itens_compl and perda > pmax_mm:
            comps_caben = [
                c for c in itens_compl
                if c['desenvolvimento'] <= perda - refilo_min
            ]
            for comp in comps_caben:
                dev_c  = comp['desenvolvimento']
                max_nc = min(5, int(perda / dev_c))
                for nc in range(1, max_nc + 1):
                    nova_perda = perda - nc * dev_c
                    if nova_perda < refilo_min:
                        continue
                    nova_pct = nova_perda / largura * 100.0
                    if not (pmin_mm <= nova_perda <= pmax_mm):
                        continue
                    kg_c = round(PESO_BOBINA_KG / largura * nc * dev_c, 1)
                    itens_final = base_items + [{
                        'codigo':        comp['codigo'],
                        'label':         comp['label'],
                        'desenvolvimento': dev_c,
                        'n_cortes':      nc,
                        'subtotal_mm':   round(nc * dev_c, 3),
                        'kg':            kg_c,
                        'papel':         'COMPLEMENTAR',
                    }]
                    resultados.append({
                        'largura':          largura,
                        'itens':            itens_final,
                        'soma_mm':          round(largura - nova_perda, 3),
                        'perda_mm':         round(nova_perda, 3),
                        'perda_pct':        round(nova_pct, 4),
                        'status':           '✓ Válida',
                        'tem_complementar': True,
                    })

    return resultados


def encontrar_planos(itens_sel: list, cfg: dict, larguras: list,
                     com_complementares: bool = False) -> list:
    """Busca planos em todas as larguras e retorna lista deduplicada e ordenada."""
    itens_compl = None
    if com_complementares:
        codigos_sel = {i['codigo'] for i in itens_sel}
        esp_alvo    = itens_sel[0]['espessura'] if itens_sel else None
        mask = ~df_matrizes['Código'].isin(codigos_sel)
        if esp_alvo is not None:
            mask = mask & (df_matrizes['Espessura'] == esp_alvo)
        itens_compl = [
            {
                'codigo': str(row['Código']),
                'label':  f"{row['Código']} — {str(row['Produto'])[:25]}",
                'desenvolvimento': float(row['Desenvolvimento']),
                'espessura':       float(row['Espessura']),
            }
            for _, row in df_matrizes[mask].iterrows()
        ]

    all_planos = []
    for larg in larguras:
        all_planos.extend(buscar_por_largura(itens_sel, larg, cfg, itens_compl))

    # Deduplica por chave (largura + cortes de cada item)
    seen, unique = set(), []
    for p in all_planos:
        chave = (p['largura'], tuple((i['codigo'], i['n_cortes']) for i in p['itens']))
        if chave not in seen:
            seen.add(chave)
            unique.append(p)

    unique.sort(key=lambda p: (0 if p['status'] == '✓ Válida' else 1, p['perda_pct']))
    return unique


def sugerir_alocacao(planos_validos: list, necessidades: dict) -> tuple:
    """
    Sugere quantas bobinas de cada plano cortar para atender as necessidades.
    Retorna (lista de alocações, resumo de produção).
    """
    if not planos_validos:
        return [], {
            c: {'necessidade': v, 'producao': 0.0, 'diferenca': -v}
            for c, v in necessidades.items()
        }

    codigos = list(necessidades.keys())
    n, m    = len(codigos), len(planos_validos)

    # Matriz KG[item, plano]
    kg_mat = np.zeros((n, m))
    for j, plano in enumerate(planos_validos):
        for item in plano['itens']:
            if item['papel'] == 'ITEM' and item['codigo'] in necessidades:
                i = codigos.index(item['codigo'])
                kg_mat[i, j] += item['kg']

    needs     = np.array([necessidades[c] for c in codigos], dtype=float)
    remaining = needs.copy()
    allocation = np.zeros(m, dtype=int)

    for _ in range(500):
        if np.all(remaining <= 0):
            break
        # Pontuação: quanto cada plano cobre da demanda restante
        scores = np.sum(
            np.minimum(kg_mat, np.maximum(remaining[:, None], 0)),
            axis=0,
        )
        best_j = int(np.argmax(scores))
        if scores[best_j] <= 0:
            break

        # Quantidade de bobinas para cobrir pelo menos um item de uma vez
        useful = (kg_mat[:, best_j] > 0) & (remaining > 0)
        if useful.any():
            n_add = max(1, int(np.min(remaining[useful] / kg_mat[useful, best_j])))
        else:
            n_add = 1

        allocation[best_j] += n_add
        remaining -= n_add * kg_mat[:, best_j]

    production = kg_mat @ allocation.astype(float)

    alloc_list = [
        {'plano': planos_validos[j], 'qtd': int(allocation[j])}
        for j in range(m) if allocation[j] > 0
    ]
    prod_summary = {
        codigos[i]: {
            'necessidade': float(needs[i]),
            'producao':    round(float(production[i]), 1),
            'diferenca':   round(float(production[i] - needs[i]), 1),
        }
        for i in range(n)
    }
    return alloc_list, prod_summary


# ── Entrada de Itens ──────────────────────────────────────────────────────────

if 'sc2_itens' not in st.session_state:
    st.session_state['sc2_itens'] = []   # [{codigo, label, desenvolvimento, espessura, needed_kg}]

with st.container(border=True):
    st.markdown('<div class="section-title">Itens e Necessidades</div>', unsafe_allow_html=True)

    ca, cb, cc = st.columns([2, 2, 1])
    with ca:
        novo_cod = st.text_input(
            "Código do Item", key="sc2_cod_input",
            placeholder="Digite o código e clique em Adicionar",
        )
    with cb:
        nova_qty = st.number_input(
            "Necessidade (KG)", min_value=1.0, value=5_000.0, step=500.0,
            key="sc2_qty_input",
        )
    with cc:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_add = st.button("➕ Adicionar", use_container_width=True)

    if btn_add:
        codigo = novo_cod.strip().upper()
        if not codigo:
            st.error("Informe o código do item.")
        else:
            matches = df_matrizes[df_matrizes['Código'].str.upper() == codigo]
            if matches.empty:
                st.error(f"Código **{codigo}** não encontrado na base de matrizes.")
            else:
                # Agrupa por (código, desenvolvimento, espessura) — tira duplicatas de matriz
                variantes = (
                    matches.groupby(['Código', 'Desenvolvimento', 'Espessura'])
                    .first().reset_index()
                )
                if len(variantes) == 1:
                    row = variantes.iloc[0]
                    cod_str = str(row['Código'])
                    if any(i['codigo'] == cod_str and i['desenvolvimento'] == float(row['Desenvolvimento'])
                           for i in st.session_state['sc2_itens']):
                        st.warning(f"Item **{cod_str}** já adicionado.")
                    else:
                        st.session_state['sc2_itens'].append({
                            'codigo':         cod_str,
                            'label':          f"{cod_str} — {str(row.get('Produto',''))[:30]} ({float(row['Espessura'])} mm esp / {float(row['Desenvolvimento']):.1f} mm dev)",
                            'desenvolvimento': float(row['Desenvolvimento']),
                            'espessura':       float(row['Espessura']),
                            'needed_kg':       nova_qty,
                        })
                        st.session_state.pop('sc2_resultado', None)
                        st.rerun()
                else:
                    st.session_state['sc2_pending'] = variantes.to_dict('records')
                    st.session_state['sc2_pending_qty'] = nova_qty
                    st.rerun()

    # Seleção quando há múltiplas variantes
    if 'sc2_pending' in st.session_state:
        variantes = st.session_state['sc2_pending']
        st.info(f"Encontradas **{len(variantes)}** variantes. Selecione a desejada:")
        opts = {
            f"{r['Código']} — {str(r.get('Produto',''))[:30]} | esp {r['Espessura']} mm | dev {float(r['Desenvolvimento']):.1f} mm": r
            for r in variantes
        }
        sel_key = st.selectbox("Variante:", list(opts.keys()), key="sc2_var_sel")
        col_conf, _ = st.columns([1, 3])
        with col_conf:
            if st.button("Confirmar variante", key="sc2_conf_var"):
                row = opts[sel_key]
                cod_str = str(row['Código'])
                st.session_state['sc2_itens'].append({
                    'codigo':         cod_str,
                    'label':          f"{cod_str} — {str(row.get('Produto',''))[:30]} ({float(row['Espessura'])} mm esp / {float(row['Desenvolvimento']):.1f} mm dev)",
                    'desenvolvimento': float(row['Desenvolvimento']),
                    'espessura':       float(row['Espessura']),
                    'needed_kg':       st.session_state['sc2_pending_qty'],
                })
                del st.session_state['sc2_pending']
                del st.session_state['sc2_pending_qty']
                st.session_state.pop('sc2_resultado', None)
                st.rerun()

    # Lista de itens adicionados
    if st.session_state['sc2_itens']:
        st.markdown("<br>", unsafe_allow_html=True)
        hc1, hc2, hc3, hc4, _ = st.columns([4, 1.5, 1.8, 1.8, 0.5])
        hc1.caption("Item")
        hc2.caption("Desenv. (mm)")
        hc3.caption("Esp. (mm)")
        hc4.caption("Necessidade (KG)")

        rem_idx = None
        for idx, item in enumerate(st.session_state['sc2_itens']):
            c1, c2, c3, c4, c5 = st.columns([4, 1.5, 1.8, 1.8, 0.5])
            c1.markdown(f"**{item['codigo']}** — {item['label'].split('—')[1].strip() if '—' in item['label'] else ''}")
            c2.markdown(f"`{item['desenvolvimento']:.1f}`")
            c3.markdown(f"`{item['espessura']}`")
            with c4:
                novo_val = st.number_input(
                    "KG", value=float(item['needed_kg']),
                    min_value=1.0, step=500.0,
                    key=f"sc2_qty_{idx}", label_visibility="collapsed",
                )
                if novo_val != item['needed_kg']:
                    st.session_state['sc2_itens'][idx]['needed_kg'] = novo_val
                    st.session_state.pop('sc2_resultado', None)
            with c5:
                if st.button("✕", key=f"sc2_del_{idx}"):
                    rem_idx = idx

        if rem_idx is not None:
            st.session_state['sc2_itens'].pop(rem_idx)
            st.session_state.pop('sc2_resultado', None)
            st.rerun()

        st.divider()
        total_kg = sum(i['needed_kg'] for i in st.session_state['sc2_itens'])
        espessuras_unicas = {i['espessura'] for i in st.session_state['sc2_itens']}
        c_tot, c_warn = st.columns([2, 3])
        c_tot.markdown(
            f'<div class="linha-total">Total necessidade: <b>{total_kg:,.0f} KG</b> '
            f'≈ <b>{total_kg/PESO_BOBINA_KG:.1f} bobinas</b> referência</div>',
            unsafe_allow_html=True,
        )
        if len(espessuras_unicas) > 1:
            c_warn.warning(
                f"⚠️ Itens com espessuras diferentes: {sorted(espessuras_unicas)} mm. "
                "Em geral planos de corte não misturam espessuras.",
                icon="⚠️",
            )
    else:
        st.info("Nenhum item adicionado. Use o formulário acima para incluir os itens desejados.")


# ── Botão Calcular ────────────────────────────────────────────────────────────

if st.session_state['sc2_itens']:
    if st.button("🔍  Calcular Planos de Corte", type="primary", use_container_width=True):
        itens   = st.session_state['sc2_itens']
        necess  = {i['codigo']: i['needed_kg'] for i in itens}
        cfg     = _cfg_local()
        larguras = get_larguras()

        with st.spinner("Calculando planos — aguarde…"):
            # Aba 1: somente os itens selecionados
            pl_sol = encontrar_planos(itens, cfg, larguras, com_complementares=False)
            validos_sol = [p for p in pl_sol if p['status'] == '✓ Válida']
            alloc_sol, prod_sol = sugerir_alocacao(validos_sol, necess)

            # Aba 2: com complementares
            pl_comp = encontrar_planos(itens, cfg, larguras, com_complementares=True)
            validos_comp = [p for p in pl_comp if p['status'] == '✓ Válida']
            alloc_comp, prod_comp = sugerir_alocacao(validos_comp, necess)

        st.session_state['sc2_resultado'] = {
            'sol':  {'planos': pl_sol,  'validos': validos_sol,  'alloc': alloc_sol,  'prod': prod_sol},
            'comp': {'planos': pl_comp, 'validos': validos_comp, 'alloc': alloc_comp, 'prod': prod_comp},
        }
        st.rerun()


# ── Resultados ────────────────────────────────────────────────────────────────

def _render_tab(dados: dict, titulo_tab: str):
    planos  = dados['planos']
    validos = dados['validos']
    alloc   = dados['alloc']
    prod    = dados['prod']

    if not planos:
        st.warning("Nenhum plano encontrado para os itens e parâmetros informados.")
        return

    invalidos = [p for p in planos if p['status'] != '✓ Válida']

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Planos encontrados",  len(planos))
    m2.metric("✅ Válidos",           len(validos))
    m3.metric("Fora da regra",        len(invalidos))
    m4.metric("Larguras testadas",    len({p['largura'] for p in planos}))

    st.divider()

    # ── Tabela de planos ───────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="section-title">Planos de Corte Encontrados</div>', unsafe_allow_html=True)

        chk_inv = st.checkbox(
            "Mostrar planos fora da regra", key=f"sc2_inv_{titulo_tab}",
        )
        lista_exib = validos + (invalidos if chk_inv else [])
        lista_exib = lista_exib[:50]

        if lista_exib:
            rows_plan = []
            for idx, p in enumerate(lista_exib):
                tem_comp = "Sim" if p['tem_complementar'] else "—"
                rows_plan.append({
                    '#':            idx + 1,
                    'Largura (mm)': p['largura'],
                    'Combinação':   _label_plano(p['itens']),
                    'Soma (mm)':    p['soma_mm'],
                    'Perda (mm)':   p['perda_mm'],
                    'Perda (%)':    p['perda_pct'],
                    'KG Útil':      round(sum(i['kg'] for i in p['itens'] if i['papel'] == 'ITEM'), 1),
                    'Compl.':       tem_comp,
                    'Status':       p['status'],
                })
            df_pl = pd.DataFrame(rows_plan)
            st.dataframe(
                df_pl,
                use_container_width=True, hide_index=True,
                column_config={
                    '#':            st.column_config.NumberColumn('#', width='small'),
                    'Largura (mm)': st.column_config.NumberColumn('Largura (mm)', width='small'),
                    'Soma (mm)':    st.column_config.NumberColumn('Soma (mm)', format='%.3f'),
                    'Perda (mm)':   st.column_config.NumberColumn('Perda (mm)', format='%.3f'),
                    'Perda (%)':    st.column_config.NumberColumn('Perda (%)', format='%.4f%%'),
                    'KG Útil':      st.column_config.NumberColumn('KG Útil', format='%.1f'),
                    'Status':       st.column_config.TextColumn('Status', width='small'),
                    'Compl.':       st.column_config.TextColumn('Compl.', width='small'),
                },
            )

    if not alloc:
        st.warning("Não foi possível gerar alocação sugerida (nenhum plano válido encontrado).")
        return

    # ── Alocação Sugerida ──────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="section-title">Alocação Sugerida de Bobinas</div>', unsafe_allow_html=True)

        total_bob   = sum(a['qtd'] for a in alloc)
        total_kg_al = sum(
            a['qtd'] * sum(i['kg'] for i in a['plano']['itens'] if i['papel'] == 'ITEM')
            for a in alloc
        )

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total de Bobinas", total_bob)
        mc2.metric("KG Útil Total",    f"{total_kg_al:,.0f} kg")
        mc3.metric("Peso Total (12 t/bobina)", f"{total_bob * PESO_BOBINA_KG / 1_000:.1f} ton")

        rows_al = []
        for a in alloc:
            p   = a['plano']
            qtd = a['qtd']
            kg_util = sum(i['kg'] for i in p['itens'] if i['papel'] == 'ITEM')
            rows_al.append({
                'Largura (mm)':  p['largura'],
                'Combinação':    _label_plano(p['itens']),
                'Perda (%)':     p['perda_pct'],
                'Status':        p['status'],
                'Qtd. Bobinas':  qtd,
                'KG Útil/Bob.':  round(kg_util, 1),
                'KG Útil Total': round(kg_util * qtd, 1),
            })
        st.dataframe(
            pd.DataFrame(rows_al),
            use_container_width=True, hide_index=True,
            column_config={
                'Largura (mm)':  st.column_config.NumberColumn('Largura (mm)', width='small'),
                'Perda (%)':     st.column_config.NumberColumn('Perda (%)', format='%.4f%%'),
                'Qtd. Bobinas':  st.column_config.NumberColumn('Qtd. Bobinas', width='small'),
                'KG Útil/Bob.':  st.column_config.NumberColumn('KG/Bob.', format='%.1f'),
                'KG Útil Total': st.column_config.NumberColumn('KG Total', format='%.1f'),
            },
        )

    # ── Resumo de Produção vs Necessidade ─────────────────────────────────────
    with st.container(border=True):
        st.markdown('<div class="section-title">Produção Estimada vs Necessidade</div>', unsafe_allow_html=True)

        rows_pr = []
        for cod, vals in prod.items():
            item_info   = next((i for i in st.session_state['sc2_itens'] if i['codigo'] == cod), {})
            pct_atend   = (vals['producao'] / vals['necessidade'] * 100) if vals['necessidade'] > 0 else 0
            rows_pr.append({
                'Código':              cod,
                'Descrição':           item_info.get('label', cod).split('—')[1].strip()[:40] if '—' in item_info.get('label', '') else '',
                'Necessidade (KG)':    vals['necessidade'],
                'Produção Est. (KG)':  vals['producao'],
                'Diferença (KG)':      vals['diferenca'],
                'Atendimento (%)':     round(pct_atend, 1),
            })
        df_pr = pd.DataFrame(rows_pr)

        def _style_dif(val):
            try:
                v = float(val)
                return 'color: #22c55e' if v >= 0 else 'color: #ef4444'
            except Exception:
                return ''

        def _style_atend(val):
            try:
                v = float(val)
                if v >= 100:
                    return 'color: #22c55e'
                if v >= 80:
                    return 'color: #f59e0b'
                return 'color: #ef4444'
            except Exception:
                return ''

        st.dataframe(
            df_pr.style
                .map(_style_dif,   subset=['Diferença (KG)'])
                .map(_style_atend, subset=['Atendimento (%)']),
            use_container_width=True, hide_index=True,
            column_config={
                'Necessidade (KG)':   st.column_config.NumberColumn('Necessidade (KG)',   format='%.0f'),
                'Produção Est. (KG)': st.column_config.NumberColumn('Produção Est. (KG)', format='%.1f'),
                'Diferença (KG)':     st.column_config.NumberColumn('Diferença (KG)',     format='%+.1f'),
                'Atendimento (%)':    st.column_config.NumberColumn('Atendimento (%)',     format='%.1f%%'),
            },
        )

        sobra_total = sum(v['diferenca'] for v in prod.values())
        if sobra_total >= 0:
            st.success(f"✅ Plano atende todas as necessidades com sobra de {sobra_total:,.0f} KG.")
        else:
            st.warning(f"⚠️ Plano cobre a maior parte das necessidades. Faltam {abs(sobra_total):,.0f} KG.")

    # ── Detalhes dos planos usados ─────────────────────────────────────────────
    with st.expander("Ver itens detalhados dos planos alocados", expanded=False):
        linhas_det = []
        for a in alloc:
            p = a['plano']
            for item in p['itens']:
                linhas_det.append({
                    'Largura (mm)':    p['largura'],
                    'Qtd. Bobinas':    a['qtd'],
                    'Papel':           item['papel'],
                    'Código':          item['codigo'],
                    'Desenv. (mm)':    item['desenvolvimento'],
                    'Nº Cortes':       item['n_cortes'],
                    'Subtotal (mm)':   item['subtotal_mm'],
                    'KG/Bobina':       item['kg'],
                    'KG Total':        round(item['kg'] * a['qtd'], 1),
                })
        if linhas_det:
            st.dataframe(
                pd.DataFrame(linhas_det),
                use_container_width=True, hide_index=True,
                column_config={
                    'Largura (mm)':  st.column_config.NumberColumn('Largura (mm)', width='small'),
                    'Qtd. Bobinas':  st.column_config.NumberColumn('Bobinas', width='small'),
                    'Papel':         st.column_config.TextColumn('Papel', width='small'),
                    'Desenv. (mm)':  st.column_config.NumberColumn('Desenv. (mm)', format='%.3f'),
                    'Nº Cortes':     st.column_config.NumberColumn('Nº Cortes', width='small'),
                    'Subtotal (mm)': st.column_config.NumberColumn('Subtotal (mm)', format='%.3f'),
                    'KG/Bobina':     st.column_config.NumberColumn('KG/Bob.', format='%.1f'),
                    'KG Total':      st.column_config.NumberColumn('KG Total', format='%.1f'),
                },
            )
        st.markdown(
            '<span class="tag-item">ITEM</span> &nbsp; item solicitado pelo usuário &emsp;'
            '<span class="tag-comp">COMPLEMENTAR</span> &nbsp; item do banco usado para completar a largura',
            unsafe_allow_html=True,
        )


if 'sc2_resultado' in st.session_state:
    resultado = st.session_state['sc2_resultado']

    st.markdown("<br>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="section-title">Planos de Corte</div>', unsafe_allow_html=True)

        tab_sol, tab_comp = st.tabs([
            "📦  Somente os Itens",
            "🔧  Com Complementares",
        ])

        with tab_sol:
            _render_tab(resultado['sol'], 'sol')

        with tab_comp:
            _render_tab(resultado['comp'], 'comp')


st.caption(
    f"Referência: bobinas de {PESO_BOBINA_KG:,} kg (12 ton) · "
    f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
