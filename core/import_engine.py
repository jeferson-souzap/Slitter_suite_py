import sqlite3
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "slitter.db"
BACKUP_DIR = PROJECT_ROOT / "data" / "backup"

INPUT_DIR = Path(r"D:\#Mega\Jeferson - Dev\02 - Linguagens\Python\Acotel\Necessidade_Prod_Sliter_py\Files\input")

# ── Mapeamentos de colunas ────────────────────────────────────────────────────

_MAP_CRONOGRAMA = {
    'Maquina': 'maquina',
    'Tipo da ordem': 'tipo_ordem',
    'Unnamed: 1': 'seq',
    'Número do Item versão do sequenciamento': 'num_item_seq',
    'Matriz': 'matriz',
    'Modelo': 'modelo',
    'Material': 'material',
    'Descrição': 'descricao',
    'Quantidade': 'quantidade',
    'Unid.medida básica': 'unid_medida',
    'Quantidade peças': 'qtd_pecas',
    'Comprimento': 'comprimento',
    'Ordem': 'ordem',
    'Cliente': 'cliente',
    'Quantidade produzida': 'qtd_produzida',
    'Ordem de venda': 'ordem_venda',
    'Data Prevista': 'data_prevista',
    'Data sequenciamento': 'data_sequenciamento',
    'Hora início': 'hora_inicio',
    'Hora fim': 'hora_fim',
    'Setup Máquina': 'setup_maquina',
    'Intervalo': 'intervalo',
    'Turno': 'turno',
    'Tempo máquina': 'tempo_maquina',
    'ID Atraso': 'id_atraso',
    'Quantidade básica': 'qtd_basica',
    'Tempo referência operação': 'tempo_ref_operacao',
    'Unidade de tempo': 'unid_tempo',
    'Tempo referência operação em minutos': 'tempo_ref_min',
    'Nº do Sequenciamento': 'num_sequenciamento',
    'Plano de corte': 'plano_corte',
}

_MAP_ITENS = {
    'Ordem': 'ordem',
    'Material': 'material',
    'Lista comp.item': 'lista_comp_item',
    'Data de necessidade': 'data_necessidade',
    'Qtd.necessária (EINHEIT)': 'qtd_necessaria',
    'Qtd.retirada (EINHEIT)': 'qtd_retirada',
    'Unid.medida básica (=EINHEIT)': 'unid_medida',
    'Texto breve material': 'descricao',
    'Lote': 'lote',
    'Seqüência': 'sequencia',
    'Operação': 'operacao',
    'Item de reserva': 'item_reserva',
    'Centro': 'centro',
    'Depósito': 'deposito',
    'Ícone tipo mensagem': 'icone_msg',
    'Status do sistema': 'status_sistema',
}

_MAP_PROG = {
    'Ordem': 'ordem',
    'Ordem do cliente': 'ordem_cliente',
    'Item ord.cliente': 'item_ord_cliente',
    'Material': 'material',
    'Texto breve material': 'descricao',
    'Tipo de ordem': 'tipo_ordem',
    'Quantidade da ordem (GMEIN)': 'qtd_ordem',
    'Qtd.fornecida (GMEIN)': 'qtd_fornecida',
    'Ícone tipo mensagem': 'icone_msg',
    'Status do sistema': 'status_sistema',
    'Planejador MRP': 'planejador_mrp',
    'Centro': 'centro',
    'Versão': 'versao',
    'Texto descritivo': 'texto_descritivo',
    'Centro planej.': 'centro_planej',
    'Grupo roteiro': 'grupo_roteiro',
    'Data de produção': 'data_producao',
    'Centro planejamento': 'centro_planejamento',
    'Empresa solicitante': 'empresa_solicitante',
    'Status do usuário': 'status_usuario',
    'Lote': 'lote',
    'Criado por': 'criado_por',
    'Marc.p/elimin.': 'marc_elimin',
    'Data início básica': 'data_inicio_basica',
    'Data confirmada': 'data_confirmada',
    'Data conclusão (prog.)': 'data_conclusao_prog',
    'Data de início hora': 'hora_inicio',
    'Data de liberação real': 'data_liberacao_real',
    'Data fim confirmação': 'data_fim_confirmacao',
    'Data início progr.': 'data_inicio_progr',
    'Data fim básica': 'data_fim_basica',
    'Data de início prevista': 'data_inicio_prevista',
    'Data conclusão progr.': 'data_conclusao_progr',
    'Data fim prevista': 'data_fim_prevista',
    'Data real do fim': 'data_real_fim',
    'Data de conclusão base': 'data_conclusao_base',
    'Data início real': 'data_inicio_real',
    'Data-base iníc.': 'data_base_inicio',
    'Data início (prog.)': 'data_inicio_prog',
}

