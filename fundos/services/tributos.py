"""
Serviço de Cálculos Tributários
Referências: 
- Resolução CVM 175/2022 (PDD)
- Lei 11.033/2004 (Tabela regressiva IR)
- Decreto 6.306/2007 (IOF)
"""

from decimal import Decimal, ROUND_HALF_UP


def calcular_pdd(dias_atraso: int, valor_nominal: Decimal) -> Decimal:
    """
    Calcula Provisão para Devedores Duvidosos conforme Resolução CVM 175/2022 - Anexo II.
    
    Faixas de provisão:
    - 0-30 dias: 0%
    - 31-60 dias: 1%
    - 61-90 dias: 3%
    - 91-120 dias: 10%
    - 121-150 dias: 30%
    - 151-180 dias: 50%
    - 181-360 dias: 75%
    - > 360 dias: 100%
    
    Args:
        dias_atraso: Número de dias em atraso
        valor_nominal: Valor nominal do título
        
    Returns:
        Valor da provisão (PDD)
    """
    if dias_atraso < 0:
        raise ValueError("Dias de atraso não pode ser negativo")
    
    if valor_nominal < 0:
        raise ValueError("Valor nominal não pode ser negativo")
    
    faixas = {
        (0, 30): Decimal('0.00'),
        (31, 60): Decimal('0.01'),
        (61, 90): Decimal('0.03'),
        (91, 120): Decimal('0.10'),
        (121, 150): Decimal('0.30'),
        (151, 180): Decimal('0.50'),
        (181, 360): Decimal('0.75'),
        (361, 999999): Decimal('1.00')
    }
    
    for (min_dias, max_dias), percentual in faixas.items():
        if min_dias <= dias_atraso <= max_dias:
            pdd = valor_nominal * percentual
            return pdd.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return Decimal('0.00')


def calcular_ir_resgate(
    valor_resgate: Decimal,
    valor_aplicacao: Decimal,
    dias_aplicado: int
) -> Decimal:
    """
    Calcula Imposto de Renda sobre resgate (tabela regressiva).
    
    Tabela regressiva:
    - Até 180 dias: 22,5%
    - 181 a 360 dias: 20%
    - 361 a 720 dias: 17,5%
    - Acima de 720 dias: 15%
    
    Referência: Lei 11.033/2004
    
    Args:
        valor_resgate: Valor bruto do resgate
        valor_aplicacao: Valor original aplicado (custo médio)
        dias_aplicado: Dias corridos desde aplicação
        
    Returns:
        Valor do IR a reter
    """
    if dias_aplicado < 0:
        raise ValueError("Dias aplicado não pode ser negativo")
    
    rendimento = valor_resgate - valor_aplicacao
    
    if rendimento <= 0:
        return Decimal('0.00')
    
    # Tabela regressiva
    if dias_aplicado <= 180:
        aliquota = Decimal('0.225')
    elif dias_aplicado <= 360:
        aliquota = Decimal('0.20')
    elif dias_aplicado <= 720:
        aliquota = Decimal('0.175')
    else:
        aliquota = Decimal('0.15')
    
    ir = rendimento * aliquota
    return ir.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_iof(valor_resgate: Decimal, dias_aplicado: int) -> Decimal:
    """
    Calcula IOF regressivo (zero após 30 dias).
    
    Tabela regressiva diária:
    - D+0: 96%
    - D+1: 93%
    - D+2: 90%
    - ...
    - D+29: 3%
    - D+30 em diante: 0%
    
    Referência: Decreto 6.306/2007
    
    Args:
        valor_resgate: Valor do resgate
        dias_aplicado: Dias corridos desde aplicação
        
    Returns:
        Valor do IOF a reter
    """
    if dias_aplicado < 0:
        raise ValueError("Dias aplicado não pode ser negativo")
    
    if dias_aplicado >= 30:
        return Decimal('0.00')
    
    # Fórmula: 96% - (dias * 3,33%)
    percentual_iof = Decimal('0.96') - (Decimal(dias_aplicado) * Decimal('0.0333'))
    percentual_iof = max(percentual_iof, Decimal('0.00'))
    
    # IOF é 1% sobre o rendimento, ajustado pelo percentual regressivo
    iof = valor_resgate * percentual_iof * Decimal('0.01')
    return iof.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_impostos_resgate(
    valor_bruto: Decimal,
    valor_aplicacao: Decimal,
    data_aplicacao,  # datetime.date
    data_resgate      # datetime.date
) -> dict:
    """
    Calcula todos os impostos de um resgate (IR + IOF).
    
    Args:
        valor_bruto: Valor bruto do resgate
        valor_aplicacao: Custo médio de aquisição
        data_aplicacao: Data da aplicação original
        data_resgate: Data do resgate
        
    Returns:
        dict com ir_retido, iof_retido, valor_liquido
    """
    dias_aplicado = (data_resgate - data_aplicacao).days
    
    ir = calcular_ir_resgate(valor_bruto, valor_aplicacao, dias_aplicado)
    iof = calcular_iof(valor_bruto, dias_aplicado)
    valor_liquido = valor_bruto - ir - iof
    
    return {
        'ir_retido': ir,
        'iof_retido': iof,
        'valor_liquido': valor_liquido,
        'dias_aplicado': dias_aplicado,
        'rendimento_bruto': valor_bruto - valor_aplicacao
    }