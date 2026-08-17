"""
Processamento de Aplicações e Resgates
"""

from datetime import datetime, date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from fundos.models import (
    MovimentacaoCota,
    Fundo,
    Cotista,
    CotaHistorico,
    StatusMovimentacao
)
from .tributos import calcular_impostos_resgate


HORARIO_CORTE_PADRAO = time(14, 0)


def determinar_data_cotizacao(
    data_solicitacao: datetime,
    tipo_cotizacao: str,
    horario_corte: time = HORARIO_CORTE_PADRAO
) -> date:
    """
    Determina data de cotização baseada em horário de corte.
    
    Args:
        data_solicitacao: Data/hora da solicitação
        tipo_cotizacao: 'D+0' ou 'D+1'
        horario_corte: Horário limite para cotização no mesmo dia
        
    Returns:
        Data de cotização
    """
    hora_solicitacao = data_solicitacao.time()
    
    if tipo_cotizacao == 'D+0':
        if hora_solicitacao <= horario_corte:
            data_cotizacao = data_solicitacao.date()
        else:
            data_cotizacao = data_solicitacao.date() + timedelta(days=1)
    else:  # D+1
        data_cotizacao = data_solicitacao.date() + timedelta(days=1)
    
    # Pula fim de semana (simplificado - não considera feriados)
    while data_cotizacao.weekday() >= 5:
        data_cotizacao += timedelta(days=1)
    
    return data_cotizacao


@transaction.atomic
def processar_aplicacao(
    fundo_id: str,
    cotista_id: str,
    valor_financeiro: Decimal,
    data_solicitacao: datetime = None
) -> MovimentacaoCota:
    """
    Processa solicitação de aplicação.
    
    Fluxo:
    1. Valida fundo e cotista
    2. Determina data de cotização
    3. Determina data de liquidação
    4. Cria movimentação com status AGUARDANDO_PAGAMENTO
    
    Args:
        fundo_id: UUID do fundo
        cotista_id: UUID do cotista
        valor_financeiro: Valor a aplicar
        data_solicitacao: Data/hora da solicitação (default: agora)
        
    Returns:
        MovimentacaoCota criada
    """
    if data_solicitacao is None:
        data_solicitacao = timezone.now()
    
    try:
        fundo = Fundo.objects.get(id=fundo_id, ativo=True)
    except Fundo.DoesNotExist:
        raise ValueError(f"Fundo {fundo_id} não encontrado ou inativo")
    
    try:
        cotista = Cotista.objects.get(id=cotista_id, ativo=True)
    except Cotista.DoesNotExist:
        raise ValueError(f"Cotista {cotista_id} não encontrado ou inativo")
    
    if valor_financeiro <= 0:
        raise ValueError("Valor financeiro deve ser positivo")
    
    # Determina data de cotização
    data_cotizacao = determinar_data_cotizacao(
        data_solicitacao,
        fundo.tipo_cotizacao,
        fundo.horario_corte
    )
    
    # Determina data de liquidação
    data_liquidacao = data_cotizacao + timedelta(days=fundo.prazo_liquidacao or 0)
    while data_liquidacao.weekday() >= 5:
        data_liquidacao += timedelta(days=1)
    
    # Cria movimentação
    movimentacao = MovimentacaoCota.objects.create(
        tipo_movimentacao='APLICACAO',
        fundo=fundo,
        cotista=cotista,
        valor_financeiro=valor_financeiro,
        data_solicitacao=data_solicitacao,
        data_cotizacao=data_cotizacao,
        data_liquidacao=data_liquidacao,
        status=StatusMovimentacao.AGUARDANDO_PAGAMENTO
    )
    
    return movimentacao


