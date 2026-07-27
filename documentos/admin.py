from django.contrib import admin

from .models import DocumentoFundo


@admin.register(DocumentoFundo)
class DocumentoFundoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'fundo', 'categoria', 'tamanho', 'enviado_por', 'data_upload')
    list_filter = ('categoria', 'fundo')
    search_fields = ('nome', 'fundo__razao_social', 'fundo__cnpj')
    readonly_fields = ('id', 'tamanho', 'data_upload')
    autocomplete_fields = ['fundo']
