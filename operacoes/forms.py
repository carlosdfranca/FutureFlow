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
    
    sacado_endereco = forms.CharField(
        max_length=200,
        required=False,
        label="Endereço do Sacado",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Logradouro, número"
        })
    )
    
    sacado_cep = forms.CharField(
        max_length=8,
        required=False,
        label="CEP do Sacado",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00000000"
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
    
    chave_nfe = forms.CharField(
        max_length=44,
        required=False,
        label="Chave NF-e",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "44 dígitos"
        })
    )


# Formset para múltiplos títulos
TituloFormSet = formset_factory(TituloForm, extra=1, can_delete=True)


class EventoTituloForm(forms.ModelForm):
    """
    Form para registrar eventos de saída/retorno de um título (liquidação
    total, liquidação parcial, baixa e reativação). Os demais tipos de
    evento (aquisição, prorrogação, etc.) são criados pelo próprio fluxo
    de negócio, não por este formulário.
    """

    TIPOS_LIQUIDACAO = [
        TipoEventoTitulo.LIQUIDACAO_TOTAL,
        TipoEventoTitulo.LIQUIDACAO_PARCIAL,
        TipoEventoTitulo.BAIXA,
        TipoEventoTitulo.REATIVACAO,
    ]

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

    def __init__(self, *args, titulo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.titulo = titulo
        self.fields['tipo_evento'].choices = [
            (tipo.value, tipo.label) for tipo in self.TIPOS_LIQUIDACAO
        ]
        self.fields['valor_evento'].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo_evento = cleaned_data.get('tipo_evento')
        valor_evento = cleaned_data.get('valor_evento')

        if tipo_evento == TipoEventoTitulo.LIQUIDACAO_PARCIAL:
            if not valor_evento:
                self.add_error('valor_evento', 'Informe o valor liquidado para liquidação parcial.')
            elif self.titulo is not None and valor_evento > self.titulo.saldo_devedor:
                self.add_error(
                    'valor_evento',
                    f'Valor não pode exceder o saldo devedor (R$ {self.titulo.saldo_devedor}).'
                )

        return cleaned_data


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


class LiquidarAplicacaoForm(forms.Form):
    """Form para registrar a liquidação/resgate de uma aplicação"""

    data_liquidacao = forms.DateField(
        label='Data de Liquidação',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    valor_resgate = forms.DecimalField(
        label='Valor de Resgate',
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )


# ============================================
# FORMS: CNAB
# ============================================

class CnabParametrosForm(forms.Form):
    dtl = forms.DateField(
        label='Data de Liquidação (DTL)',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    cdo = forms.CharField(
        label='Código Originador (CDO)',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 01'})
    )
    ocorrencia = forms.CharField(
        label='Ocorrência',
        max_length=2,
        initial='01',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '01'})
    )
