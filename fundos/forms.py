from django import forms
from .models import Fundo, TipoFundo

class FundoForm(forms.ModelForm):
    # Declarado explicitamente para que max_length=18 (formatado) seja renderizado
    # no HTML. clean_cnpj() extrai apenas os dígitos antes de salvar.
    cnpj = forms.CharField(
        max_length=18,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': '18',
            'placeholder': '00.000.000/0000-00',
        }),
        label='CNPJ',
    )

    class Meta:
        model = Fundo
        fields = [
            'razao_social',
            'nome_comercial',
            'cnpj',
            'codigo_anbima',
            'tipo_fundo',
            'data_constituicao',
            'tipo_cotizacao',
            'prazo_liquidacao',
            'horario_corte',
            'taxa_administracao',
            'taxa_gestao',
        ]
        widgets = {
            'razao_social':      forms.TextInput(attrs={'class': 'form-control'}),
            'nome_comercial':    forms.TextInput(attrs={'class': 'form-control'}),
            # cnpj é declarado como field explícito acima — widget definido lá
            'codigo_anbima':     forms.TextInput(attrs={'class': 'form-control', 'maxlength': '6'}),
            'tipo_fundo':        forms.Select(attrs={'class': 'form-select'}),
            'data_constituicao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'tipo_cotizacao':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'D+0 ou D+1'}),
            'prazo_liquidacao':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'horario_corte':     forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'taxa_administracao': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001', 'min': '0'}),
            'taxa_gestao':       forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001', 'min': '0'}),
        }
        labels = {
            'razao_social':      'Razão Social',
            'nome_comercial':    'Nome Comercial',
            'cnpj':              'CNPJ (somente números)',
            'codigo_anbima':     'Código ANBIMA',
            'tipo_fundo':        'Tipo de Fundo',
            'data_constituicao': 'Data de Constituição',
            'tipo_cotizacao':    'Tipo de Cotização',
            'prazo_liquidacao':  'Prazo de Liquidação (dias úteis)',
            'horario_corte':     'Horário de Corte',
            'taxa_administracao': 'Taxa de Administração (% a.a.)',
            'taxa_gestao':       'Taxa de Gestão (% a.a.)',
        }

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj', '')
        digits = ''.join(c for c in cnpj if c.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve conter exatamente 14 dígitos.')
        return digits


class InformeUploadForm(forms.Form):
    xml_file = forms.FileField(
        label='Arquivo XML do Informe Mensal',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.xml',
        }),
        help_text='Selecione o arquivo .xml gerado pela administradora (máx. 5 MB).',
    )

    def clean_xml_file(self):
        f = self.cleaned_data.get('xml_file')
        if not f:
            return f
        if not f.name.lower().endswith('.xml'):
            raise forms.ValidationError('O arquivo deve ter extensão .xml.')
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError('O arquivo não pode ultrapassar 5 MB.')
        return f