_MAP_ZPP001 = {
    'Dt. Exib.': 'dt_exib',
    'Centro': 'centro',
    'Matriz de Conformação': 'matriz',
    'Modelo': 'modelo',
    'Espessura Padrão (mm)': 'espessura',
    'Material': 'material',
    'Texto breve material': 'descricao',
    'Unid.medida básica': 'unid_medida',
    'Tipo de material': 'tipo_material_sap',
    'Denom.grupo merc.': 'grupo_merc',
    'Utilização livre': 'utilizacao_livre',
    'OC - Livre': 'oc_livre',
    'Tot.Crono 1': 'tot_crono_1',
    'Dt.Crono 1': 'dt_crono_1',
    'Tot.Crono 2': 'tot_crono_2',
    'Dt.Crono 2': 'dt_crono_2',
    'Tot.Remessas': 'tot_remessas',
    'Tot. OVs': 'tot_ovs',
    'Transfer.': 'transferencia',
    'Tot. Said': 'tot_saidas',
    'Est.Disp': 'est_disp',
    'Estq.Plan.': 'estq_plan',
    'Tipo de Aço': 'tipo_aco',
    'Aspecto': 'aspecto',
    'Cor': 'cor',
    'Especificação': 'especificacao',
    'Tolerância': 'tolerancia',
    'Largura (mm)': 'largura',
    'Tipo de Material': 'tipo_material',
    'Revestimento': 'revestimento',
}

# ── Helpers internos ──────────────────────────────────────────────────────────

def _machine_from_filename(filename: str) -> str:
    stem = Path(filename).stem  # CR-ITL130-1-EXPORT
    return stem.removeprefix('CR-').removesuffix('-EXPORT')


