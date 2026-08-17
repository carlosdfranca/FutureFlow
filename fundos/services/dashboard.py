"""
Serviço de agregação para o Dashboard do Fundo.

Monta o contexto de dados (KPIs executivos, enquadramento, série histórica,
saúde da carteira, concentração e distribuição de risco) consumido por
`fundos/templates/fundos/dashboard_fundo.html`.

Cada bloco degrada graciosamente para vazio (None/0/[]) quando não há dado --
o template esconde o bloco correspondente. Isso é o que permite o mesmo
template atender FIDC (rico em títulos/cessões e Informes Mensais) e FII/FIP
(hoje sem esses dados): os blocos que dependem deles simplesmente não aparecem.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth

from fundos.models import InformeMensal
from operacoes.models import Titulo, Aplicacao
from .enquadramento import avaliar_enquadramento

# Ordem fixa de exibição do rating (AA = melhor, H = pior) -- usada para que os
# baldes apareçam sempre na mesma ordem no gráfico, mesmo quando algum não tem saldo.
ORDEM_RISCO = ['AA', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

# Quantas competências de Informe Mensal entram na série histórica (2 anos).
MESES_HISTORICO = 24


def _pct(parte, total):
    if not total:
        return None
    return (Decimal(parte or 0) / total * Decimal('100')).quantize(Decimal('0.01'))


def _variacao_pct(atual, anterior):
    """% de variação de `anterior` para `atual`. None se não der para calcular.

    Aceita Decimal (campos monetários) ou int (ex.: qt_total_cotistas) --
    normaliza os dois para Decimal antes de operar (int/int em Python é
    divisão real e vira float, que não opera com Decimal).
    """
    if atual is None or anterior is None or anterior == 0:
        return None
    atual, anterior = Decimal(atual), Decimal(anterior)
    return ((atual - anterior) / anterior * Decimal('100')).quantize(Decimal('0.01'))


def montar_dashboard(fundo):
    """Monta o dict de contexto completo do dashboard de um fundo."""
    hoje = date.today()

    # ── Carteira ao vivo (mesmo padrão de carteira_fundo, fundos/views.py) ──
    titulos_ativos = Titulo.objects.filter(fundo=fundo, ativo=True)
    aplicacoes_ativas = Aplicacao.objects.filter(fundo=fundo, status='ATIVA')

    saldo_dc = titulos_ativos.aggregate(s=Sum('saldo_devedor'))['s'] or Decimal('0')
    valor_liquidez = aplicacoes_ativas.aggregate(v=Sum('valor'))['v'] or Decimal('0')
    total_carteira = saldo_dc + valor_liquidez

    saldos_por_devedor = [
        {'doc': row['sacado_cpf_cnpj'], 'nome': row['sacado_nome'], 'saldo': row['s']}
        for row in titulos_ativos.order_by()
                                  .values('sacado_cpf_cnpj', 'sacado_nome')
                                  .annotate(s=Sum('saldo_devedor'))
    ]
    enquadramento = avaliar_enquadramento(
        fundo, saldo_dc, valor_liquidez, saldos_por_devedor=saldos_por_devedor
    )

    # ── Informes Mensais (série histórica) ───────────────────────────────
    informes = list(InformeMensal.objects.filter(fundo=fundo).order_by('competencia'))
    informe_atual = informes[-1] if informes else None
    informe_anterior = informes[-2] if len(informes) >= 2 else None

    # ── Bloco 1 — KPIs executivos ────────────────────────────────────────
    vencidos_agg = titulos_ativos.filter(data_vencimento__lt=hoje).aggregate(s=Sum('saldo_devedor'))
    saldo_vencido = vencidos_agg['s'] or Decimal('0')
    pdd_total = titulos_ativos.aggregate(p=Sum('valor_pdd'))['p'] or Decimal('0')

    kpis = {
        'patrimonio_liquido': informe_atual.vl_patrimonio_liquido if informe_atual else None,
        'patrimonio_liquido_var': _variacao_pct(
            informe_atual.vl_patrimonio_liquido if informe_atual else None,
            informe_anterior.vl_patrimonio_liquido if informe_anterior else None,
        ),
        'competencia_atual': informe_atual.competencia_display if informe_atual else None,
        'total_carteira': total_carteira,
        'qt_total_cotistas': informe_atual.qt_total_cotistas if informe_atual else None,
        'qt_total_cotistas_var': _variacao_pct(
            informe_atual.qt_total_cotistas if informe_atual else None,
            informe_anterior.qt_total_cotistas if informe_anterior else None,
        ),
        'rentabilidade_senior': informe_atual.rentabilidade_senior if informe_atual else None,
        'pct_inadimplencia': _pct(saldo_vencido, saldo_dc),
        'saldo_vencido': saldo_vencido,
        'pdd_total': pdd_total,
        'pdd_pct': _pct(pdd_total, saldo_dc),
    }

    # ── Bloco 3 — Série histórica (Informes Mensais, últimos 24 meses) ──
    serie_historica = [
        {
            'competencia_display': i.competencia_display,
            'pl': i.vl_patrimonio_liquido,
            'cota_senior': i.vl_cota_senior,
            'cota_subord': i.vl_cota_subord,
            'captacao': (i.vl_capt_senior or Decimal('0')) + (i.vl_capt_subord or Decimal('0')),
            'resgate': (i.vl_resg_senior or Decimal('0')) + (i.vl_resg_subord or Decimal('0')),
            'rentabilidade_senior': i.rentabilidade_senior,
        }
        for i in informes[-MESES_HISTORICO:]
    ]

    # ── Bloco 4 — Saúde da carteira: aging + fluxo futuro de vencimentos ─
    faixas_aging = [
        ('vencido', Q(data_vencimento__lt=hoje)),
        ('0-30', Q(data_vencimento__gte=hoje) & Q(data_vencimento__lt=hoje + timedelta(days=30))),
        ('31-60', Q(data_vencimento__gte=hoje + timedelta(days=30)) & Q(data_vencimento__lt=hoje + timedelta(days=60))),
        ('61-90', Q(data_vencimento__gte=hoje + timedelta(days=60)) & Q(data_vencimento__lt=hoje + timedelta(days=90))),
        ('90+', Q(data_vencimento__gte=hoje + timedelta(days=90))),
    ]
    aging = []
    for label, cond in faixas_aging:
        total = titulos_ativos.filter(cond).aggregate(s=Sum('saldo_devedor'))['s'] or Decimal('0')
        aging.append({'label': label, 'total': total, 'pct': _pct(total, saldo_dc) or Decimal('0')})

    fluxo_vencer = [
        {
            'mes': row['mes'].strftime('%m/%Y'),
            'total': row['total'],
        }
        for row in titulos_ativos.filter(data_vencimento__gte=hoje)
                                  .order_by()
                                  .annotate(mes=TruncMonth('data_vencimento'))
                                  .values('mes')
                                  .annotate(total=Sum('saldo_devedor'))
                                  .order_by('mes')[:12]
    ]

    # ── Bloco 5 — Concentração: top sacados e top cedentes ───────────────
    top_sacados = [
        {
            'nome': row['sacado_nome'],
            'doc': row['sacado_cpf_cnpj'],
            'total': row['total'],
            'pct': _pct(row['total'], saldo_dc),
        }
        for row in titulos_ativos.order_by()
                                  .values('sacado_cpf_cnpj', 'sacado_nome')
                                  .annotate(total=Sum('saldo_devedor'))
                                  .order_by('-total')[:10]
    ]
    top_cedentes = [
        {
            'nome': row['operacao_cessao__cedente_nome'],
            'doc': row['operacao_cessao__cedente_cnpj'],
            'total': row['total'],
            'pct': _pct(row['total'], saldo_dc),
        }
        for row in titulos_ativos.order_by()
                                  .values('operacao_cessao__cedente_cnpj', 'operacao_cessao__cedente_nome')
                                  .annotate(total=Sum('saldo_devedor'))
                                  .order_by('-total')[:10]
    ]

    # ── Bloco 6 — Distribuição de risco (rating AA→H) ────────────────────
    risco_map = {
        row['classificacao_risco']: row['total']
        for row in titulos_ativos.order_by()
                                  .values('classificacao_risco')
                                  .annotate(total=Sum('saldo_devedor'))
    }
    distribuicao_risco = [
        {'label': label, 'total': risco_map.get(label) or Decimal('0'), 'pct': _pct(risco_map.get(label), saldo_dc) or Decimal('0')}
        for label in ORDEM_RISCO
        if risco_map.get(label)
    ]

    return {
        'fundo': fundo,
        'enquadramento': enquadramento,
        'saldo_dc': saldo_dc,
        'valor_liquidez': valor_liquidez,
        'total_carteira': total_carteira,
        'kpis': kpis,
        'tem_informes': bool(informes),
        'serie_historica': serie_historica,
        'tem_titulos': titulos_ativos.exists(),
        'aging': aging,
        'fluxo_vencer': fluxo_vencer,
        'top_sacados': top_sacados,
        'top_cedentes': top_cedentes,
        'distribuicao_risco': distribuicao_risco,
    }
