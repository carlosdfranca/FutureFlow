"""
fundos/services/informe_xml.py

Parser do XML do Informe Mensal CVM (formato DOC_ARQ, versão 6.x).
Retorna um dict estruturado com todos os dados relevantes para persistência.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import date
import xml.etree.ElementTree as ET


# ============================================================
# Exceptions
# ============================================================

class InformeParseError(Exception):
    """Erros de parsing ou validação do Informe Mensal XML."""


# ============================================================
# Helpers
# ============================================================

def _text(element, tag: str) -> str | None:
    """Busca o texto de um sub-elemento. Retorna None se não encontrado."""
    node = element.find(tag)
    if node is None or node.text is None:
        return None
    return node.text.strip()


def _dec(element, tag: str) -> Decimal | None:
    """
    Extrai um valor Decimal de um sub-elemento cujo texto está no formato BR
    (separador de milhar = '.', decimal = ','), ex: "12.000.000,00".
    Retorna None se elemento não existir ou valor for zero/vazio.
    """
    raw = _text(element, tag)
    return _to_decimal_br(raw)


def _to_decimal_br(raw: str | None) -> Decimal | None:
    """Converte string no formato BR para Decimal. Retorna None se inválido."""
    if not raw:
        return None
    # Remove separador de milhar e troca vírgula decimal por ponto
    cleaned = raw.replace('.', '').replace(',', '.')
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _int(element, tag: str) -> int | None:
    """Extrai inteiro de sub-elemento."""
    raw = _text(element, tag)
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _parse_competencia(raw: str | None) -> date:
    """
    Converte 'MM/AAAA' → date(year, month, 1).
    Ex: '02/2026' → date(2026, 2, 1).
    """
    if not raw:
        raise InformeParseError("Campo DT_COMPT ausente no XML.")
    try:
        mes, ano = raw.strip().split('/')
        return date(int(ano), int(mes), 1)
    except (ValueError, AttributeError):
        raise InformeParseError(f"Formato inválido para DT_COMPT: '{raw}'. Esperado MM/AAAA.")


# ============================================================
# Mapeamento CART_SEGMT → SegmentoCarteira
# ============================================================

# (tag_xml, segmento, subsegmento)
_CARTEIRA_MAP: list[tuple[str, str, str | None]] = [
    # Industrial
    ('VL_IND',                          'INDUSTRIAL',           None),
    # Mercado Imobiliário (não tem segmento próprio → OUTROS)
    ('VL_MERC_IMOBIL',                  'OUTROS',               'IMOBILIARIO'),
    # Comercial
    ('VL_COMERC',                       'COMERCIAL',            'GERAL'),
    ('VL_COMERC_VARJ',                  'COMERCIAL',            'VAREJO'),
    ('VL_ARREND_MERCNT',                'COMERCIAL',            'ARRENDAMENTO'),
    # Serviços
    ('VL_SERV',                         'SERVICOS',             'GERAL'),
    ('VL_SERV_PUBLIC',                  'SERVICOS',             'PUBLICO'),
    ('VL_SERV_EDUC',                    'SERVICOS',             'EDUCACAO'),
    ('VL_SERV_ENTRETEN',                'SERVICOS',             'ENTRETENIMENTO'),
    # Agronegócio
    ('VL_AGRONEG',                      'AGRONEG',              None),
    # Financeiro
    ('VL_FINANC_CRED_PESSOA',           'FINANCEIRO',           'CRED_PESSOA'),
    ('VL_FINANC_CRED_PESSOA_CONSIG',    'FINANCEIRO',           'CONSIG'),
    ('VL_FINANC_CRED_CORPOR',           'FINANCEIRO',           'CORPORATIVO'),
    ('VL_FINANC_MMARKET',               'FINANCEIRO',           'MONEY_MARKET'),
    ('VL_FINANC_VEICL',                 'FINANCEIRO',           'VEICULOS'),
    ('VL_FINANC_IMOBIL_EMPSRL',         'FINANCEIRO',           'IMOBIL_EMPRESARIAL'),
    ('VL_FINANC_IMOBIL_RESID',          'FINANCEIRO',           'IMOBIL_RESIDENCIAL'),
    ('VL_FINANC_OUTRO',                 'FINANCEIRO',           'OUTRO'),
    # Cartão de Crédito
    ('VL_CART_CRED',                    'CARTAO_CREDITO',       None),
    # Factoring
    ('VL_FACT_PESSOA',                  'FACTORING',            'PESSOA'),
    ('VL_FACT_CORPOR',                  'FACTORING',            'CORPORATIVO'),
    # Setor Público
    ('VL_SETOR_PUBLIC_PRECAT',          'SETOR_PUBLICO',        'PRECAT'),
    ('VL_SETOR_PUBLIC_CRED_TRIBUT',     'SETOR_PUBLICO',        'CRED_TRIBUT'),
    ('VL_SETOR_PUBLIC_ROYA',            'SETOR_PUBLICO',        'ROYALTIES'),
    ('VL_SETOR_PUBLIC_OUTRO',           'SETOR_PUBLICO',        'OUTRO'),
    # Ação Judicial
    ('VL_ACAO_JUDIC',                   'ACAO_JUDIC',           None),
    # Valores Mobiliários
    ('VL_DEBT',                         'VALORES_MOBILIARIOS',  'DEBENTURES'),
    ('VL_CRI',                          'VALORES_MOBILIARIOS',  'CRI'),
    ('VL_NP_COMERC',                    'VALORES_MOBILIARIOS',  'NOTA_COMERCIAL'),
    ('VL_LETRA_FINANC',                 'VALORES_MOBILIARIOS',  'LETRA_FINANCEIRA'),
    ('VL_CLS_COTA_FIF',                 'VALORES_MOBILIARIOS',  'COTA_FIF'),
    ('VL_OUTRO_DICRED',                 'VALORES_MOBILIARIOS',  'OUTRO_DICRED'),
    # Outros
    ('VL_PROPRD_MARCA_PATENT',          'OUTROS',               'PROPRIEDADE_INTELECTUAL'),
]


def _parse_carteira(root: ET.Element) -> list[dict]:
    """
    Extrai a composição da carteira por segmento/subsegmento.
    Retorna apenas registros com valor > 0.
    """
    cart = root.find('LISTA_INFORM/CART_SEGMT')
    if cart is None:
        return []

    # Tags aninhadas por seção
    _SECTION_PARENTS = {
        'VL_COMERC':                'SEGMT_COMERC',
        'VL_COMERC_VARJ':           'SEGMT_COMERC',
        'VL_ARREND_MERCNT':         'SEGMT_COMERC',
        'VL_SERV':                  'SEGMT_SERV',
        'VL_SERV_PUBLIC':           'SEGMT_SERV',
        'VL_SERV_EDUC':             'SEGMT_SERV',
        'VL_SERV_ENTRETEN':         'SEGMT_SERV',
        'VL_FINANC_CRED_PESSOA':    'SEGMT_FINANC',
        'VL_FINANC_CRED_PESSOA_CONSIG': 'SEGMT_FINANC',
        'VL_FINANC_CRED_CORPOR':    'SEGMT_FINANC',
        'VL_FINANC_MMARKET':        'SEGMT_FINANC',
        'VL_FINANC_VEICL':          'SEGMT_FINANC',
        'VL_FINANC_IMOBIL_EMPSRL':  'SEGMT_FINANC',
        'VL_FINANC_IMOBIL_RESID':   'SEGMT_FINANC',
        'VL_FINANC_OUTRO':          'SEGMT_FINANC',
        'VL_FACT_PESSOA':           'SEGMT_FACT',
        'VL_FACT_CORPOR':           'SEGMT_FACT',
        'VL_SETOR_PUBLIC_PRECAT':   'SEGMT_SETOR_PUBLIC',
        'VL_SETOR_PUBLIC_CRED_TRIBUT': 'SEGMT_SETOR_PUBLIC',
        'VL_SETOR_PUBLIC_ROYA':     'SEGMT_SETOR_PUBLIC',
        'VL_SETOR_PUBLIC_OUTRO':    'SEGMT_SETOR_PUBLIC',
    }

    # Valores Mobiliários ficam em APLIC_ATIVO/VALORES_MOB
    _VALORES_MOB_TAGS = {
        'VL_DEBT', 'VL_CRI', 'VL_NP_COMERC',
        'VL_LETRA_FINANC', 'VL_CLS_COTA_FIF', 'VL_OUTRO_DICRED',
    }

    valores_mob_node = root.find('LISTA_INFORM/APLIC_ATIVO/VALORES_MOB')

    result = []
    for tag, segmento, subsegmento in _CARTEIRA_MAP:
        if tag in _VALORES_MOB_TAGS:
            valor = _dec(valores_mob_node, tag) if valores_mob_node is not None else None
        elif tag in _SECTION_PARENTS:
            parent_node = cart.find(_SECTION_PARENTS[tag])
            valor = _dec(parent_node, tag) if parent_node is not None else None
        else:
            valor = _dec(cart, tag)

        if valor and valor > 0:
            result.append({
                'segmento': segmento,
                'subsegmento': subsegmento,
                'valor': valor,
            })

    return result


# ============================================================
# Parser principal
# ============================================================

def parse_informe_mensal(xml_bytes: bytes) -> dict:
    """
    Parseia o XML do Informe Mensal CVM (formato DOC_ARQ).

    Retorna um dict com as chaves:
        header, ativos, passivo, patrliq, cedentes, carteira_segmentos,
        cotas_classes, rentabilidade, desempenho, liquidez, vencimentos,
        captacao_resgate, scr

    Lança InformeParseError em caso de XML inválido ou campos obrigatórios ausentes.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise InformeParseError(f"XML inválido: {exc}") from exc

    cab = root.find('CAB_INFORM')
    if cab is None:
        raise InformeParseError("Elemento CAB_INFORM não encontrado. Verifique se é um Informe Mensal CVM.")

    lista = root.find('LISTA_INFORM')
    if lista is None:
        raise InformeParseError("Elemento LISTA_INFORM não encontrado.")

    # ── Header ────────────────────────────────────────────────
    header = {
        'versao':            _text(cab, 'VERSAO'),
        'competencia_raw':   _text(cab, 'DT_COMPT'),
        'competencia':       _parse_competencia(_text(cab, 'DT_COMPT')),
        'cnpj_administrador': _text(cab, 'NR_CNPJ_ADM') or '',
        'cnpj_fundo':        _text(cab, 'NR_CNPJ_FUNDO') or '',
        'nome_fundo':        _text(cab, 'NM_CLASSE') or '',
    }

    # ── Ativos ────────────────────────────────────────────────
    aplic = lista.find('APLIC_ATIVO')
    dicred_node = aplic.find('DICRED') if aplic is not None else None
    ativos = {
        'vl_disponib':      _dec(aplic, 'VL_DISPONIB'),
        'vl_carteira':      _dec(aplic, 'VL_CARTEIRA'),
        'vl_total_ativos':  _dec(aplic, 'VL_SOM_APLIC_ATIVO'),
        'vl_dicred':        _dec(dicred_node, 'VL_DICRED'),
        'vl_dicred_cedent': _dec(dicred_node, 'VL_DICRED_CEDENT'),
        'vl_dicred_inad':   _dec(dicred_node, 'VL_DICRED_EXISTE_INAD'),
        'vl_dicred_venc_inad': _dec(dicred_node, 'VL_DICRED_TOTAL_VENC_INAD'),
    }

    # ── Cedentes ──────────────────────────────────────────────
    cedentes = []
    lista_cedent = aplic.find('LISTA_CEDENT') if aplic is not None else None
    if lista_cedent is not None:
        for ced in lista_cedent.findall('CEDENT'):
            cnpj_ced = _text(ced, 'NR_PF_PJ_CEDENT')
            pr = _dec(ced, 'PR_CEDENT')
            if cnpj_ced:
                cedentes.append({'nr_pf_pj_cedent': cnpj_ced, 'pr_cedent': pr})

    # ── Passivo ───────────────────────────────────────────────
    passiv = lista.find('PASSIV')
    passiv_val = passiv.find('PASSIV_VALORES') if passiv is not None else None
    passivo = {
        'vl_total_passivo': _dec(passiv, 'VL_SOM_PASSIV'),
        'vl_pgto_curprz':   _dec(passiv_val, 'VL_PGTO_CURPRZ'),
        'vl_pgto_lprazo':   _dec(passiv_val, 'VL_PGTO_LPRAZO'),
    }

    # ── PL ────────────────────────────────────────────────────
    patrliq = lista.find('PATRLIQ')
    pl = {
        'vl_patrimonio_liquido':       _dec(patrliq, 'VL_PATRIM_LIQ'),
        'vl_patrimonio_liquido_medio': _dec(patrliq, 'VL_PATRIM_LIQ_MEDIO'),
    }

    # ── Cotas e Cotistas ──────────────────────────────────────
    outras = lista.find('OUTRAS_INFORM')
    num_cot = outras.find('NUM_COTISTAS') if outras is not None else None
    desc_serie = outras.find('DESC_SERIE_CLASSE') if outras is not None else None

    cotas_classes = {
        'qt_total_cotistas':  _int(num_cot, 'QT_TOTAL_COTISTAS'),
        'qt_cotistas_senior': _int(num_cot, 'QT_TOTAL_COTISTAS_SENIOR'),
        'qt_cotistas_subord': _int(num_cot, 'QT_TOTAL_COTISTAS_SUBORD'),
    }
    if desc_serie is not None:
        senior = desc_serie.find('DESC_SERIE_CLASSE_SENIOR')
        subord = desc_serie.find('DESC_SERIE_CLASSE_SUBORD')
        cotas_classes.update({
            'qt_cotas_senior': _dec(senior, 'QT_COTAS') if senior is not None else None,
            'vl_cota_senior':  _dec(senior, 'VL_COTAS')  if senior is not None else None,
            'qt_cotas_subord': _dec(subord, 'QT_COTAS') if subord is not None else None,
            'vl_cota_subord':  _dec(subord, 'VL_COTAS')  if subord is not None else None,
        })

    # ── Rentabilidade ─────────────────────────────────────────
    rent_mes = outras.find('RENT_MES') if outras is not None else None
    rentabilidade = {
        'rentabilidade_senior': None,
        'rentabilidade_subord': None,
    }
    if rent_mes is not None:
        rent_s = rent_mes.find('RENT_CLASSE_SENIOR')
        rent_sub = rent_mes.find('RENT_CLASSE_SUBORD')
        if rent_s is not None:
            rentabilidade['rentabilidade_senior'] = _to_decimal_br(_text(rent_s, 'PR_APURADA'))
        if rent_sub is not None:
            rentabilidade['rentabilidade_subord'] = _to_decimal_br(_text(rent_sub, 'PR_APURADA'))

    # ── Desempenho ────────────────────────────────────────────
    desemp_node = outras.find('DESEMP') if outras is not None else None
    desempenho = {
        'desemp_esp_senior':  None,
        'desemp_real_senior': None,
        'desemp_esp_subord':  None,
        'desemp_real_subord': None,
    }
    if desemp_node is not None:
        ds = desemp_node.find('CLASSE_SENIOR')
        dsub = desemp_node.find('CLASSE_SUBORD')
        if ds is not None:
            desempenho['desemp_esp_senior']  = _to_decimal_br(_text(ds, 'DESEMP_ESP'))
            desempenho['desemp_real_senior'] = _to_decimal_br(_text(ds, 'DESEMP_REAL'))
        if dsub is not None:
            desempenho['desemp_esp_subord']  = _to_decimal_br(_text(dsub, 'DESEMP_ESP'))
            desempenho['desemp_real_subord'] = _to_decimal_br(_text(dsub, 'DESEMP_REAL'))

    # ── Liquidez ──────────────────────────────────────────────
    liqdez_node = outras.find('LIQUIDEZ') if outras is not None else None
    liquidez = {
        'vl_liqdez_30':       _dec(liqdez_node, 'VL_ATIV_LIQDEZ_30'),
        'vl_liqdez_60':       _dec(liqdez_node, 'VL_ATIV_LIQDEZ_60'),
        'vl_liqdez_90':       _dec(liqdez_node, 'VL_ATIV_LIQDEZ_90'),
        'vl_liqdez_180':      _dec(liqdez_node, 'VL_ATIV_LIQDEZ_180'),
        'vl_liqdez_360':      _dec(liqdez_node, 'VL_ATIV_LIQDEZ_360'),
        'vl_liqdez_mais_360': _dec(liqdez_node, 'VL_ATIV_LIQDEZ_MAIS_360'),
    }

    # ── Perfil de vencimentos (sem aquisição) ─────────────────
    venc_node = lista.find('COMPMT_DICRED_SEM_AQUIS')
    vencimentos = {
        'vl_venc_30':      _dec(venc_node, 'VL_PRAZO_VENC_30'),
        'vl_venc_31_60':   _dec(venc_node, 'VL_PRAZO_VENC_31_60'),
        'vl_venc_61_90':   _dec(venc_node, 'VL_PRAZO_VENC_61_90'),
        'vl_venc_91_120':  _dec(venc_node, 'VL_PRAZO_VENC_91_120'),
        'vl_venc_121_180': _dec(venc_node, 'VL_PRAZO_VENC_121_150'),
        'vl_venc_181_360': _dec(venc_node, 'VL_PRAZO_VENC_151_180'),
        'vl_venc_361_720': _dec(venc_node, 'VL_PRAZO_VENC_361_720'),
        'vl_venc_mais_720': _dec(venc_node, 'VL_PRAZO_VENC_1080'),
    }

    # ── Captação / Resgate ────────────────────────────────────
    capt_resga = outras.find('CAPTA_RESGA_AMORTI') if outras is not None else None
    captacao_resgate = {
        'vl_capt_senior': None,
        'vl_capt_subord': None,
        'vl_resg_senior': None,
        'vl_resg_subord': None,
    }
    if capt_resga is not None:
        capt = capt_resga.find('CAPT_MES')
        resg = capt_resga.find('RESG_MES')
        if capt is not None:
            s = capt.find('CLASSE_SENIOR')
            sub = capt.find('CLASSE_SUBORD')
            captacao_resgate['vl_capt_senior'] = _dec(s, 'VL_TOTAL') if s is not None else None
            captacao_resgate['vl_capt_subord'] = _dec(sub, 'VL_TOTAL') if sub is not None else None
        if resg is not None:
            s = resg.find('CLASSE_SENIOR')
            sub = resg.find('CLASSE_SUBORD')
            captacao_resgate['vl_resg_senior'] = _dec(s, 'VL_TOTAL') if s is not None else None
            captacao_resgate['vl_resg_subord'] = _dec(sub, 'VL_TOTAL') if sub is not None else None

    # ── Rating SCR ────────────────────────────────────────────
    scr_node = outras.find('RES_INF_PRST_SCR') if outras is not None else None
    devd_node = scr_node.find('VLR_TOTAL_DIR_CRD_DEVD') if scr_node is not None else None
    scr = {
        'vl_rating_aa':  _dec(devd_node, 'AA'),
        'vl_rating_a':   _dec(devd_node, 'A'),
        'vl_rating_b':   _dec(devd_node, 'B'),
        'vl_rating_c':   _dec(devd_node, 'C'),
        'vl_rating_d_h': None,
    }
    if devd_node is not None:
        d_h_total = sum(
            v for tag in ('D', 'E', 'F', 'G', 'H')
            if (v := _to_decimal_br(_text(devd_node, tag))) is not None
        )
        scr['vl_rating_d_h'] = d_h_total if d_h_total else None

    return {
        'header':              header,
        'ativos':              ativos,
        'passivo':             passivo,
        'patrliq':             pl,
        'cedentes':            cedentes,
        'carteira_segmentos':  _parse_carteira(root),
        'cotas_classes':       cotas_classes,
        'rentabilidade':       rentabilidade,
        'desempenho':          desempenho,
        'liquidez':            liquidez,
        'vencimentos':         vencimentos,
        'captacao_resgate':    captacao_resgate,
        'scr':                 scr,
    }
