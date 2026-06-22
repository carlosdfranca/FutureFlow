from django.contrib import admin
from .models import OperacaoCessao, Titulo, EventoTitulo, Aplicacao


# ============================================
# ADMIN: OPERAÇÃO DE CESSÃO
# ============================================

class TituloInline(admin.TabularInline):
    model = Titulo
    extra = 0
    fields = ['numero_titulo', 'sacado_nome', 'valor_nominal', 'data_vencimento', 'ativo']
    readonly_fields = ['numero_titulo', 'sacado_nome', 'valor_nominal', 'data_vencimento', 'ativo']
    can_delete = False
    max_num = 0  # Não permite adicionar via inline


@admin.register(OperacaoCessao)
class OperacaoCessaoAdmin(admin.ModelAdmin):
    list_display = [
        'numero_contrato', 
        'cedente_nome', 
        'fundo', 
        'data_aquisicao', 
        'valor_total_nominal',
        'status'
    ]
    list_filter = ['status', 'fundo', 'data_aquisicao']
    search_fields = ['numero_contrato', 'cedente_nome', 'cedente_cnpj']
    readonly_fields = ['criado_por', 'criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('fundo', 'numero_contrato', 'data_contrato', 'data_aquisicao', 'status')
        }),
        ('Cedente', {
            'fields': ('cedente_cnpj', 'cedente_nome', 'cedente_endereco')
        }),
        ('Valores', {
            'fields': ('valor_total_nominal', 'valor_total_aquisicao')
        }),
        ('Observações', {
            'fields': ('observacoes',),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TituloInline]


# ============================================
# ADMIN: TÍTULO
# ============================================

class EventoTituloInline(admin.TabularInline):
    model = EventoTitulo
    extra = 0
    fields = ['tipo_evento', 'data_evento', 'valor_evento', 'descricao']
    readonly_fields = ['tipo_evento', 'data_evento', 'valor_evento', 'descricao']
    can_delete = False
    max_num = 0


@admin.register(Titulo)
class TituloAdmin(admin.ModelAdmin):
    list_display = [
        'numero_titulo',
        'sacado_nome',
        'fundo',
        'valor_nominal',
        'saldo_devedor',
        'data_vencimento',
        'classificacao_risco',
        'ativo'
    ]
    list_filter = ['ativo', 'classificacao_risco', 'fundo', 'data_vencimento']
    search_fields = ['numero_titulo', 'sacado_nome', 'sacado_cpf_cnpj']
    readonly_fields = ['criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Relacionamentos', {
            'fields': ('operacao_cessao', 'fundo')
        }),
        ('Identificação', {
            'fields': ('numero_titulo', 'sacado_nome', 'sacado_cpf_cnpj')
        }),
        ('Valores', {
            'fields': ('valor_nominal', 'valor_aquisicao', 'saldo_devedor')
        }),
        ('Datas', {
            'fields': ('data_emissao', 'data_vencimento')
        }),
        ('Risco e PDD', {
            'fields': ('classificacao_risco', 'percentual_pdd', 'valor_pdd')
        }),
        ('Status', {
            'fields': ('ativo',)
        }),
        ('Auditoria', {
            'fields': ('criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EventoTituloInline]


# ============================================
# ADMIN: EVENTO DE TÍTULO
# ============================================

@admin.register(EventoTitulo)
class EventoTituloAdmin(admin.ModelAdmin):
    list_display = [
        'titulo',
        'tipo_evento',
        'data_evento',
        'valor_evento',
        'usuario_responsavel',
        'criado_em'
    ]
    list_filter = ['tipo_evento', 'data_evento']
    search_fields = ['titulo__numero_titulo', 'documento_referencia', 'descricao']
    readonly_fields = ['criado_em']
    
    fieldsets = (
        ('Evento', {
            'fields': ('titulo', 'tipo_evento', 'data_evento', 'valor_evento')
        }),
        ('Documentação', {
            'fields': ('descricao', 'documento_referencia')
        }),
        ('Auditoria', {
            'fields': ('usuario_responsavel', 'criado_em')
        }),
    )


# ============================================
# ADMIN: APLICAÇÃO
# ============================================

@admin.register(Aplicacao)
class AplicacaoAdmin(admin.ModelAdmin):
    list_display = [
        'descricao',
        'tipo_aplicacao',
        'fundo',
        'valor',
        'data_aplicacao',
        'criado_por'
    ]
    list_filter = ['tipo_aplicacao', 'fundo', 'data_aplicacao']
    search_fields = ['descricao']
    readonly_fields = ['criado_por', 'criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('fundo', 'tipo_aplicacao', 'descricao', 'valor', 'data_aplicacao')
        }),
        ('Auditoria', {
            'fields': ('criado_por', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
