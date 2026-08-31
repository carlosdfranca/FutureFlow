"""
fundos/services/lamina.py

Monta os dados para a Lâmina de Acompanhamento (PDF A4, 1 fundo × 1 competência)
a partir dos dados já persistidos em InformeMensal/InformeMensalCarteira. Não
gera o PDF em si -- só o dict de contexto consumido por
fundos/templates/fundos/lamina_pdf.html, renderizado com WeasyPrint na view
(fundos/views.py::lamina_informe_pdf).

Decisões de negócio já fechadas (ver plano da Fase 1+2):
- Classe de cota (sênior vs. subordinada) é escolhida automaticamente por
  fundo: usa sênior só se o fundo realmente tiver cotas sênior.
- "% da carteira" no bloco de ativos usa InformeMensalCarteira.percentual_carteira
  como já está gravado (denominador = carteira, não PL).
- Status de enquadramento tem 3 estados: Enquadrado / Desenquadrado / Não
  avaliado (quando o fundo não tem os limites cadastrados).
- Valores voltam como Decimal/None -- a formatação (BRL, %) acontece no
  template, reusando fundos/templatetags/fundos_filters.py.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal
from functools import reduce

from django.contrib.staticfiles import finders
from django.db.models import Sum

from .enquadramento import avaliar_enquadramento
from ..models import InformeMensal, SegmentoCarteira

# Quantos ativos individuais aparecem na lâmina antes de agrupar o resto
# em uma linha "Outros ativos".
LIMITE_ATIVOS_EXIBIDOS = 8

# Rótulos legíveis para os códigos de subsegmento gravados por
# fundos/services/informe_xml.py::_CARTEIRA_MAP (32 pares segmento/subsegmento
# do XML CVM). Um código não mapeado aqui cai no fallback _humanizar_codigo().
_SUBSEGMENTO_LABELS = {
    'IMOBILIARIO': 'Imobiliário',
    'GERAL': 'Geral',
    'VAREJO': 'Varejo',
    'ARRENDAMENTO': 'Arrendamento Mercantil',
    'PUBLICO': 'Público',
    'EDUCACAO': 'Educação',
    'ENTRETENIMENTO': 'Entretenimento',
    'CRED_PESSOA': 'Crédito Pessoal',
    'CONSIG': 'Consignado',
    'CORPORATIVO': 'Corporativo',
    'MONEY_MARKET': 'Money Market',
    'VEICULOS': 'Veículos',
    'IMOBIL_EMPRESARIAL': 'Imobiliário Empresarial',
    'IMOBIL_RESIDENCIAL': 'Imobiliário Residencial',
    'OUTRO': 'Outro',
    'PESSOA': 'Pessoa',
    'PRECAT': 'Precatórios',
    'CRED_TRIBUT': 'Créditos Tributários',
    'ROYALTIES': 'Royalties',
    'DEBENTURES': 'Debêntures',
    'CRI': 'CRI',
    'NOTA_COMERCIAL': 'Nota Comercial',
    'LETRA_FINANCEIRA': 'Letra Financeira',
    'COTA_FIF': 'Cota de FIF',
    'OUTRO_DICRED': 'Outro Direito Creditório',
    'PROPRIEDADE_INTELECTUAL': 'Propriedade Intelectual',
}

_PUBLICO_ALVO_LABELS = {
    'PROFISSIONAL': 'Investidores profissionais',
    'QUALIFICADO': 'Investidores qualificados',
    'VAREJO': 'Investidores em geral',
}


def _humanizar_codigo(codigo: str) -> str:
    return codigo.replace('_', ' ').strip().title()


def _descricao_segmento(seg) -> str:
    """'Setor Público — Precatórios' a partir de um SegmentoCarteira do XML CVM."""
    rotulo_segmento = SegmentoCarteira(seg.segmento).label
    if not seg.subsegmento:
        return rotulo_segmento
    rotulo_sub = _SUBSEGMENTO_LABELS.get(seg.subsegmento, _humanizar_codigo(seg.subsegmento))
    return f"{rotulo_segmento} — {rotulo_sub}"


def _serie_ate(fundo, competencia):
    """Todos os InformeMensal do fundo até (e incluindo) `competencia`, mais
    antigo primeiro. Limitado à competência da lâmina -- uma lâmina de uma
    competência passada não deve enxergar informes futuros."""
    return list(
        InformeMensal.objects.filter(fundo=fundo, competencia__lte=competencia)
        .order_by('competencia')
    )


def _classe_rentabilidade(informe) -> tuple[str, str]:
    """Escolha automática (Decisão D2): sênior só se o fundo realmente tiver
    cotas sênior; a maioria dos FIDCs de classe única usa subordinada."""
    if informe.qt_cotas_senior and informe.qt_cotas_senior > 0:
        return 'rentabilidade_senior', 'Cota Sênior'
    return 'rentabilidade_subord', 'Cota Única'


def _grade_rentabilidade(serie, campo, ano_ant, ano_atual):
    """Pivota a série em duas listas de 12 posições (Jan..Dez), uma por ano.
    Mês sem informe fica None (o template trata como '-'), nunca 0."""
    grade = {ano_ant: [None] * 12, ano_atual: [None] * 12}
    for informe in serie:
        ano = informe.competencia.year
        if ano in grade:
            valor = getattr(informe, campo)
            if valor is not None:
                grade[ano][informe.competencia.month - 1] = valor
    return grade[ano_ant], grade[ano_atual]


@dataclass
class Estatisticas:
    meses_pos: int
    meses_neg: int
    maior_ret: Decimal | None
    menor_ret: Decimal | None
    ret_12m: Decimal | None
    ret_ini: Decimal | None
    meses_disponiveis: int
    meses_esperados: int

    @property
    def cobertura_completa(self) -> bool:
        return self.meses_disponiveis >= self.meses_esperados


def _composto(retornos_pct) -> Decimal | None:
    """Produto composto (1+r)*(1+r)*...-1 a partir de uma lista de retornos
    já em escala percentual (ex.: -0.43 = -0,43%), retorna também em %."""
    if not retornos_pct:
        return None
    fator = reduce(lambda acc, r: acc * (1 + r / Decimal('100')), retornos_pct, Decimal('1'))
    return (fator - 1) * Decimal('100')


def _estatisticas(serie, campo, fundo, competencia_lamina) -> Estatisticas:
    retornos = [getattr(i, campo) for i in serie if getattr(i, campo) is not None]

    meses_esperados = (
        (competencia_lamina.year - fundo.data_constituicao.year) * 12
        + (competencia_lamina.month - fundo.data_constituicao.month)
        + 1
    )

    return Estatisticas(
        meses_pos=sum(1 for r in retornos if r > 0),
        meses_neg=sum(1 for r in retornos if r < 0),
        maior_ret=max(retornos) if retornos else None,
        menor_ret=min(retornos) if retornos else None,
        ret_12m=_composto(retornos[-12:]),
        ret_ini=_composto(retornos),
        meses_disponiveis=len(serie),
        meses_esperados=max(meses_esperados, len(serie)),
    )


def _carteira_ativos(informe):
    """Top N segmentos por valor (já vem ordenado por -valor, Meta.ordering
    de InformeMensalCarteira), resto agrupado em 'Outros ativos'."""
    segmentos = list(informe.carteira.all())
    principais = segmentos[:LIMITE_ATIVOS_EXIBIDOS]
    resto = segmentos[LIMITE_ATIVOS_EXIBIDOS:]

    ativos = [
        {'descricao': _descricao_segmento(s), 'valor': s.valor, 'percentual': s.percentual_carteira}
        for s in principais
    ]
    if resto:
        ativos.append({
            'descricao': 'Outros ativos',
            'valor': sum((s.valor for s in resto), Decimal('0')),
            'percentual': sum((s.percentual_carteira or Decimal('0') for s in resto), Decimal('0')),
        })
    return ativos


def _status_enquadramento(fundo):
    """Reusa fundos/services/enquadramento.py -- mesma função usada em
    carteira_fundo e no dashboard. Acrescenta o 3º estado (A5.1)."""
    from operacoes.models import Titulo, Aplicacao

    titulos_ativos = Titulo.objects.filter(fundo=fundo, ativo=True)
    aplicacoes_ativas = Aplicacao.objects.filter(fundo=fundo, status='ATIVA')

    saldo_dc = titulos_ativos.aggregate(s=Sum('saldo_devedor'))['s'] or Decimal('0')
    valor_liquidez = aplicacoes_ativas.aggregate(v=Sum('valor'))['v'] or Decimal('0')

    saldos_por_devedor = [
        {'doc': row['sacado_cpf_cnpj'], 'nome': row['sacado_nome'], 'saldo': row['s']}
        for row in titulos_ativos.order_by()
        .values('sacado_cpf_cnpj', 'sacado_nome')
        .annotate(s=Sum('saldo_devedor'))
    ]

    resultado = avaliar_enquadramento(fundo, saldo_dc, valor_liquidez, saldos_por_devedor=saldos_por_devedor)

    if not resultado.avaliavel:
        rotulo = 'Não avaliado'
    elif resultado.desenquadrado:
        rotulo = 'Desenquadrado'
    else:
        rotulo = 'Enquadrado'

    return resultado, rotulo


def _logo_cinnamon_base64() -> str | None:
    """Lê static/img/logo-light.png do disco (via staticfiles finders) e
    devolve como data: URI -- o PDF não depende de nenhuma requisição HTTP
    durante a geração. Usa a versão "light" (feita para fundo claro) porque
    a lâmina é sempre fundo branco -- a "dark" fica ilegível aqui."""
    caminho = finders.find('img/logo-light.png')
    if not caminho:
        return None
    with open(caminho, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


def montar_dados_lamina(fundo, informe) -> dict:
    """Monta o dict de contexto completo para fundos/lamina_pdf.html a partir
    de um Fundo e um InformeMensal específico (a competência da lâmina)."""
    competencia = informe.competencia
    ano_atual = competencia.year
    ano_ant = ano_atual - 1

    serie = _serie_ate(fundo, competencia)
    campo_rent, rotulo_classe = _classe_rentabilidade(informe)

    grade_ant, grade_atual = _grade_rentabilidade(serie, campo_rent, ano_ant, ano_atual)
    estatisticas = _estatisticas(serie, campo_rent, fundo, competencia)
    ativos = _carteira_ativos(informe)
    enquadramento, status_enq = _status_enquadramento(fundo)

    num_ativos = informe.carteira.count()

    return {
        'fundo': fundo,
        'informe': informe,
        'competencia_display': informe.competencia_display,
        'ano_ant': ano_ant,
        'ano_atual': ano_atual,
        'grade_ant': grade_ant,
        'grade_atual': grade_atual,
        'rotulo_classe': rotulo_classe,
        'estatisticas': estatisticas,
        'ativos': ativos,
        'enquadramento': enquadramento,
        'status_enquadramento': status_enq,
        'num_ativos': num_ativos,
        'publico_alvo': _PUBLICO_ALVO_LABELS.get(fundo.classificacao_investidor, '—'),
        'tese_investimento': fundo.politica_investimento if isinstance(fundo.politica_investimento, str) else None,
        'logo_cinnamon': _logo_cinnamon_base64(),
    }
