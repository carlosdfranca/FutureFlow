"""
Service layer for Aplicação (fund investment in assets) operations.
Handles business logic for liquidating aplicações.
"""
from django.db import transaction


@transaction.atomic
def liquidar_aplicacao(aplicacao, data_liquidacao, valor_resgate, usuario):
    """
    Marca uma aplicação como liquidada, registrando data e valor de resgate.

    Args:
        aplicacao: Instância de Aplicacao
        data_liquidacao: date
        valor_resgate: Decimal
        usuario: User responsável pela liquidação

    Returns:
        Aplicacao atualizada

    Raises:
        ValueError: se a aplicação já estiver liquidada
    """
    if aplicacao.status == 'LIQUIDADA':
        raise ValueError('Aplicação já está liquidada.')

    aplicacao.status = 'LIQUIDADA'
    aplicacao.data_liquidacao = data_liquidacao
    aplicacao.valor_resgate = valor_resgate
    aplicacao.liquidado_por = usuario
    aplicacao.save(update_fields=[
        'status', 'data_liquidacao', 'valor_resgate', 'liquidado_por', 'atualizado_em'
    ])

    return aplicacao