def _dates_to_str(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
    return df


def _fix_timedeltas(df: pd.DataFrame) -> pd.DataFrame:
    """Converte colunas com timedelta para string — ocorre quando hora passa da meia-noite."""
    import datetime
    for col in df.columns:
        if df[col].dtype == object:
            mask = df[col].apply(lambda v: isinstance(v, datetime.timedelta))
            if mask.any():
                df.loc[mask, col] = df.loc[mask, col].apply(
                    lambda v: str(v) if pd.notna(v) else None
                )
    return df


def _backup(files: list[Path]) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.exists():
            shutil.copy2(f, BACKUP_DIR / f.name)


def _ensure_metadata(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _METADATA (
            tabela      TEXT PRIMARY KEY,
            atualizado_em TEXT
        )
    """)


def _set_metadata(conn: sqlite3.Connection, tabela: str) -> str:
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "INSERT INTO _METADATA (tabela, atualizado_em) VALUES (?, ?) "
        "ON CONFLICT(tabela) DO UPDATE SET atualizado_em = excluded.atualizado_em",
        (tabela, ts),
    )
    return ts


def _table_exists(conn: sqlite3.Connection, tabela: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabela,)
    )
    return cur.fetchone() is not None


# ── Passo 01 — OP_CRONOGRAMA ──────────────────────────────────────────────────

def import_op_cronograma_from_files(arquivos) -> dict:
    """Recebe lista de file-like objects (UploadedFile do Streamlit ou Path)."""
    if not arquivos:
        return {'status': 'error', 'message': 'Nenhum arquivo fornecido.'}

    frames = []
    for f in arquivos:
        nome = f.name if hasattr(f, 'name') else Path(f).name
        df = pd.read_excel(f)
        df.insert(0, 'Maquina', _machine_from_filename(nome))
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True).rename(columns=_MAP_CRONOGRAMA)
    combined = _dates_to_str(combined, ['data_prevista', 'data_sequenciamento'])
    combined = _fix_timedeltas(combined)

    if 'modelo' in combined.columns:
        combined['modelo'] = combined['modelo'].astype(str)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)
        combined.to_sql('OP_CRONOGRAMA', conn, if_exists='replace', index=False)
        ts = _set_metadata(conn, 'OP_CRONOGRAMA')

    return {
        'status': 'success',
        'table': 'OP_CRONOGRAMA',
        'rows': len(combined),
        'machines': sorted(combined['maquina'].dropna().unique().tolist()),
        'atualizado_em': ts,
        'df': combined,
    }


def import_op_cronograma() -> dict:
    cr_files = sorted(INPUT_DIR.glob('CR-*-EXPORT.xlsx'))
    if not cr_files:
        return {'status': 'error', 'message': f'Nenhum CR-*-EXPORT.xlsx encontrado em {INPUT_DIR}'}

    _backup(cr_files)

    frames = []
    for f in cr_files:
        df = pd.read_excel(f)
        df.insert(0, 'Maquina', _machine_from_filename(f.name))
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True).rename(columns=_MAP_CRONOGRAMA)
    combined = _dates_to_str(combined, ['data_prevista', 'data_sequenciamento'])
    combined = _fix_timedeltas(combined)

    if 'modelo' in combined.columns:
        combined['modelo'] = combined['modelo'].astype(str)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)
        combined.to_sql('OP_CRONOGRAMA', conn, if_exists='replace', index=False)
        ts = _set_metadata(conn, 'OP_CRONOGRAMA')

    return {
        'status': 'success',
        'table': 'OP_CRONOGRAMA',
        'rows': len(combined),
        'machines': sorted(combined['maquina'].dropna().unique().tolist()),
        'atualizado_em': ts,
    }


# ── Passo 02 — Necessidade de Produção ───────────────────────────────────────

def import_necessidade_from_files(f_itens, f_prog, f_zpp001) -> dict:
    """Recebe file-like objects para ITENS_CRONOGRAMA, PROG e ZPP001."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        if not _table_exists(conn, 'OP_CRONOGRAMA'):
            return {
                'status': 'error',
                'message': 'Etapa 01 não concluída: tabela OP_CRONOGRAMA não encontrada.',
            }

    df_itens = pd.read_excel(f_itens).rename(columns=_MAP_ITENS)
    df_itens = _dates_to_str(df_itens, ['data_necessidade'])

    df_prog_df = pd.read_excel(f_prog)
    df_prog_df = df_prog_df.drop(columns=['Unnamed: 23'], errors='ignore')
    df_prog_df = df_prog_df.rename(columns=_MAP_PROG)
    date_cols_prog = [
        'data_confirmada', 'data_conclusao_prog', 'data_liberacao_real',
        'data_real_fim', 'data_conclusao_base', 'data_inicio_real',
        'data_base_inicio', 'data_inicio_prog',
    ]
    df_prog_df = _dates_to_str(df_prog_df, date_cols_prog)

    df_zpp = pd.read_excel(f_zpp001).rename(columns=_MAP_ZPP001)
    df_zpp = _dates_to_str(df_zpp, ['dt_exib', 'dt_crono_1', 'dt_crono_2'])

    results = {}
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)
        for table, df in [
            ('ITENS_CRONOGRAMA', df_itens),
            ('PROG',             df_prog_df),
            ('ZPP001',           df_zpp),
        ]:
            df.to_sql(table, conn, if_exists='replace', index=False)
            ts = _set_metadata(conn, table)
            results[table] = {'rows': len(df), 'atualizado_em': ts}

    return {'status': 'success', 'tables': results}


def import_necessidade() -> dict:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        if not _table_exists(conn, 'OP_CRONOGRAMA'):
            return {
                'status': 'error',
                'message': 'Passo 01 não executado: tabela OP_CRONOGRAMA não encontrada. '
                           'Execute import_op_cronograma() primeiro.',
            }

    f_itens  = INPUT_DIR / 'ITENS-CRONOGRAMA-EXPORT.xlsx'
    f_prog   = INPUT_DIR / 'PROG-EXPORT.xlsx'
    f_zpp001 = INPUT_DIR / 'ZPP001-EXPORT.xlsx'

    for f in (f_itens, f_prog, f_zpp001):
        if not f.exists():
            return {'status': 'error', 'message': f'Arquivo não encontrado: {f}'}

    _backup([f_itens, f_prog, f_zpp001])

    # ITENS_CRONOGRAMA
    df_itens = pd.read_excel(f_itens).rename(columns=_MAP_ITENS)
    df_itens = _dates_to_str(df_itens, ['data_necessidade'])

    # PROG
    df_prog = pd.read_excel(f_prog)
    df_prog = df_prog.drop(columns=['Unnamed: 23'], errors='ignore')
    df_prog = df_prog.rename(columns=_MAP_PROG)
    date_cols_prog = [
        'data_confirmada', 'data_conclusao_prog', 'data_liberacao_real',
        'data_real_fim', 'data_conclusao_base', 'data_inicio_real',
        'data_base_inicio', 'data_inicio_prog',
    ]
    df_prog = _dates_to_str(df_prog, date_cols_prog)

    # ZPP001
    df_zpp = pd.read_excel(f_zpp001).rename(columns=_MAP_ZPP001)
    df_zpp = _dates_to_str(df_zpp, ['dt_exib', 'dt_crono_1', 'dt_crono_2'])

    results = {}
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)

        for table, df in [
            ('ITENS_CRONOGRAMA', df_itens),
            ('PROG', df_prog),
            ('ZPP001', df_zpp),
        ]:
            df.to_sql(table, conn, if_exists='replace', index=False)
            ts = _set_metadata(conn, table)
            results[table] = {'rows': len(df), 'atualizado_em': ts}

    return {'status': 'success', 'tables': results}


