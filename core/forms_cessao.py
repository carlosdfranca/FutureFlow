from django import forms
from decimal import Decimal
from fundos.models import Fundo

# =====================================================
# FORM — OPERAÇÃO DE CESSÃO (dados gerais)
# =====================================================

class CessaoOperacaoForm(forms.Form):

    xml_file = forms.FileField(
        label="XML da NF-e",
        required=False,
        widget=forms.FileInput(attrs={
            "class": "form-control"
        })
    )

    fundo = forms.ModelChoiceField(
        queryset=Fundo.objects.filter(ativo=True),
        label="Fundo FIDC",
        required=True,
        widget=forms.Select(attrs={
            "class": "form-select"
        })
    )

    data_contrato = forms.DateField(
        label="Data do Contrato",
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )

    preco_aquisicao = forms.DecimalField(
        label="Preço de Aquisição",
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "0,00",
            "step": "0.01"
        })
    )

    banco = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nome do banco"
        })
    )

    agencia = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "0000"
        })
    )

    conta = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "00000-0"
        })
    )

    cessionario_nome = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            "class": "form-control"
        })
    )

    cessionario_doc = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "CNPJ"
        })
    )


# =====================================================
# FORM — LINHA DE TÍTULO (editável)
# =====================================================

class TituloCessaoForm(forms.Form):

    numero = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    sacado_nome = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    sacado_doc = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    valor = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01"
        })
    )

    vencimento = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )

    tipo = forms.CharField(
        max_length=50,
        initial="Duplicata",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

# =====================================================
# FORMSET — MÚLTIPLOS TÍTULOS
# =====================================================
TituloCessaoFormSet = forms.formset_factory(
    TituloCessaoForm,
    extra=0,
    can_delete=False
)


class CessaoForm(forms.Form):

    data_aquisicao = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )

    preco_aquisicao = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.01"
        })
    )

    banco_aquisicao = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    agencia_aquisicao = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    conta_aquisicao = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    banco_fundo = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    agencia_fundo = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    conta_fundo = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    data_contrato = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control"
        })
    )

    # =========================================
    # EMITENTE / CEDENTE
    # =========================================
    
    emitente_razao_social = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    emitente_cnpj = forms.CharField(
        max_length=18,  # Com formatação XX.XXX.XXX/XXXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XX.XXX.XXX/XXXX-XX"
        })
    )
    
    emitente_representante = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    emitente_cpf = forms.CharField(
        max_length=14,  # Com formatação XXX.XXX.XXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XXX.XXX.XXX-XX"
        })
    )
    
    emitente_email = forms.EmailField(
        max_length=200,
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "exemplo@email.com"
        })
    )
    
    emitente_cargo = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    emitente_endereco = forms.CharField(
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    # =========================================
    # CESSIONÁRIO / CREDOR
    # =========================================
    
    cessionario_razao_social = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    cessionario_cnpj = forms.CharField(
        max_length=18,  # Com formatação XX.XXX.XXX/XXXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XX.XXX.XXX/XXXX-XX"
        })
    )
    
    cessionario_representante = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    cessionario_cpf = forms.CharField(
        max_length=14,  # Com formatação XXX.XXX.XXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XXX.XXX.XXX-XX"
        })
    )
    
    cessionario_email = forms.EmailField(
        max_length=200,
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "exemplo@email.com"
        })
    )
    
    cessionario_cargo = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    cessionario_endereco = forms.CharField(
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    # =========================================
    # TESTEMUNHAS
    # =========================================
    
    testemunha1_nome = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    testemunha1_cpf = forms.CharField(
        max_length=14,  # Com formatação XXX.XXX.XXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XXX.XXX.XXX-XX"
        })
    )
    
    testemunha2_nome = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    testemunha2_cpf = forms.CharField(
        max_length=14,  # Com formatação XXX.XXX.XXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XXX.XXX.XXX-XX"
        })
    )

    # =========================================
    # SACADO
    # =========================================
    
    sacado_razao_social = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    sacado_cnpj = forms.CharField(
        max_length=18,  # Com formatação XX.XXX.XXX/XXXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XX.XXX.XXX/XXXX-XX"
        })
    )
    
    sacado_representante = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    sacado_cpf = forms.CharField(
        max_length=14,  # Com formatação XXX.XXX.XXX-XX
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "XXX.XXX.XXX-XX"
        })
    )
    
    sacado_email = forms.EmailField(
        max_length=200,
        required=False,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "exemplo@email.com"
        })
    )
    
    sacado_cargo = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    sacado_endereco = forms.CharField(
        max_length=300,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
