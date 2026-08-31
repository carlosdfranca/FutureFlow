"""
Service layer for Cessão operations.
Handles business logic for creating cessões, títulos, and events.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from operacoes.models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo


def calcular_valor_presente(valor_nominal, taxa_desconto_pct) -> Decimal:
    """
    VL_PRESENTE = ARRED(VL_NOMINAL - VL_NOMINAL * TAXA_DESCONTO; 2)

    `taxa_desconto_pct` é percentual (0.60 = 0,6%). Espelha a função
    `CalcularDesconto` do legado (`docs/legado_vba/Módulo3.bas:5-26`), que
    aplicava um deságio fixo de 0,6%; aqui a taxa é parametrizável por
    operação em vez de fixa em código.

    Usa ROUND_HALF_UP (não o `round()` nativo, que é bankers' rounding) para
    reproduzir o comportamento do ARRED() do Excel.
    """
    vn = Decimal(str(valor_nominal or 0))
    taxa = Decimal(str(taxa_desconto_pct or 0)) / Decimal('100')
    return (vn - vn * taxa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


@transaction.atomic
def processar_cessao(
    fundo,
    cedente_dados: dict,
    titulos_dados: list[dict],
    operacao_dados: dict,
    usuario
) -> OperacaoCessao:
    """
    Cria uma operação de cessão completa:
    1. Cria OperacaoCessao
    2. Cria Titulo para cada título
    3. Cria EventoTitulo (AQUISICAO) para cada título
    
    Args:
        fundo: Instância do Fundo
        cedente_dados: dict com cnpj, nome, endereco
        titulos_dados: list de dicts com dados dos títulos
        operacao_dados: dict com numero_contrato, data_contrato, data_aquisicao,
            taxa_desconto, observacoes
        usuario: User que está criando a operação

    Returns:
        OperacaoCessao criada
    """
    taxa_desconto = Decimal(str(operacao_dados.get('taxa_desconto') or 0))

    # O valor presente (valor_aquisicao) é sempre recalculado aqui a partir
    # do valor_nominal e da taxa_desconto da operação — nunca confiamos no
    # valor_aquisicao vindo de titulos_dados (o campo é somente-leitura na
    # tela, mas o servidor é a fonte de verdade).
    valor_total_nominal = sum(Decimal(str(t['valor_nominal'])) for t in titulos_dados)
    valor_total_aquisicao = sum(
        calcular_valor_presente(t['valor_nominal'], taxa_desconto) for t in titulos_dados
    )

    # Criar operação
    operacao = OperacaoCessao.objects.create(
        fundo=fundo,
        cedente_cnpj=cedente_dados['cnpj'],
        cedente_nome=cedente_dados['nome'],
        cedente_endereco=cedente_dados.get('endereco', ''),
        numero_contrato=operacao_dados['numero_contrato'],
        data_contrato=operacao_dados['data_contrato'],
        data_aquisicao=operacao_dados['data_aquisicao'],
        taxa_desconto=taxa_desconto,
        valor_total_nominal=valor_total_nominal,
        valor_total_aquisicao=valor_total_aquisicao,
        status='CONFIRMADA',
        observacoes=operacao_dados.get('observacoes', ''),
        criado_por=usuario
    )

    # Criar títulos e eventos
    for titulo_data in titulos_dados:
        valor_presente = calcular_valor_presente(titulo_data['valor_nominal'], taxa_desconto)

        # Criar Titulo
        titulo = Titulo.objects.create(
            operacao_cessao=operacao,
            fundo=fundo,
            numero_titulo=titulo_data['numero_titulo'],
            sacado_nome=titulo_data['sacado_nome'],
            sacado_cpf_cnpj=titulo_data['sacado_cpf_cnpj'],
            sacado_endereco=titulo_data.get('sacado_endereco', ''),
            sacado_cep=titulo_data.get('sacado_cep', ''),
            valor_nominal=titulo_data['valor_nominal'],
            valor_aquisicao=valor_presente,
            data_emissao=titulo_data.get('data_emissao', operacao.data_aquisicao),
            data_vencimento=titulo_data['data_vencimento'],
            saldo_devedor=titulo_data['valor_nominal'],
            ativo=True,
            classificacao_risco='AA',  # Inicialmente AA
            chave_nfe=titulo_data.get('chave_nfe', '')
        )

        # Evento de AQUISICAO
        EventoTitulo.objects.create(
            titulo=titulo,
            tipo_evento=TipoEventoTitulo.AQUISICAO,
            data_evento=operacao.data_aquisicao,
            valor_evento=titulo.valor_aquisicao,
            descricao=f'Aquisição via operação {operacao.numero_contrato}',
            usuario_responsavel=usuario
        )

    return operacao


@transaction.atomic
def criar_evento_titulo(
    titulo,
    tipo_evento: int,
    data_evento,
    usuario,
    valor_evento=None,
    descricao='',
    documento_referencia=''
) -> EventoTitulo:
    """
    Cria um evento operacional e atualiza o estado do título.
    
    Args:
        titulo: Instância do Titulo
        tipo_evento: TipoEventoTitulo (int)
        data_evento: date
        usuario: User responsável
        valor_evento: Decimal (opcional)
        descricao: str
        documento_referencia: str
        
    Returns:
        EventoTitulo criado
    """
    # Criar evento
    evento = EventoTitulo.objects.create(
        titulo=titulo,
        tipo_evento=tipo_evento,
        data_evento=data_evento,
        valor_evento=valor_evento,
        descricao=descricao,
        documento_referencia=documento_referencia,
        usuario_responsavel=usuario
    )
    
    # Atualizar estado do título baseado no tipo de evento
    if tipo_evento == TipoEventoTitulo.LIQUIDACAO_PARCIAL:
        if valor_evento:
            titulo.saldo_devedor -= Decimal(str(valor_evento))
            titulo.save(update_fields=['saldo_devedor', 'atualizado_em'])
    
    elif tipo_evento == TipoEventoTitulo.LIQUIDACAO_TOTAL:
        titulo.saldo_devedor = Decimal('0')
        titulo.ativo = False
        titulo.save(update_fields=['saldo_devedor', 'ativo', 'atualizado_em'])
    
    elif tipo_evento == TipoEventoTitulo.BAIXA:
        titulo.ativo = False
        titulo.save(update_fields=['ativo', 'atualizado_em'])
    
    elif tipo_evento == TipoEventoTitulo.REATIVACAO:
        titulo.ativo = True
        titulo.save(update_fields=['ativo', 'atualizado_em'])
    
    elif tipo_evento == TipoEventoTitulo.AJUSTE_VALOR:
        if valor_evento:
            # Ajuste pode ser positivo ou negativo
            titulo.valor_nominal = Decimal(str(valor_evento))
            titulo.saldo_devedor = Decimal(str(valor_evento))
            titulo.save(update_fields=['valor_nominal', 'saldo_devedor', 'atualizado_em'])
    
    elif tipo_evento == TipoEventoTitulo.PRORROGACAO:
        # Data de vencimento deve ser atualizada externamente
        pass
    
    return evento