# ── Passo 03 — Calcular Necessidade de Produção ──────────────────────────────

def _parse_largura(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace('.', '').replace(',', '.'))
    except Exception:
        return None


def _fecha_sozinho(largura_val) -> str:
    larg = _parse_largura(largura_val)
    if larg is None or larg <= 0:
        return ''
    opcoes = []
    for bw in [1000, 1200, 1500]:
        n_int = round(bw / larg)
        if n_int > 0 and abs(n_int * larg - bw) < 0.5:
            opcoes.append(f"{bw} - ({n_int} cortes)")
    return ' | '.join(opcoes)


def calcular_necessidade_prod() -> dict:
    required = ('OP_CRONOGRAMA', 'ITENS_CRONOGRAMA', 'ZPP001', 'PROG')

    with sqlite3.connect(DB_PATH) as conn:
        ausentes = [t for t in required if not _table_exists(conn, t)]
        if ausentes:
            return {
                'status': 'error',
                'message': f'Tabelas não encontradas: {ausentes}. '
                           f'Execute os passos anteriores primeiro.',
            }

        df_op   = pd.read_sql('SELECT * FROM OP_CRONOGRAMA',    conn)
        df_it   = pd.read_sql('SELECT * FROM ITENS_CRONOGRAMA', conn)
        df_zpp  = pd.read_sql('SELECT * FROM ZPP001',           conn)
        df_prog = pd.read_sql('SELECT * FROM PROG',             conn)

    # ── OP_CRONOGRAMA: filtro seq != 0 (equivalente ao script original) ──
    df_op = df_op[pd.to_numeric(df_op['num_item_seq'], errors='coerce').fillna(0) != 0].copy()

    # ── Itens: pendente por Ordem + Material ─────────────────────────────
    df_it = df_it[pd.to_numeric(df_it['qtd_necessaria'], errors='coerce').fillna(0) >= 1].copy()
    df_it['qtd_pendente'] = (
        pd.to_numeric(df_it['qtd_necessaria'], errors='coerce').fillna(0) -
        pd.to_numeric(df_it['qtd_retirada'],   errors='coerce').fillna(0)
    ).clip(lower=0)

    df_it = (
        df_it
        .groupby(['ordem', 'material', 'descricao'], as_index=False)['qtd_pendente']
        .sum()
    )
    df_it = df_it[df_it['qtd_pendente'] > 1]

    # ── Datas mínimas, máquinas e descrição pai por Ordem ─────────────────
    df_datas = df_op.groupby('ordem', as_index=False)['data_sequenciamento'].min()

    df_maquinas = (
        df_op
        .groupby('ordem', as_index=False)['maquina']
        .agg(lambda x: ' / '.join(sorted(x.dropna().unique())))
    )

    df_descricao = (
        df_op
        .groupby('ordem', as_index=False)['descricao']
        .agg(lambda x: ' / '.join(sorted(x.dropna().astype(str).unique())))
    )

    df = df_it.merge(df_datas,     on='ordem', how='left')
    df = df.merge(df_maquinas,     on='ordem', how='left')
    df = df.merge(df_descricao,    on='ordem', how='left', suffixes=('', '_pai'))

    # ── Estoque (ZPP001): apenas fitas slitter ────────────────────────────
    df_est = df_zpp[df_zpp['grupo_merc'] == 'IN - FITA SLITTER'][[
        'material', 'utilizacao_livre', 'matriz', 'espessura',
        'largura', 'tipo_aco', 'tipo_material',
    ]].copy()
    df_est['utilizacao_livre'] = pd.to_numeric(df_est['utilizacao_livre'], errors='coerce').fillna(0)

    # ── Programadas (PROG) ────────────────────────────────────────────────
    df_prog['qtd_programada'] = (
        pd.to_numeric(df_prog['qtd_ordem'],    errors='coerce').fillna(0) -
        pd.to_numeric(df_prog['qtd_fornecida'], errors='coerce').fillna(0)
    ).clip(lower=0)

    df_prog_agg = df_prog.groupby('material', as_index=False)['qtd_programada'].sum()

    # ── Merge final ───────────────────────────────────────────────────────
    df = df.merge(df_est,      on='material', how='left')
    df = df.merge(df_prog_agg, on='material', how='left')

    df['utilizacao_livre'] = df['utilizacao_livre'].fillna(0)
    df['qtd_programada']   = df['qtd_programada'].fillna(0)
    df['saldo_inicial']    = df['utilizacao_livre'] + df['qtd_programada']

    # ── FIFO por material ─────────────────────────────────────────────────
    df = df.sort_values('data_sequenciamento').reset_index(drop=True)
    df['demanda_acumulada'] = df.groupby('material')['qtd_pendente'].cumsum()
    df['saldo_projetado']   = df['saldo_inicial'] - df['demanda_acumulada']
    df['status']            = df['saldo_projetado'].apply(lambda x: 'Ok' if x >= 0 else 'Programar')
    df['fecha_sozinho']     = df['largura'].apply(_fecha_sozinho)

    df_nec = df[[
        'ordem', 'maquina', 'descricao_pai', 'material', 'descricao',
        'espessura', 'largura', 'tipo_aco', 'tipo_material', 'matriz',
        'data_sequenciamento', 'qtd_pendente', 'utilizacao_livre',
        'qtd_programada', 'saldo_inicial', 'demanda_acumulada',
        'saldo_projetado', 'status', 'fecha_sozinho',
    ]].copy()

    # ── Resumo Detalhado ──────────────────────────────────────────────────
    df_res = (
        df.groupby(
            ['espessura', 'tipo_aco', 'tipo_material', 'material', 'descricao'],
            dropna=False,
        )
        .agg(
            maquinas          = ('maquina',          lambda x: ' / '.join(sorted(x.dropna().unique()))),
            descricao_pai     = ('descricao_pai',    lambda x: ' / '.join(sorted(x.dropna().astype(str).unique()))),
            matriz            = ('matriz',            'first'),
            qtd_demanda_total = ('qtd_pendente',     'sum'),
            utilizacao_livre  = ('utilizacao_livre', 'first'),
            qtd_programada    = ('qtd_programada',   'first'),
            saldo_inicial     = ('saldo_inicial',    'first'),
        )
        .reset_index()
    )

    df_res['qtd_a_programar'] = (df_res['qtd_demanda_total'] - df_res['saldo_inicial']).clip(lower=0)
    df_res = df_res[df_res['qtd_a_programar'] > 0].copy()
    df_res = df_res.sort_values(
        ['espessura', 'tipo_aco', 'qtd_a_programar'],
        ascending=[True, True, False],
    ).reset_index(drop=True)

    df_res = df_res[[
        'espessura', 'tipo_aco', 'tipo_material', 'material', 'descricao',
        'maquinas', 'descricao_pai', 'matriz',
        'qtd_demanda_total', 'utilizacao_livre', 'qtd_programada',
        'saldo_inicial', 'qtd_a_programar',
    ]]

    # ── Salvar no banco ───────────────────────────────────────────────────
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)
        df_nec.to_sql('NECESSIDADE',      conn, if_exists='replace', index=False)
        df_res.to_sql('RESUMO_DETALHADO', conn, if_exists='replace', index=False)
        ts_nec = _set_metadata(conn, 'NECESSIDADE')
        ts_res = _set_metadata(conn, 'RESUMO_DETALHADO')

    return {
        'status': 'success',
        'tables': {
            'NECESSIDADE':      {'rows': len(df_nec), 'atualizado_em': ts_nec},
            'RESUMO_DETALHADO': {'rows': len(df_res), 'atualizado_em': ts_res},
        },
        'resumo': {
            'status_ok':       int((df_nec['status'] == 'Ok').sum()),
            'status_programar': int((df_nec['status'] == 'Programar').sum()),
            'qtd_a_programar_total': float(df_res['qtd_a_programar'].sum()),
            'skus_a_programar': int(len(df_res)),
        },
    }


