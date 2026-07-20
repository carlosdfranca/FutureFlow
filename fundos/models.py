from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from usuarios.models import Empresa
from django.conf import settings
import uuid

# ============================================
# ENUMS
# ============================================

class TipoFundo(models.TextChoices):
    FII = 'FII', 'Fundo de Investimento Imobiliário'
    FIDC = 'FIDC', 'Fundo de Investimento em Direitos Creditórios'
    FIP = 'FIP', 'Fundo de Investimento em Participações'

class ClassificacaoInvestidor(models.TextChoices):
    PROFISSIONAL = 'PROFISSIONAL', 'Profissional'
    QUALIFICADO  = 'QUALIFICADO',  'Qualificado'

class TipoCondominio(models.TextChoices):
    PADRONIZADO     = 'PADRONIZADO',     'Padronizado'
    NAO_PADRONIZADO = 'NAO_PADRONIZADO', 'Não Padronizado'

class EstruturaFundo(models.TextChoices):
    ABERTO  = 'ABERTO',  'Aberto'
    FECHADO = 'FECHADO', 'Fechado'

class StatusMovimentacao(models.TextChoices):
    SOLICITADO = 'SOLICITADO', 'Solicitado'
    AGUARDANDO_PAGAMENTO = 'AGUARDANDO_PAGAMENTO', 'Aguardando Pagamento'
    CONFIRMADO = 'CONFIRMADO', 'Confirmado'
    CANCELADO = 'CANCELADO', 'Cancelado'

# ============================================
# MODELO: FUNDO
# ============================================

