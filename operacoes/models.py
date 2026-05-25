from django.db import models
from django.conf import settings
import uuid


# ============================================
# ENUMS
# ============================================

class TipoEventoTitulo(models.IntegerChoices):
    """
    Tipos de eventos operacionais sobre títulos (recebíveis).
    Valores correspondem ao campo OCORRENCIA do CNAB240.
    """
    AQUISICAO = 1, 'Aquisição de Título'
    BAIXA = 2, 'Baixa de Título'
    LIQUIDACAO_PARCIAL = 14, 'Liquidação Parcial'
    LIQUIDACAO_TOTAL = 6, 'Liquidação Total'
    PRORROGACAO = 10, 'Prorrogação de Vencimento'
    AJUSTE_VALOR = 31, 'Ajuste de Valor'
    REATIVACAO = 99, 'Reativação de Título'
    SUBSTITUICAO = 50, 'Substituição de Título'
    PROTESTO = 60, 'Protesto'


class TipoAplicacao(models.TextChoices):
    """
    Tipos de aplicações em ativos diversos.
    Representa onde o fundo aplica seus recursos.
    """
    TESOURO = 'TESOURO', 'Tesouro Direto'
    COTA_FUNDO = 'COTA_FUNDO', 'Cota de Fundo'
    COMPROMISSADA = 'COMPROMISSADA', 'Operação Compromissada'
    OUTROS = 'OUTROS', 'Outros'


# ============================================
# MODELO: OPERAÇÃO DE CESSÃO
# ============================================

class OperacaoCessao(models.Model):
    """
    Representa um contrato/operação de cessão de crédito.
    Agrupa múltiplos títulos cedidos numa mesma operação.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento
    fundo = models.ForeignKey(
        'fundos.Fundo',
        on_delete=models.PROTECT,
        related_name='operacoes_cessao'
    )
    
    # Informações do Cedente
    cedente_cnpj = models.CharField(max_length=18, db_index=True)
    cedente_nome = models.CharField(max_length=200)
    cedente_endereco = models.TextField(blank=True)
    
    # Dados do Contrato
    numero_contrato = models.CharField(max_length=50, unique=True, db_index=True)
    data_contrato = models.DateField()
    data_aquisicao = models.DateField(help_text='Data de aquisição dos títulos pelo fundo')
    
    # Valores Totais
    valor_total_nominal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text='Soma dos valores nominais dos títulos'
    )
    valor_total_aquisicao = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text='Valor pago pelo fundo na aquisição'
    )
    
    # Controle
    status = models.CharField(
        max_length=20,
        choices=[
            ('RASCUNHO', 'Rascunho'),
            ('CONFIRMADA', 'Confirmada'),
            ('CANCELADA', 'Cancelada'),
        ],
        default='RASCUNHO'
    )
    
    # Observações
    observacoes = models.TextField(blank=True)
    
    # Auditoria
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='cessoes_criadas'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'operacoes_cessao'
        verbose_name = 'Operação de Cessão'
        verbose_name_plural = 'Operações de Cessão'
        ordering = ['-data_aquisicao']
        indexes = [
            models.Index(fields=['fundo', 'status']),
            models.Index(fields=['cedente_cnpj']),
            models.Index(fields=['data_aquisicao']),
        ]
    
    def __str__(self):
        return f"{self.numero_contrato} - {self.cedente_nome}"


# ============================================
# MODELO: TÍTULO (RECEBÍVEL)
# ============================================

class Titulo(models.Model):
    """
    Representa um título/recebível individual adquirido numa cessão.
    Mantém estado atual denormalizado para performance.
    Histórico completo mantido em EventoTitulo.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamentos
    operacao_cessao = models.ForeignKey(
        OperacaoCessao,
        on_delete=models.PROTECT,
        related_name='titulos'
    )
    fundo = models.ForeignKey(
        'fundos.Fundo',
        on_delete=models.PROTECT,
        related_name='titulos',
        help_text='Redundância controlada para queries eficientes'
    )
    
    # Identificação do Título
    numero_titulo = models.CharField(max_length=100, db_index=True)
    sacado_nome = models.CharField(max_length=200)
    sacado_cpf_cnpj = models.CharField(max_length=18, db_index=True)
    
    # Valores
    valor_nominal = models.DecimalField(max_digits=16, decimal_places=2)
    valor_aquisicao = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text='Valor pago pelo fundo'
    )
    
    # Datas
    data_emissao = models.DateField()
    data_vencimento = models.DateField(db_index=True)
    
    # Estado Atual (denormalizado)
    saldo_devedor = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text='Atualizado conforme eventos de liquidação'
    )
    ativo = models.BooleanField(
        default=True,
        db_index=True,
        help_text='False se título foi baixado/liquidado totalmente'
    )
    
    # PDD (Provisão para Devedores Duvidosos)
    percentual_pdd = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Calculado conforme Resolução CMN 2682'
    )
    valor_pdd = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    
    # Classificação de Risco
    classificacao_risco = models.CharField(
        max_length=2,
        choices=[
            ('AA', 'AA - 0 dias'),
            ('A', 'A - 15-30 dias'),
            ('B', 'B - 31-60 dias'),
            ('C', 'C - 61-90 dias'),
            ('D', 'D - 91-120 dias'),
            ('E', 'E - 121-150 dias'),
            ('F', 'F - 151-180 dias'),
            ('G', 'G - 181-360 dias'),
            ('H', 'H - > 360 dias'),
        ],
        default='AA'
    )
    
    # Auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'operacoes_titulo'
        verbose_name = 'Título (Recebível)'
        verbose_name_plural = 'Títulos (Recebíveis)'
        ordering = ['data_vencimento']
        indexes = [
            models.Index(fields=['fundo', 'ativo']),
            models.Index(fields=['sacado_cpf_cnpj']),
            models.Index(fields=['data_vencimento', 'ativo']),
        ]
    
    def __str__(self):
        return f"{self.numero_titulo} - {self.sacado_nome}"