# ── Estoque de Bobinas (EWMW) ────────────────────────────────────────────────

_MAP_EWMW = {
    'Produto':                          'material',
    'Descrição breve do produto':       'descricao',
    'Quantidade':                       'quantidade',
    'Lote':                             'lote',
    'UM básica':                        'unid_medida',
    'Posição no depósito':              'posicao_deposito',
    'Data EM':                          'data_em',
    'Hr.entr.mercadorias':              'hora_entrada',
    'Tipo de estoque':                  'tipo_estoque',
    'Denominação do tipo de estoque':   'denom_tipo_estoque',
    'Ordem do cliente/projeto':         'ordem_cliente',
    'Item ordem cliente':               'item_ordem_cliente',
    'Documento':                        'documento',
    'Tipo de depósito':                 'tipo_deposito',
    'Tipo':                             'tipo',
}


def _parse_desc_bobina(descricao: str) -> tuple:
    """Retorna (tipo_material, tipo_aco, espessura, largura, fora_padrao)."""
    import re
    if not descricao or pd.isna(descricao):
        return None, None, None, None, False

    partes = str(descricao).strip().split()
    tipo_material = partes[0] if partes else None
    tipo_aco      = partes[1] if len(partes) > 1 else None

    fora_padrao = 'XFP' in str(descricao).upper()

    # Espessura: número com vírgula/ponto imediatamente antes de X ou de MM
    m = re.search(r'(\d+[.,]\d+)\s*[Xx]', descricao)
    if not m:
        m = re.search(r'(\d+[.,]\d+)\s*MM', descricao, re.IGNORECASE)
    espessura = float(m.group(1).replace(',', '.')) if m else None

    # Largura: apenas para BB e somente quando há dimensão explícita (não XFP)
    largura = None
    if tipo_material == 'BB' and not fora_padrao:
        ml = re.search(r'[Xx](\d+(?:[.,]\d+)?)\s*MM', descricao, re.IGNORECASE)
        largura = float(ml.group(1).replace(',', '.')) if ml else None

    return tipo_material, tipo_aco, espessura, largura, fora_padrao


