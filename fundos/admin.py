from django.contrib import admin
from .models import Fundo, Cotista, MovimentacaoCota, CotaHistorico, Ativo, Recebiveis, InformeMensal, InformeMensalCedente, InformeMensalCarteira

@admin.register(Fundo)
class FundoAdmin(admin.ModelAdmin):
    list_display = ('razao_social', 'cnpj', 'tipo_fundo', 'ativo', 'data_cadastro')
    list_filter = ('tipo_fundo', 'ativo', 'empresa')
    search_fields = ('razao_social', 'cnpj', 'codigo_anbima')
    readonly_fields = ('id', 'data_cadastro', 'data_atualizacao')

@admin.register(Cotista)
class CotistaAdmin(admin.ModelAdmin):
    list_display = ('nome_razao_social', 'cpf_cnpj', 'tipo_pessoa', 'email', 'ativo')
    list_filter = ('tipo_pessoa', 'qualificacao', 'ativo')
    search_fields = ('nome_razao_social', 'cpf_cnpj', 'email')

@admin.register(MovimentacaoCota)
class MovimentacaoCotaAdmin(admin.ModelAdmin):
    list_display = ('fundo', 'cotista', 'tipo_movimentacao', 'valor_financeiro', 'data_cotizacao', 'status')
    list_filter = ('tipo_movimentacao', 'status', 'data_cotizacao')
    search_fields = ('fundo__razao_social', 'cotista__nome_razao_social')
    date_hierarchy = 'data_cotizacao'

@admin.register(CotaHistorico)
class CotaHistoricoAdmin(admin.ModelAdmin):
    list_display = ('fundo', 'data_referencia', 'valor_cota', 'patrimonio_liquido', 'quantidade_cotas')
    list_filter = ('fundo', 'data_referencia')
    date_hierarchy = 'data_referencia'

@admin.register(Ativo)
class AtivoAdmin(admin.ModelAdmin):
    list_display = ('fundo', 'tipo_ativo', 'codigo_isin', 'emissor_nome', 'valor_mercado', 'ativo')
    list_filter = ('tipo_ativo', 'ativo', 'fundo')
    search_fields = ('codigo_isin', 'codigo_negociacao', 'emissor_nome')

@admin.register(Recebiveis)
class RecebiveisAdmin(admin.ModelAdmin):
    list_display = ('fundo', 'numero_titulo', 'cedente_nome', 'sacado_nome', 'valor_nominal', 'data_vencimento', 'status', 'dias_atraso')
    list_filter = ('status', 'fundo', 'data_vencimento')
    search_fields = ('numero_titulo', 'cedente_nome', 'sacado_nome', 'cedente_cnpj', 'sacado_cpf_cnpj')
    date_hierarchy = 'data_vencimento'


class InformeMensalCarteiraInline(admin.TabularInline):
    model = InformeMensalCarteira
    extra = 0
    readonly_fields = ('segmento', 'subsegmento', 'valor', 'percentual_carteira')


class InformeMensalCedenteInline(admin.TabularInline):
    model = InformeMensalCedente
    extra = 0
    readonly_fields = ('nr_pf_pj_cedent', 'pr_cedent')


@admin.register(InformeMensal)
class InformeMensalAdmin(admin.ModelAdmin):
    list_display = ('fundo', 'competencia_display', 'vl_patrimonio_liquido', 'vl_carteira', 'qt_total_cotistas', 'criado_em')
    list_filter = ('fundo', 'competencia')
    search_fields = ('fundo__razao_social', 'fundo__cnpj')
    readonly_fields = ('id', 'criado_em', 'atualizado_em', 'criado_por')
    date_hierarchy = 'competencia'
    inlines = [InformeMensalCarteiraInline, InformeMensalCedenteInline]

    def competencia_display(self, obj):
        return obj.competencia_display
    competencia_display.short_description = 'Competência'
    competencia_display.admin_order_field = 'competencia'


@admin.register(InformeMensalCarteira)
class InformeMensalCarteiraAdmin(admin.ModelAdmin):
    list_display = ('informe', 'segmento', 'subsegmento', 'valor', 'percentual_carteira')
    list_filter = ('segmento', 'informe__fundo')
    search_fields = ('informe__fundo__razao_social',)


@admin.register(InformeMensalCedente)
class InformeMensalCedenteAdmin(admin.ModelAdmin):
    list_display = ('informe', 'nr_pf_pj_cedent', 'pr_cedent')
    search_fields = ('nr_pf_pj_cedent', 'informe__fundo__razao_social')
