"""
Service layer for Cessão operations.
Handles business logic for creating cessões, títulos, and events.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from operacoes.models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo


# Taxa de IOF padrão sugerida na tela de import (percentual: 0.6 = 0,6%).
# Vive aqui, e não espalhada em forms/views/template, porque foi exatamente um
# literal solto que virou o `0.994` hardcoded da macro legada.
TAXA_IOF_PADRAO = Decimal('0.6')


def _aplicar_taxa(valor, taxa_pct) -> Decimal:
    """ARRED(valor - valor * taxa; 2), com taxa em percentual (0.6 = 0,6%).

    ROUND_HALF_UP (e não o `round()` nativo, que é bankers' rounding) para
    reproduzir o ARRED()/ROUND() do Excel.
    """
    v = Decimal(str(valor or 0))
    taxa = Decimal(str(taxa_pct or 0)) / Decimal('100')
    return (v - v * taxa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_valor_nominal(valor_face, taxa_iof_pct) -> Decimal:
    """Primeiro passo da cascata: desconta o IOF do valor bruto da duplicata.

    `valor_face` é o `cobr/dup/vDup` do XML (valor bruto). O resultado é o que
    o legado chama de "Valor da Duplicata" (aba MENU, coluna J) e é o que vai
    para `Titulo.valor_nominal` e para o CNAB pos. 127-139.

    Espelha `CalcularDesconto` (`docs/legado_vba/Módulo3.bas:5-26`), que crava
    `Round(valor * 0.994, 2)` — 0,6% de IOF. Aqui a taxa é parametrizável por
    operação (`OperacaoCessao.taxa_iof`) em vez de fixa em código.

    Divergência conhecida e aceita: o `Round()` do VBA é half-even, enquanto
    este usa half-up para manter um único modo de arredondamento no sistema.
    Com IOF de 0,6% os dois só divergem (em R$ 0,01) quando o valor bruto
    termina em X2,50 — aí `valor - valor*0,006` cai em meio centavo exato com
    o centavo anterior par, e o half-even desce enquanto o half-up sobe.
    Ex.: 12.002,50 → 11.930,485 → 11.930,49 aqui, 11.930,48 no VBA. É 1 em
    1.000 valores possíveis; valores terminando em X7,50 não divergem.
    """
    return _aplicar_taxa(valor_face, taxa_iof_pct)


def calcular_valor_presente(valor_nominal, taxa_desconto_pct) -> Decimal:
    """Segundo passo da cascata: desconta o deságio do valor nominal.

    VL_PRESENTE = ARRED(VL_NOMINAL - VL_NOMINAL * TAXA_DESCONTO; 2)

    `valor_nominal` já vem líquido de IOF (saída de `calcular_valor_nominal`);
    `taxa_desconto_pct` é percentual (2.88 = 2,88%). Espelha a fórmula da
    coluna I da aba BASE da planilha legada: `=ROUND((F2-(F2*2,88%));2)`.

    O arredondamento intermediário entre os dois passos é obrigatório: aplicar
    as duas taxas numa expressão só erra centavos (ex.: 4.567,20 → 4.539,80 →
    4.409,05; sem o passo do meio dá 4.409,04).
    """
    return _aplicar_taxa(valor_nominal, taxa_desconto_pct)


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
        titulos_dados: list de dicts com dados dos títulos. O valor vem na
            chave `valor_face` (bruto, `cobr/dup/vDup` do XML) — nunca em
            `valor_nominal`, que aqui é derivado.
        operacao_dados: dict com numero_contrato, data_contrato, data_aquisicao,
            taxa_iof, taxa_desconto, observacoes
        usuario: User que está criando a operação

    Returns:
        OperacaoCessao criada
    """
    # Acesso duro nas duas taxas de propósito: um `.get(...) or 0` silencioso
    # em cima de um caller que esqueceu de passar a taxa é exatamente o bug
    # que essa cascata veio consertar. Melhor estourar KeyError.
    taxa_iof = Decimal(str(operacao_dados['taxa_iof'] or 0))
    taxa_desconto = Decimal(str(operacao_dados['taxa_desconto'] or 0))

    # Cascata de dois passos, calculada UMA vez por título. Os totais da
    # operação saem desta lista, então o cabeçalho sempre fecha com a soma das
    # próprias linhas. Nada do que vem em titulos_dados além do `valor_face` é
    # confiado: `valor_nominal` e `valor_aquisicao` são derivados aqui, no
    # servidor (os campos são somente-leitura na tela, mas quem manda é isto).
    valores = []
    for t in titulos_dados:
        nominal = calcular_valor_nominal(t['valor_face'], taxa_iof)
        valores.append((nominal, calcular_valor_presente(nominal, taxa_desconto)))

    valor_total_nominal = sum((n for n, _ in valores), Decimal('0'))
    valor_total_aquisicao = sum((p for _, p in valores), Decimal('0'))

    # Criar operação
    operacao = OperacaoCessao.objects.create(
        fundo=fundo,
        cedente_cnpj=cedente_dados['cnpj'],
        cedente_nome=cedente_dados['nome'],
        cedente_endereco=cedente_dados.get('endereco', ''),
        numero_contrato=operacao_dados['numero_contrato'],
        data_contrato=operacao_dados['data_contrato'],
        data_aquisicao=operacao_dados['data_aquisicao'],
        taxa_iof=taxa_iof,
        taxa_desconto=taxa_desconto,
        valor_total_nominal=valor_total_nominal,
        valor_total_aquisicao=valor_total_aquisicao,
        status='CONFIRMADA',
        observacoes=operacao_dados.get('observacoes', ''),
        criado_por=usuario
    )

    # Criar títulos e eventos
    for titulo_data, (valor_nominal, valor_presente) in zip(titulos_dados, valores):
        # Criar Titulo
        titulo = Titulo.objects.create(
            operacao_cessao=operacao,
            fundo=fundo,
            numero_titulo=titulo_data['numero_titulo'],
            sacado_nome=titulo_data['sacado_nome'],
            sacado_cpf_cnpj=titulo_data['sacado_cpf_cnpj'],
            sacado_endereco=titulo_data.get('sacado_endereco', ''),
            sacado_cep=titulo_data.get('sacado_cep', ''),
            valor_nominal=valor_nominal,
            valor_aquisicao=valor_presente,
            data_emissao=titulo_data.get('data_emissao', operacao.data_aquisicao),
            data_vencimento=titulo_data['data_vencimento'],
            saldo_devedor=valor_nominal,
            ativo=True,
            classificacao_risco='AA',  # Inicialmente AA
            chave_nfe=titulo_data.get('chave_nfe', ''),
            coobrigacao=fundo.coobrigacao_cnab_padrao,
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