# ============================================
# MODELO: EVENTO DE TÍTULO
# ============================================

class EventoTitulo(models.Model):
    """
    Event sourcing: histórico imutável de todos os eventos operacionais.
    Permite rebuild do estado atual e auditoria completa.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relacionamento
    titulo = models.ForeignKey(
        Titulo,
        on_delete=models.CASCADE,
        related_name='eventos'
    )
    
    # Tipo de Evento (OCORRENCIA CNAB)
    tipo_evento = models.IntegerField(
        choices=TipoEventoTitulo.choices,
        db_index=True
    )
    
    # Dados do Evento
    data_evento = models.DateField(db_index=True)
    valor_evento = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Valor relacionado (ex: valor liquidado, ajustado)'
    )
    
    # Documentação
    descricao = models.TextField(blank=True)
    documento_referencia = models.CharField(
        max_length=100,
        blank=True,
        help_text='Número de documento/comprovante'
    )
    
    # Auditoria
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='eventos_titulo'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'operacoes_evento_titulo'
        verbose_name = 'Evento de Título'
        verbose_name_plural = 'Eventos de Título'
        ordering = ['-data_evento', '-criado_em']
        indexes = [
            models.Index(fields=['titulo', 'tipo_evento']),
            models.Index(fields=['data_evento']),
            models.Index(fields=['tipo_evento']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_evento_display()} - {self.titulo.numero_titulo} - {self.data_evento}"


# ============================================
# MODELO: APLICAÇÃO EM ATIVO
# ============================================

class Aplicacao(models.Model):
    """
    Representa aplicação do fundo em ativo diverso.
    Registro simples de aplicações financeiras do fundo.
    Diferente de MovimentacaoCota (que é aplicação de COTISTA no fundo).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    fundo = models.ForeignKey(
        'fundos.Fundo',
        on_delete=models.PROTECT,
        related_name='aplicacoes_ativo'
    )
    
    tipo_aplicacao = models.CharField(
        max_length=20,
        choices=TipoAplicacao.choices,
        db_index=True
    )
    
    descricao = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=16, decimal_places=2)
    data_aplicacao = models.DateField(db_index=True)
    
    # Auditoria
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='aplicacoes_criadas'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'operacoes_aplicacao'
        verbose_name = 'Aplicação em Ativo'
        verbose_name_plural = 'Aplicações em Ativos'
        ordering = ['-data_aplicacao']
        indexes = [
            models.Index(fields=['fundo', 'tipo_aplicacao']),
            models.Index(fields=['tipo_aplicacao']),
            models.Index(fields=['data_aplicacao']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_aplicacao_display()} - {self.descricao} - R$ {self.valor}"
