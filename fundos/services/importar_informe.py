"""
fundos/services/importar_informe.py

Persiste o resultado de parse_informe_mensal() no banco de dados.
Toda a operação é atômica: ou tudo é salvo, ou nada.
"""
from __future__ import annotations

import json
from decimal import Decimal
from datetime import date

from django.db import transaction

from fundos.models import Fundo, InformeMensal, InformeMensalCedente, InformeMensalCarteira


class InformeImportError(Exception):
    """Erros de validação de negócio durante a importação."""


def _clean_cnpj(raw: str) -> str:
    """Remove formatação de CNPJ (pontos, barras, traços)."""
    return ''.join(c for c in raw if c.isdigit())


def _to_json_safe(data: dict) -> dict:
    """Converte Decimals e dates para tipos JSON-serializáveis."""
    if isinstance(data, dict):
        return {k: _to_json_safe(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_to_json_safe(i) for i in data]
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, date):
        return data.isoformat()
    return data


@transaction.atomic
def importar_informe_mensal(
    fundo_id,
    parsed_dict: dict,
    user,
    arquivo_nome: str = '',
) -> InformeMensal:
    """
    Persiste (ou atualiza) um Informe Mensal a partir do dict retornado por
    parse_informe_mensal().

    Parâmetros
    ----------
    fundo_id   : UUID ou str — PK do Fundo
    parsed     : dict retornado por parse_informe_mensal()
    user       : instância de AUTH_USER_MODEL (pode ser None em testes)
    arquivo_nome : nome original do arquivo XML

    Retorna
    -------
    InformeMensal (criado ou atualizado)

    Lança
    -----
    InformeImportError — CNPJ do fundo não confere, ou fundo não encontrado
    """
    parsed = parsed_dict
    try:
        fundo = Fundo.objects.get(pk=fundo_id)
    except Fundo.DoesNotExist:
        raise InformeImportError(f"Fundo com id '{fundo_id}' não encontrado.")

    # ── Valida que o XML pertence a este fundo ────────────────
    cnpj_xml = _clean_cnpj(parsed['header'].get('cnpj_fundo', ''))
    cnpj_fundo = _clean_cnpj(fundo.cnpj)
    if cnpj_xml and cnpj_fundo and cnpj_xml != cnpj_fundo:
        raise InformeImportError(
            f"CNPJ do XML ({cnpj_xml}) não corresponde ao CNPJ do fundo selecionado ({cnpj_fundo})."
        )

    competencia = parsed['header']['competencia']
    header      = parsed['header']
    ativos      = parsed['ativos']
    passivo     = parsed['passivo']
    patrliq     = parsed['patrliq']
    cotas       = parsed['cotas_classes']
    rent        = parsed['rentabilidade']
    desemp      = parsed['desempenho']
    liq         = parsed['liquidez']
    venc        = parsed['vencimentos']
    capt        = parsed['captacao_resgate']
    scr         = parsed['scr']

    # ── Upsert InformeMensal ──────────────────────────────────
    informe, _ = InformeMensal.objects.update_or_create(
        fundo=fundo,
        competencia=competencia,
        defaults={
            'versao_xml':           header.get('versao') or '',
            'cnpj_administrador':   _clean_cnpj(header.get('cnpj_administrador', ''))[:14],
            'arquivo_xml_nome':     arquivo_nome[:255],
            'criado_por':           user,

            # Ativos
            'vl_disponib':          ativos.get('vl_disponib'),
            'vl_carteira':          ativos.get('vl_carteira'),
            'vl_total_ativos':      ativos.get('vl_total_ativos'),
            'vl_dicred':            ativos.get('vl_dicred'),
            'vl_dicred_cedent':     ativos.get('vl_dicred_cedent'),
            'vl_dicred_inad':       ativos.get('vl_dicred_inad'),
            'vl_dicred_venc_inad':  ativos.get('vl_dicred_venc_inad'),

            # Passivo
            'vl_total_passivo':     passivo.get('vl_total_passivo'),
            'vl_pgto_curprz':       passivo.get('vl_pgto_curprz'),
            'vl_pgto_lprazo':       passivo.get('vl_pgto_lprazo'),

            # PL
            'vl_patrimonio_liquido':        patrliq.get('vl_patrimonio_liquido'),
            'vl_patrimonio_liquido_medio':  patrliq.get('vl_patrimonio_liquido_medio'),

            # Cotas
            'qt_cotas_senior':  cotas.get('qt_cotas_senior'),
            'vl_cota_senior':   cotas.get('vl_cota_senior'),
            'qt_cotas_subord':  cotas.get('qt_cotas_subord'),
            'vl_cota_subord':   cotas.get('vl_cota_subord'),

            # Cotistas
            'qt_total_cotistas':  cotas.get('qt_total_cotistas'),
            'qt_cotistas_senior': cotas.get('qt_cotistas_senior'),
            'qt_cotistas_subord': cotas.get('qt_cotistas_subord'),

            # Rentabilidade
            'rentabilidade_senior': rent.get('rentabilidade_senior'),
            'rentabilidade_subord': rent.get('rentabilidade_subord'),

            # Desempenho
            'desemp_esp_senior':  desemp.get('desemp_esp_senior'),
            'desemp_real_senior': desemp.get('desemp_real_senior'),
            'desemp_esp_subord':  desemp.get('desemp_esp_subord'),
            'desemp_real_subord': desemp.get('desemp_real_subord'),

            # Liquidez
            'vl_liqdez_30':       liq.get('vl_liqdez_30'),
            'vl_liqdez_60':       liq.get('vl_liqdez_60'),
            'vl_liqdez_90':       liq.get('vl_liqdez_90'),
            'vl_liqdez_180':      liq.get('vl_liqdez_180'),
            'vl_liqdez_360':      liq.get('vl_liqdez_360'),
            'vl_liqdez_mais_360': liq.get('vl_liqdez_mais_360'),

            # Vencimentos
            'vl_venc_30':       venc.get('vl_venc_30'),
            'vl_venc_31_60':    venc.get('vl_venc_31_60'),
            'vl_venc_61_90':    venc.get('vl_venc_61_90'),
            'vl_venc_91_120':   venc.get('vl_venc_91_120'),
            'vl_venc_121_180':  venc.get('vl_venc_121_180'),
            'vl_venc_181_360':  venc.get('vl_venc_181_360'),
            'vl_venc_361_720':  venc.get('vl_venc_361_720'),
            'vl_venc_mais_720': venc.get('vl_venc_mais_720'),

            # Captação / Resgate
            'vl_capt_senior': capt.get('vl_capt_senior'),
            'vl_capt_subord': capt.get('vl_capt_subord'),
            'vl_resg_senior': capt.get('vl_resg_senior'),
            'vl_resg_subord': capt.get('vl_resg_subord'),

            # SCR
            'vl_rating_aa':  scr.get('vl_rating_aa'),
            'vl_rating_a':   scr.get('vl_rating_a'),
            'vl_rating_b':   scr.get('vl_rating_b'),
            'vl_rating_c':   scr.get('vl_rating_c'),
            'vl_rating_d_h': scr.get('vl_rating_d_h'),

            # Dados brutos para auditoria
            'dados_brutos': _to_json_safe(parsed),
        }
    )

    # ── Cedentes: apaga os anteriores e recria ────────────────
    informe.cedentes.all().delete()
    cedentes_objs = [
        InformeMensalCedente(
            informe=informe,
            nr_pf_pj_cedent=_clean_cnpj(c['nr_pf_pj_cedent'])[:14],
            pr_cedent=c.get('pr_cedent'),
        )
        for c in parsed.get('cedentes', [])
        if c.get('nr_pf_pj_cedent')
    ]
    if cedentes_objs:
        InformeMensalCedente.objects.bulk_create(cedentes_objs)

    # ── Carteira: apaga os anteriores e recria ────────────────
    informe.carteira.all().delete()
    vl_carteira = informe.vl_carteira or Decimal('0')
    carteira_objs = []
    for seg in parsed.get('carteira_segmentos', []):
        valor = seg.get('valor') or Decimal('0')
        if valor <= 0:
            continue
        pct = None
        if vl_carteira > 0:
            pct = (valor / vl_carteira * 100).quantize(Decimal('0.0001'))
        carteira_objs.append(
            InformeMensalCarteira(
                informe=informe,
                segmento=seg['segmento'],
                subsegmento=seg.get('subsegmento'),
                valor=valor,
                percentual_carteira=pct,
            )
        )
    if carteira_objs:
        InformeMensalCarteira.objects.bulk_create(carteira_objs)

    return informe
