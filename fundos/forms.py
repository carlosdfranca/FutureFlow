from django import forms
from decimal import Decimal, InvalidOperation
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

    aporte_minimo = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
        }),
        label='Aporte Mínimo (R$)',
    )

    limite_direitos_creditorios = forms.IntegerField(
        required=True,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100',
            'step': '1',
            'inputmode': 'numeric',
            'placeholder': '0 a 100',
        }),
        label='Limite em Direitos Creditórios (%)',
    )

    limite_liquidez = forms.IntegerField(
        required=True,
        min_value=0,
        max_value=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100',
            'step': '1',
            'inputmode': 'numeric',
            'placeholder': '0 a 100',
        }),
        label='Limite de Liquidez (%)',
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
            'classificacao_investidor',
            'estrutura_fundo',
            'tipo_condominio',
            'tipo_cotizacao',
            'prazo_liquidacao',
            'horario_corte',
            'administrador',
            'gestor',
            'condicoes_resgate',
            'aporte_minimo',
            'data_encerramento_exercicio',
            'limite_concentracao',
            'limite_direitos_creditorios',
            'limite_liquidez',
            'taxa_administracao',
            'taxa_gestao',
            'taxa_performance',
            'taxa_administracao_minima',
            'taxa_gestao_minima',
            'taxa_performance_minima',
        ]
        widgets = {
            'razao_social':      forms.TextInput(attrs={'class': 'form-control'}),
            'nome_comercial':    forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_anbima':     forms.TextInput(attrs={'class': 'form-control', 'maxlength': '6'}),
            'tipo_fundo':        forms.Select(attrs={'class': 'form-select'}),
            'data_constituicao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'classificacao_investidor': forms.Select(attrs={'class': 'form-select'}),
            'estrutura_fundo':   forms.Select(attrs={'class': 'form-select'}),
            'tipo_condominio':   forms.Select(attrs={'class': 'form-select'}),
            'tipo_cotizacao':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'D+0 ou D+1'}),
            'prazo_liquidacao':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'horario_corte':     forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'administrador':     forms.TextInput(attrs={'class': 'form-control'}),
            'gestor':            forms.TextInput(attrs={'class': 'form-control'}),
            'condicoes_resgate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: D+30 após solicitação'}),
            'data_encerramento_exercicio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 31/12'}),
            'limite_concentracao': forms.TextInput(attrs={'class': 'form-control'}),
            'taxa_administracao':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1,50% ou Isento'}),
            'taxa_gestao':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 0,50% ou Isento'}),
            'taxa_performance':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 20% sobre o que exceder o benchmark'}),
            'taxa_administracao_minima': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 0,30%'}),
            'taxa_gestao_minima':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 0,10%'}),
            'taxa_performance_minima':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 10%'}),
        }
        labels = {
            'razao_social':      'Razão Social',
            'nome_comercial':    'Nome Comercial',
            'cnpj':              'CNPJ (somente números)',
            'codigo_anbima':     'Código ANBIMA',
            'tipo_fundo':        'Tipo de Fundo',
            'data_constituicao': 'Data de Constituição',
            'classificacao_investidor': 'Classificação do Investidor',
            'estrutura_fundo':   'Estrutura',
            'tipo_condominio':   'Tipo de Condomínio (FIDC)',
            'tipo_cotizacao':    'Tipo de Cotização',
            'prazo_liquidacao':  'Prazo de Liquidação (dias úteis)',
            'horario_corte':     'Horário de Corte',
            'administrador':     'Administrador',
            'gestor':            'Gestor',
            'condicoes_resgate': 'Prazo de Resgate',
            'data_encerramento_exercicio': 'Encerramento do Exercício Social',
            'limite_concentracao': 'Limite de Concentração',
            'taxa_administracao':  'Taxa de Administração',
            'taxa_gestao':         'Taxa de Gestão',
            'taxa_performance':    'Taxa de Performance',
            'taxa_administracao_minima': 'Taxa Mínima de Administração',
            'taxa_gestao_minima':        'Taxa Mínima de Gestão',
            'taxa_performance_minima':   'Taxa Mínima de Performance',
        }

    def _parse_br_decimal(self, value):
        """Converte string BR (vírgula decimal, ponto milhar) para Decimal."""
        if not value or not value.strip():
            return None
        v = value.strip()
        if ',' in v and '.' in v:
            v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            v = v.replace(',', '.')
        try:
            return Decimal(v)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Valor inválido. Use formato numérico (ex: 1,50).')

    def clean_codigo_anbima(self):
        value = self.cleaned_data.get('codigo_anbima', '')
        return value if value else None

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj', '')
        digits = ''.join(c for c in cnpj if c.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve conter exatamente 14 dígitos.')
        return digits

    def clean_aporte_minimo(self):
        return self._parse_br_decimal(self.cleaned_data.get('aporte_minimo'))


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


class InformeLoteUploadForm(forms.Form):
    zip_file = forms.FileField(
        label='Arquivo ZIP com XMLs dos Informes',
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.zip',
        }),
        help_text='Selecione um arquivo .zip contendo um ou mais XMLs de informe mensal (máx. 50 MB).',
    )

    def clean_zip_file(self):
        f = self.cleaned_data.get('zip_file')
        if not f:
            return f
        if not f.name.lower().endswith('.zip'):
            raise forms.ValidationError('O arquivo deve ter extensão .zip.')
        if f.size > 50 * 1024 * 1024:
            raise forms.ValidationError('O arquivo ZIP não pode ultrapassar 50 MB.')
        return f