class Fundo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='fundos')
    
    # Identificação
    cnpj = models.CharField(max_length=14, unique=True, db_index=True)
    codigo_anbima = models.CharField(max_length=6, unique=True, db_index=True, null=True, blank=True)
    razao_social = models.CharField(max_length=200)
    nome_comercial = models.CharField(max_length=200, blank=True)
    tipo_fundo = models.CharField(max_length=10, choices=TipoFundo.choices)
    data_constituicao = models.DateField()
    
    # Configurações
    tipo_cotizacao = models.CharField(max_length=10, default='D+0', help_text='D+0 ou D+1')
    prazo_liquidacao = models.IntegerField(default=0, help_text='Dias úteis')
    horario_corte = models.TimeField(default='14:00')
    
    # Taxas (texto livre — ex: "1,50%", "Isento")
    taxa_administracao = models.CharField(max_length=100, blank=True, default='')
    taxa_gestao = models.CharField(max_length=100, blank=True, default='')
    taxa_performance = models.CharField(max_length=100, blank=True, default='')
    taxa_administracao_minima = models.CharField(max_length=100, blank=True, default='')
    taxa_gestao_minima = models.CharField(max_length=100, blank=True, default='')
    taxa_performance_minima = models.CharField(max_length=100, blank=True, default='')

    # Regulamento
    administrador = models.CharField(max_length=200, blank=True)
    gestor = models.CharField(max_length=200, blank=True)
    condicoes_resgate = models.CharField(max_length=300, blank=True)
    aporte_minimo = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    data_encerramento_exercicio = models.CharField(max_length=10, blank=True, help_text='Ex: 31/12')
    limite_concentracao = models.CharField(max_length=300, blank=True)

    # Enquadramento (limites de composição da carteira, em % da carteira)
    limite_direitos_creditorios = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Limite máximo em Direitos Creditórios (Cessões), em % da carteira',
    )
    limite_liquidez = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Limite máximo em Liquidez (Aplicações), em % da carteira',
    )

    # Classificação e estrutura
    classificacao_investidor = models.CharField(max_length=20, choices=ClassificacaoInvestidor.choices, blank=True)
    tipo_condominio = models.CharField(max_length=20, choices=TipoCondominio.choices, blank=True)
    estrutura_fundo = models.CharField(max_length=10, choices=EstruturaFundo.choices, blank=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    # JSON para flexibilidade
    politica_investimento = models.JSONField(null=True, blank=True)
    dados_adicionais = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'fundos'
        verbose_name = 'Fundo'
        verbose_name_plural = 'Fundos'
        ordering = ['-data_cadastro']
        indexes = [
            models.Index(fields=['cnpj']),
            models.Index(fields=['codigo_anbima']),
            models.Index(fields=['empresa', 'ativo']),
        ]
    
    def __str__(self):
        return f"{self.razao_social} ({self.cnpj})"

# ============================================
# MODELO: COTISTA
# ============================================

class Cotista(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identificação
    cpf_cnpj = models.CharField(max_length=14, unique=True, db_index=True)
    tipo_pessoa = models.CharField(max_length=2, choices=[('PF', 'Pessoa Física'), ('PJ', 'Pessoa Jurídica')])
    nome_razao_social = models.CharField(max_length=200)
    email = models.EmailField(max_length=100, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    
    # Endereço
    cep = models.CharField(max_length=8, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=10, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    
    # Compliance
    qualificacao = models.CharField(max_length=50, blank=True, help_text='Varejo, Qualificado, Profissional')
    perfil_investidor = models.CharField(max_length=50, blank=True)
    data_suitability = models.DateField(null=True, blank=True)
    
    # Dados bancários
    banco = models.CharField(max_length=3, blank=True)
    agencia = models.CharField(max_length=10, blank=True)
    conta = models.CharField(max_length=20, blank=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    dados_adicionais = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'cotistas'
        verbose_name = 'Cotista'
        verbose_name_plural = 'Cotistas'
        ordering = ['nome_razao_social']
        indexes = [
            models.Index(fields=['cpf_cnpj']),
            models.Index(fields=['tipo_pessoa']),
        ]
    
    def __str__(self):
        return f"{self.nome_razao_social} ({self.cpf_cnpj})"

# ============================================
# MODELO: MOVIMENTAÇÃO DE COTAS
# ============================================

class MovimentacaoCota(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    tipo_movimentacao = models.CharField(
        max_length=20, 
        choices=[
            ('APLICACAO', 'Aplicação'),
            ('RESGATE', 'Resgate'),
            ('COME_COTAS', 'Come-Cotas'),
        ]
    )
    
    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name='movimentacoes')
    cotista = models.ForeignKey(Cotista, on_delete=models.PROTECT, related_name='movimentacoes')
    
    # Datas
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_cotizacao = models.DateField()
    data_liquidacao = models.DateField()
    
    # Valores
    valor_financeiro = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    valor_cota = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    quantidade_cotas = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    
    # Tributos
    ir_retido = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    iof_retido = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    valor_liquido = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=25, choices=StatusMovimentacao.choices, default=StatusMovimentacao.SOLICITADO)
    
    dados_adicionais = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'movimentacoes_cotas'
        verbose_name = 'Movimentação de Cota'
        verbose_name_plural = 'Movimentações de Cotas'
        ordering = ['-data_solicitacao']
        indexes = [
            models.Index(fields=['fundo', 'data_cotizacao']),
            models.Index(fields=['cotista', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.tipo_movimentacao} - {self.fundo.razao_social} - {self.data_solicitacao.date()}"

# ============================================
# MODELO: HISTÓRICO DE COTAS
# ============================================

class CotaHistorico(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fundo = models.ForeignKey(Fundo, on_delete=models.CASCADE, related_name='cotas_historico')
    data_referencia = models.DateField(db_index=True)
    
    # Valores
    valor_cota = models.DecimalField(max_digits=16, decimal_places=6)
    patrimonio_liquido = models.DecimalField(max_digits=16, decimal_places=2)
    quantidade_cotas = models.DecimalField(max_digits=18, decimal_places=6)
    quantidade_cotistas = models.IntegerField(default=0)
    
    # Movimentações do dia
    captacao_dia = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    resgate_dia = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    
    # Rentabilidade
    rentabilidade_dia = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    rentabilidade_mes = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    rentabilidade_ano = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    # Envio ANBIMA
    enviado_anbima = models.BooleanField(default=False)
    data_envio_anbima = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'cotas_historico'
        verbose_name = 'Histórico de Cota'
        verbose_name_plural = 'Histórico de Cotas'
        ordering = ['-data_referencia']
        unique_together = [['fundo', 'data_referencia']]
        indexes = [
            models.Index(fields=['fundo', '-data_referencia']),
            models.Index(fields=['data_referencia']),
        ]
    
    def __str__(self):
        return f"{self.fundo.razao_social} - {self.data_referencia} - R$ {self.valor_cota}"

# ============================================
# MODELO: ATIVOS
# ============================================

class Ativo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name='ativos')
    
    tipo_ativo = models.CharField(max_length=50)
    codigo_isin = models.CharField(max_length=12, blank=True)
    codigo_negociacao = models.CharField(max_length=20, blank=True)
    emissor_cnpj = models.CharField(max_length=14, blank=True)
    emissor_nome = models.CharField(max_length=200, blank=True)
    
    # Quantidade e valores
    quantidade = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    preco_aquisicao = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    preco_mercado = models.DecimalField(max_digits=16, decimal_places=6, null=True, blank=True)
    valor_mercado = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    
    data_aquisicao = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    
    # Renda Fixa
    taxa_cupom = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    indexador = models.CharField(max_length=20, blank=True)
    
    # Status
    ativo = models.BooleanField(default=True)
    dados_adicionais = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'ativos'
        verbose_name = 'Ativo'
        verbose_name_plural = 'Ativos'
        ordering = ['-data_aquisicao']
        indexes = [
            models.Index(fields=['fundo', 'ativo']),
            models.Index(fields=['tipo_ativo']),
        ]
    
    def __str__(self):
        return f"{self.tipo_ativo} - {self.codigo_isin or self.codigo_negociacao}"

# ============================================
# MODELO: RECEBÍVEIS (ESPECÍFICO FIDC)
# ============================================

class Recebiveis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fundo = models.ForeignKey(Fundo, on_delete=models.PROTECT, related_name='recebiveis')
    
    # Cedente
    cedente_cnpj = models.CharField(max_length=14, db_index=True)
    cedente_nome = models.CharField(max_length=200)
    
    # Sacado
    sacado_cpf_cnpj = models.CharField(max_length=14, db_index=True)
    sacado_nome = models.CharField(max_length=200)
    
    # Título
    tipo_credito = models.CharField(max_length=50)
    numero_titulo = models.CharField(max_length=50)
    data_vencimento = models.DateField(db_index=True)
    
    # Valores
    valor_nominal = models.DecimalField(max_digits=16, decimal_places=2)
    valor_cessao = models.DecimalField(max_digits=16, decimal_places=2)
    
    # Inadimplência
    status = models.CharField(
        max_length=30, 
        default='A_VENCER',
        choices=[
            ('A_ENVIAR', 'A Enviar'),
            ('EM_COBRANCA', 'Em Cobrança'),
            ('A_VENCER', 'A Vencer'),
            ('VENCIDO', 'Vencido'),
            ('PAGO', 'Pago'),
            ('BAIXADO', 'Baixado'),
            ('REJEITADO', 'Rejeitado'),
        ]
    )
    dias_atraso = models.IntegerField(default=0)
    pdd_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    pdd_valor = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    
    dados_adicionais = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'recebiveis'
        verbose_name = 'Recebível'
        verbose_name_plural = 'Recebíveis'
        ordering = ['data_vencimento']
        indexes = [
            models.Index(fields=['fundo', 'status']),
            models.Index(fields=['cedente_cnpj']),
            models.Index(fields=['sacado_cpf_cnpj']),
            models.Index(fields=['data_vencimento']),
        ]
    
    def __str__(self):
        return f"{self.numero_titulo} - {self.sacado_nome}"


# ============================================
# MODELO: INFORME MENSAL (FECHAMENTO CVM/ANBIMA)
# ============================================

class SegmentoCarteira(models.TextChoices):
    SETOR_PUBLICO       = 'SETOR_PUBLICO',       'Setor Público'
    INDUSTRIAL          = 'INDUSTRIAL',           'Industrial'
    COMERCIAL           = 'COMERCIAL',            'Comercial'
    SERVICOS            = 'SERVICOS',             'Serviços'
    AGRONEG             = 'AGRONEG',              'Agronegócio'
    FINANCEIRO          = 'FINANCEIRO',           'Financeiro'
    FACTORING           = 'FACTORING',            'Factoring'
    CARTAO_CREDITO      = 'CARTAO_CREDITO',       'Cartão de Crédito'
    VALORES_MOBILIARIOS = 'VALORES_MOBILIARIOS',  'Valores Mobiliários'
    ACAO_JUDIC          = 'ACAO_JUDIC',           'Ação Judicial'
    OUTROS              = 'OUTROS',               'Outros'


class InformeMensal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fundo = models.ForeignKey(Fundo, on_delete=models.CASCADE, related_name='informes_mensais')

    # Identificação do informe
    competencia = models.DateField(
        db_index=True,
        help_text='Primeiro dia do mês de competência. Ex: 2026-02-01 para 02/2026.'
    )
    versao_xml = models.CharField(max_length=10, blank=True)
    cnpj_administrador = models.CharField(max_length=14, blank=True)
    arquivo_xml_nome = models.CharField(max_length=255, blank=True)

    # Ativos
    vl_disponib = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_carteira = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_total_ativos = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Direitos Creditórios
    vl_dicred = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_dicred_cedent = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_dicred_inad = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_dicred_venc_inad = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Passivo
    vl_total_passivo = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_pgto_curprz = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_pgto_lprazo = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Patrimônio Líquido
    vl_patrimonio_liquido = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_patrimonio_liquido_medio = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Cotas — Classe Subordinada
    qt_cotas_subord = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    vl_cota_subord = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    # Cotas — Classe Sênior
    qt_cotas_senior = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    vl_cota_senior = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    # Cotistas
    qt_total_cotistas = models.IntegerField(null=True, blank=True)
    qt_cotistas_senior = models.IntegerField(null=True, blank=True)
    qt_cotistas_subord = models.IntegerField(null=True, blank=True)

    # Rentabilidade mensal (%)
    rentabilidade_senior = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    rentabilidade_subord = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Desempenho esperado / realizado (%)
    desemp_esp_senior = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    desemp_real_senior = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    desemp_esp_subord = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    desemp_real_subord = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    # Liquidez
    vl_liqdez_30 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_liqdez_60 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_liqdez_90 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_liqdez_180 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_liqdez_360 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_liqdez_mais_360 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Perfil de vencimentos — sem aquisição
    vl_venc_30 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_31_60 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_61_90 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_91_120 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_121_180 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_181_360 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_361_720 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_venc_mais_720 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Captação / Resgate no mês
    vl_capt_senior = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_capt_subord = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_resg_senior = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_resg_subord = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Rating SCR (escala AA → H)
    vl_rating_aa = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_rating_a = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_rating_b = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_rating_c = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    vl_rating_d_h = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # Auditoria
    dados_brutos = models.JSONField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='informes_importados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundos_informe_mensal'
        verbose_name = 'Informe Mensal'
        verbose_name_plural = 'Informes Mensais'
        ordering = ['-competencia']
        unique_together = [['fundo', 'competencia']]
        indexes = [
            models.Index(fields=['fundo', '-competencia']),
        ]

    def __str__(self):
        return f"{self.fundo.razao_social} — {self.competencia.strftime('%m/%Y')}"

    @property
    def competencia_display(self):
        return self.competencia.strftime('%m/%Y')


# ============================================
# MODELO: CEDENTES DO INFORME MENSAL
# ============================================

class InformeMensalCedente(models.Model):
    informe = models.ForeignKey(
        InformeMensal, on_delete=models.CASCADE, related_name='cedentes'
    )
    nr_pf_pj_cedent = models.CharField(max_length=14)
    pr_cedent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'fundos_informe_mensal_cedente'
        verbose_name = 'Cedente do Informe'
        verbose_name_plural = 'Cedentes do Informe'
        ordering = ['-pr_cedent']

    def __str__(self):
        return f"{self.nr_pf_pj_cedent} — {self.pr_cedent}"


# ============================================
# MODELO: CARTEIRA POR SEGMENTO DO INFORME MENSAL
# ============================================

class InformeMensalCarteira(models.Model):
    informe = models.ForeignKey(
        InformeMensal, on_delete=models.CASCADE, related_name='carteira'
    )
    segmento = models.CharField(max_length=50, choices=SegmentoCarteira.choices)
    subsegmento = models.CharField(max_length=80, null=True, blank=True)
    valor = models.DecimalField(max_digits=16, decimal_places=2)
    percentual_carteira = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = 'fundos_informe_mensal_carteira'
        verbose_name = 'Segmento de Carteira'
        verbose_name_plural = 'Segmentos de Carteira'
        ordering = ['-valor']
        unique_together = [['informe', 'segmento', 'subsegmento']]

    def __str__(self):
        label = f"{self.segmento}"
        if self.subsegmento:
            label += f" / {self.subsegmento}"
        return f"{label}: R$ {self.valor:,.2f}"