@transaction.atomic
def processar_resgate(
    fundo_id: str,
    cotista_id: str,
    quantidade_cotas: Decimal,
    data_solicitacao: datetime = None
) -> MovimentacaoCota:
    """
    Processa solicitação de resgate.
    
    Fluxo:
    1. Valida fundo e cotista
    2. Determina data de cotização
    3. Determina data de liquidação (geralmente D+3 ou D+4)
    4. Cria movimentação com status SOLICITADO
    5. Cálculo de IR/IOF será feito após cota conhecida
    
    Args:
        fundo_id: UUID do fundo
        cotista_id: UUID do cotista
        quantidade_cotas: Quantidade de cotas a resgatar
        data_solicitacao: Data/hora da solicitação (default: agora)
        
    Returns:
        MovimentacaoCota criada
    """
    if data_solicitacao is None:
        data_solicitacao = timezone.now()
    
    try:
        fundo = Fundo.objects.get(id=fundo_id, ativo=True)
    except Fundo.DoesNotExist:
        raise ValueError(f"Fundo {fundo_id} não encontrado ou inativo")
    
    try:
        cotista = Cotista.objects.get(id=cotista_id, ativo=True)
    except Cotista.DoesNotExist:
        raise ValueError(f"Cotista {cotista_id} não encontrado ou inativo")
    
    if quantidade_cotas <= 0:
        raise ValueError("Quantidade de cotas deve ser positiva")
    
    # TODO: Validar se cotista possui cotas suficientes
    
    # Determina data de cotização
    data_cotizacao = determinar_data_cotizacao(
        data_solicitacao,
        fundo.tipo_cotizacao,
        fundo.horario_corte
    )
    
    # Data de liquidação para resgates (geralmente D+3)
    data_liquidacao = data_cotizacao + timedelta(days=3)
    while data_liquidacao.weekday() >= 5:
        data_liquidacao += timedelta(days=1)
    
    # Cria movimentação
    movimentacao = MovimentacaoCota.objects.create(
        tipo_movimentacao='RESGATE',
        fundo=fundo,
        cotista=cotista,
        quantidade_cotas=quantidade_cotas,
        data_solicitacao=data_solicitacao,
        data_cotizacao=data_cotizacao,
        data_liquidacao=data_liquidacao,
        status=StatusMovimentacao.SOLICITADO
    )
    
    return movimentacao


@transaction.atomic  # ⭐ DECORATOR ADICIONADO
def efetivar_movimentacao(movimentacao_id: str) -> MovimentacaoCota:
    """
    Efetiva movimentação após cota calculada.
    
    Para APLICACAO:
    - Calcula quantidade de cotas = Valor / Cota
    
    Para RESGATE:
    - Calcula valor bruto = Qtd cotas * Cota
    - Calcula IR e IOF
    - Calcula valor líquido
    
    Args:
        movimentacao_id: UUID da movimentação
        
    Returns:
        MovimentacaoCota atualizada
    """
    try:
        movimentacao = MovimentacaoCota.objects.select_for_update().get(id=movimentacao_id)
    except MovimentacaoCota.DoesNotExist:
        raise ValueError(f"Movimentação {movimentacao_id} não encontrada")
    
    # Busca cota do dia
    try:
        cota_hist = CotaHistorico.objects.get(
            fundo=movimentacao.fundo,
            data_referencia=movimentacao.data_cotizacao
        )
    except CotaHistorico.DoesNotExist:
        raise ValueError(f"Cota não calculada para {movimentacao.data_cotizacao}")
    
    movimentacao.valor_cota = cota_hist.valor_cota
    
    if movimentacao.tipo_movimentacao == 'APLICACAO':
        # Qtd cotas = Valor / Cota
        movimentacao.quantidade_cotas = (
            movimentacao.valor_financeiro / movimentacao.valor_cota
        ).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
        
        movimentacao.valor_liquido = movimentacao.valor_financeiro
        movimentacao.status = StatusMovimentacao.CONFIRMADO
    
    elif movimentacao.tipo_movimentacao == 'RESGATE':
        # Valor bruto = Qtd cotas * Cota
        valor_bruto = movimentacao.quantidade_cotas * movimentacao.valor_cota
        movimentacao.valor_financeiro = valor_bruto
        
        # Calcula IR e IOF (simplificado - assumindo data aplicação)
        # Em produção, buscar custo médio real do cotista
        data_aplicacao_estimada = movimentacao.data_cotizacao - timedelta(days=800)
        valor_aplicacao_estimado = valor_bruto * Decimal('0.8')  # 20% de rendimento
        
        impostos = calcular_impostos_resgate(
            valor_bruto,
            valor_aplicacao_estimado,
            data_aplicacao_estimada,
            movimentacao.data_cotizacao
        )
        
        movimentacao.ir_retido = impostos['ir_retido']
        movimentacao.iof_retido = impostos['iof_retido']
        movimentacao.valor_liquido = impostos['valor_liquido']
        movimentacao.status = StatusMovimentacao.CONFIRMADO
    
    movimentacao.save()

    return movimentacao