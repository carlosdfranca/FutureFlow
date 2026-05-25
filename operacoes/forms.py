from django import forms
from django.forms import formset_factory
from fundos.models import Fundo
from .models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo, Aplicacao, TipoAplicacao


# ============================================
# FORMS: CESSÃO
# ============================================

class CessaoOperacaoForm(forms.Form):
    """Form para dados gerais da operação de cessão"""
    
    fundo = forms.ModelChoiceField(
        queryset=Fundo.objects.filter(ativo=True),
        label="Fundo FIDC",
        required=True,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    
    numero_contrato = forms.CharField(
        max_length=50,
        label="Número do Contrato",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex: CONT-2024-001"
        })
    )
    
    data_contrato = forms.DateField(
        label="Data do Contrato",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )
    
    data_aquisicao = forms.DateField(
        label="Data de Aquisição",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )
    
    cedente_cnpj = forms.CharField(
        max_length=18,
        label="CNPJ do Cedente",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00.000.000/0000-00"
        })
    )
    
    cedente_nome = forms.CharField(
        max_length=200,
        label="Nome do Cedente",
        widget=forms.TextInput(attrs={
            "class": "form-control"
        })
    )
    
    cedente_endereco = forms.CharField(
        required=False,
        label="Endereço do Cedente",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3
        })
    )
    
    observacoes = forms.CharField(
        required=False,
        label="Observações",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3
        })
    )


class TituloForm(forms.Form):
    """Form para cada título individual"""
    
    numero_titulo = forms.CharField(
        max_length=100,
        label="Número do Título",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    sacado_nome = forms.CharField(
        max_length=200,
        label="Nome do Sacado",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    sacado_cpf_cnpj = forms.CharField(
        max_length=18,
        label="CPF/CNPJ do Sacado",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "000.000.000-00"
        })
    )
    
    valor_nominal = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        label="Valor Nominal",
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01"
        })
    )
    
    valor_aquisicao = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        label="Valor de Aquisição",
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01"
        })
    )
    
    data_vencimento = forms.DateField(
        label="Data de Vencimento",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )


# Formset para múltiplos títulos
TituloFormSet = formset_factory(TituloForm, extra=1, can_delete=True)


class EventoTituloForm(forms.ModelForm):
    """Form para criar eventos em títulos"""
    
    class Meta:
        model = EventoTitulo
        fields = ['tipo_evento', 'data_evento', 'valor_evento', 'descricao', 'documento_referencia']
        widgets = {
            'tipo_evento': forms.Select(attrs={'class': 'form-select'}),
            'data_evento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_evento': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'documento_referencia': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ============================================
# FORMS: APLICAÇÃO
# ============================================

class AplicacaoForm(forms.ModelForm):
    """Form simples para aplicações em ativos"""
    
    class Meta:
        model = Aplicacao
        fields = ['fundo', 'tipo_aplicacao', 'descricao', 'valor', 'data_aplicacao']
        widgets = {
            'fundo': forms.Select(attrs={'class': 'form-select'}),
            'tipo_aplicacao': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Tesouro IPCA+ 2035'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'data_aplicacao': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fundo'].queryset = Fundo.objects.filter(ativo=True)
