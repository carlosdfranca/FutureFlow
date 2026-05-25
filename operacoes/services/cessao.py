"""
Service layer for Cessão operations.
Handles business logic for creating cessões, títulos, and events.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from operacoes.models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo


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
        operacao_dados: dict com numero_contrato, data_contrato, data_aquisicao, observacoes
        usuario: User que está criando a operação
        
    Returns:
        OperacaoCessao criada
    """
    # Calcular valores totais
    valor_total_nominal = sum(Decimal(str(t['valor_nominal'])) for t in titulos_dados)
    valor_total_aquisicao = sum(Decimal(str(t['valor_aquisicao'])) for t in titulos_dados)
    
    # Criar operação
    operacao = OperacaoCessao.objects.create(
        fundo=fundo,
        cedente_cnpj=cedente_dados['cnpj'],
        cedente_nome=cedente_dados['nome'],
        cedente_endereco=cedente_dados.get('endereco', ''),
        numero_contrato=operacao_dados['numero_contrato'],
        data_contrato=operacao_dados['data_contrato'],
        data_aquisicao=operacao_dados['data_aquisicao'],
        valor_total_nominal=valor_total_nominal,
        valor_total_aquisicao=valor_total_aquisicao,
        status='CONFIRMADA',
        observacoes=operacao_dados.get('observacoes', ''),
        criado_por=usuario
    )
    
    # Criar títulos e eventos
    for titulo_data in titulos_dados:
        # Criar Titulo
        titulo = Titulo.objects.create(
            operacao_cessao=operacao,
            fundo=fundo,
            numero_titulo=titulo_data['numero_titulo'],
            sacado_nome=titulo_data['sacado_nome'],
            sacado_cpf_cnpj=titulo_data['sacado_cpf_cnpj'],
            valor_nominal=titulo_data['valor_nominal'],
            valor_aquisicao=titulo_data['valor_aquisicao'],
            data_emissao=titulo_data.get('data_emissao', operacao.data_aquisicao),
            data_vencimento=titulo_data['data_vencimento'],
            saldo_devedor=titulo_data['valor_nominal'],
            ativo=True,
            classificacao_risco='AA'  # Inicialmente AA
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


def calcular_totais_operacao(titulos_dados: list[dict]) -> dict:
    """
    Calcula valores totais de uma operação de cessão.
    
    Args:
        titulos_dados: list de dicts com valor_nominal e valor_aquisicao
        
    Returns:
        dict com valor_total_nominal e valor_total_aquisicao
    """
    valor_total_nominal = sum(Decimal(str(t['valor_nominal'])) for t in titulos_dados)
    valor_total_aquisicao = sum(Decimal(str(t['valor_aquisicao'])) for t in titulos_dados)
    
    return {
        'valor_total_nominal': valor_total_nominal,
        'valor_total_aquisicao': valor_total_aquisicao,
        'quantidade_titulos': len(titulos_dados)
    }