def import_estoque_bobinas(arquivo) -> dict:
    """Importa EWMW-EXPORT.xlsx acumulando no banco (uma linha por lote/posição/dia)."""
    from datetime import date as _date

    df = pd.read_excel(arquivo)
    df = df.rename(columns=_MAP_EWMW)
    df = _dates_to_str(df, ['data_em'])

    hoje = _date.today().isoformat()
    df['data_importacao'] = hoje

    # Colunas derivadas da descrição
    parsed = df['descricao'].apply(
        lambda d: pd.Series(
            _parse_desc_bobina(d),
            index=['tipo_material', 'tipo_aco', 'espessura', 'largura', 'fora_padrao'],
        )
    )
    df = pd.concat([df, parsed], axis=1)

    # status_90: "90+" se o material está em estoque há mais de 90 dias
    df['dias_estoque'] = (
        pd.to_datetime(hoje) - pd.to_datetime(df['data_em'], errors='coerce')
    ).dt.days
    df['status_90'] = df['dias_estoque'].apply(
        lambda d: '90+' if pd.notna(d) and d > 90 else 'Ok'
    )

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_metadata(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ESTOQUE_BOBINAS (
                data_importacao TEXT,
                material        INTEGER,
                descricao       TEXT,
                quantidade      REAL,
                lote            TEXT,
                unid_medida     TEXT,
                posicao_deposito TEXT,
                data_em         TEXT,
                hora_entrada    TEXT,
                tipo_estoque    TEXT,
                denom_tipo_estoque TEXT,
                ordem_cliente   INTEGER,
                item_ordem_cliente INTEGER,
                documento       REAL,
                tipo_deposito   TEXT,
                tipo            TEXT,
                tipo_material   TEXT,
                tipo_aco        TEXT,
                espessura       REAL,
                largura         REAL,
                fora_padrao     INTEGER,
                dias_estoque    REAL,
                status_90       TEXT
            )
        """)
        # Remove importação anterior do mesmo dia (mantém apenas a última)
        conn.execute(
            "DELETE FROM ESTOQUE_BOBINAS WHERE data_importacao = ?", (hoje,)
        )
        df.to_sql('ESTOQUE_BOBINAS', conn, if_exists='append', index=False)
        ts = _set_metadata(conn, 'ESTOQUE_BOBINAS')

    return {
        'status': 'success',
        'rows': len(df),
        'data_importacao': hoje,
        'atualizado_em': ts,
    }


# ── Configurações de usuário ──────────────────────────────────────────────────

def _ensure_configuracoes(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CONFIGURACOES (
            usuario TEXT NOT NULL,
            chave   TEXT NOT NULL,
            valor   TEXT,
            PRIMARY KEY (usuario, chave)
        )
    """)


def get_configuracao(usuario: str, chave: str) -> str | None:
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as conn:
        if not _table_exists(conn, 'CONFIGURACOES'):
            return None
        cur = conn.execute(
            "SELECT valor FROM CONFIGURACOES WHERE usuario=? AND chave=?",
            (usuario, chave),
        )
        row = cur.fetchone()
        return row[0] if row else None


def set_configuracao(usuario: str, chave: str, valor: str) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        _ensure_configuracoes(conn)
        conn.execute(
            "INSERT INTO CONFIGURACOES (usuario, chave, valor) VALUES (?, ?, ?) "
            "ON CONFLICT(usuario, chave) DO UPDATE SET valor = excluded.valor",
            (usuario, chave, valor),
        )


# ── Utilitários públicos ──────────────────────────────────────────────────────

def get_metadata() -> dict:
    if not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        if not _table_exists(conn, '_METADATA'):
            return {}
        cur = conn.execute("SELECT tabela, atualizado_em FROM _METADATA ORDER BY tabela")
        return {row[0]: row[1] for row in cur.fetchall()}


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)
