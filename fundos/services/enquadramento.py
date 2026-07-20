"""
Serviço de Enquadramento de Carteira

Avalia se um fundo está desenquadrado com base nos limites máximos de
composição da carteira definidos no cadastro do fundo:
- limite_direitos_creditorios: % máximo em Direitos Creditórios (Cessões)
- limite_liquidez: % máximo em Liquidez (Aplicações)

Regra: total_carteira = saldo_dc (Direitos Creditórios ativos) + valor_liquidez
(Aplicações ativas). O fundo está desenquadrado se o percentual real de
qualquer uma das duas categorias ultrapassar o respectivo limite cadastrado.

Só é possível avaliar quando o fundo tem os dois limites preenchidos e a
carteira tem saldo (total > 0); caso contrário, não há sinalização.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db.models import Sum


@dataclass
class ResultadoEnquadramento:
    avaliavel: bool               # tem os 2 limites cadastrados E total > 0
    desenquadrado: bool
    total: Decimal
    pct_dc: Decimal                # % real em Direitos Creditórios
    pct_liquidez: Decimal          # % real em Liquidez
    limite_dc: Optional[int]
    limite_liquidez: Optional[int]
    dc_excede: bool                # pct_dc > limite_dc
    liquidez_excede: bool          # pct_liquidez > limite_liquidez


def _pct(parte: Decimal, total: Decimal) -> Decimal:
    if not total:
        return Decimal('0.00')
    return (parte / total * Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def avaliar_enquadramento(fundo, saldo_dc: Decimal, valor_liquidez: Decimal) -> ResultadoEnquadramento:
    """
    Avalia o enquadramento de um fundo a partir dos saldos reais de sua carteira.

    Args:
        fundo: instância de Fundo (usa limite_direitos_creditorios e limite_liquidez)
        saldo_dc: total ativo em Direitos Creditórios (Cessões), em R$
        valor_liquidez: total ativo em Liquidez (Aplicações), em R$

    Returns:
        ResultadoEnquadramento
    """
    saldo_dc = saldo_dc or Decimal('0')
    valor_liquidez = valor_liquidez or Decimal('0')
    total = saldo_dc + valor_liquidez

    limite_dc = fundo.limite_direitos_creditorios
    limite_liquidez = fundo.limite_liquidez

    pct_dc = _pct(saldo_dc, total)
    pct_liquidez = _pct(valor_liquidez, total)

    avaliavel = limite_dc is not None and limite_liquidez is not None and total > 0

    dc_excede = avaliavel and pct_dc > limite_dc
    liquidez_excede = avaliavel and pct_liquidez > limite_liquidez

    return ResultadoEnquadramento(
        avaliavel=avaliavel,
        desenquadrado=bool(avaliavel and (dc_excede or liquidez_excede)),
        total=total,
        pct_dc=pct_dc,
        pct_liquidez=pct_liquidez,
        limite_dc=limite_dc,
        limite_liquidez=limite_liquidez,
        dc_excede=dc_excede,
        liquidez_excede=liquidez_excede,
    )


def anexar_enquadramento(fundos):
    """
    Calcula e anexa `.enquadramento` a cada Fundo da lista, em lote (sem N+1):
    agrega Direitos Creditórios (Titulo.saldo_devedor, ativo=True) e Liquidez
    (Aplicacao.valor, status='ATIVA') por fundo em duas queries agrupadas.

    Args:
        fundos: lista de instâncias de Fundo

    Returns:
        A mesma lista, com `.enquadramento` (ResultadoEnquadramento) em cada item.
    """
    from operacoes.models import Titulo, Aplicacao  # import local evita ciclo no topo do módulo

    ids = [f.id for f in fundos]
    dc_map = {
        row['fundo']: row['s']
        for row in Titulo.objects.filter(fundo_id__in=ids, ativo=True)
                                  .order_by().values('fundo').annotate(s=Sum('saldo_devedor'))
    }
    liq_map = {
        row['fundo']: row['v']
        for row in Aplicacao.objects.filter(fundo_id__in=ids, status='ATIVA')
                                     .order_by().values('fundo').annotate(v=Sum('valor'))
    }
    for f in fundos:
        f.enquadramento = avaliar_enquadramento(
            f, dc_map.get(f.id) or Decimal('0'), liq_map.get(f.id) or Decimal('0')
        )
    return fundos
