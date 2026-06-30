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

    # Campos de % e R$ declarados como CharField para aceitar formato BR (vírgula decimal).
    # clean_* converte para Decimal antes de salvar. O JS do template formata a exibição.
    taxa_administracao = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
        }),
        label='Taxa de Administração (% a.a.)',
    )
    taxa_gestao = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
        }),
        label='Taxa de Gestão (% a.a.)',
    )
    taxa_performance = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0,00',
            'inputmode': 'decimal',
        }),
        label='Taxa de Performance (% a.a.)',
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
            'administrador',
            'gestor',
            'condicoes_resgate',
            'auditoria',
            'aporte_minimo',
            'data_encerramento_exercicio',
            'taxa_administracao',
            'taxa_gestao',
            'taxa_performance',
        ]
        widgets = {
            'razao_social':      forms.TextInput(attrs={'class': 'form-control'}),
            'nome_comercial':    forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_anbima':     forms.TextInput(attrs={'class': 'form-control', 'maxlength': '6'}),
            'tipo_fundo':        forms.Select(attrs={'class': 'form-select'}),
            'data_constituicao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'tipo_cotizacao':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'D+0 ou D+1'}),
            'prazo_liquidacao':  forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'horario_corte':     forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'administrador':     forms.TextInput(attrs={'class': 'form-control'}),
            'gestor':            forms.TextInput(attrs={'class': 'form-control'}),
            'condicoes_resgate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: D+30 após solicitação'}),
            'auditoria':         forms.TextInput(attrs={'class': 'form-control'}),
            'data_encerramento_exercicio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 31/12'}),
            # taxa_administracao, taxa_gestao, taxa_performance, aporte_minimo: declarados acima
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
            'administrador':     'Administrador',
            'gestor':            'Gestor',
            'condicoes_resgate': 'Condições de Resgate',
            'auditoria':         'Auditoria',
            'data_encerramento_exercicio': 'Encerramento do Exercício Social',
        }

    def _parse_br_decimal(self, value):
        """Converte string BR (vírgula decimal, ponto milhar) para Decimal."""
        if not value or not value.strip():
            return None
        v = value.strip()
        if ',' in v and '.' in v:
            # "50.000,25" → remove pontos de milhar, troca vírgula por ponto
            v = v.replace('.', '').replace(',', '.')
        elif ',' in v:
            # "1,5000" → só vírgula decimal
            v = v.replace(',', '.')
        # else: já está em formato ponto decimal ("1.5000")
        try:
            return Decimal(v)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Valor inválido. Use formato numérico (ex: 1,50).')

    def clean_codigo_anbima(self):
        value = self.cleaned_data.get('codigo_anbima', '')
        # CharField unique+null=True: vazio deve ser NULL no DB, não "" (evita UniqueConstraint)
        return value if value else None

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get('cnpj', '')
        digits = ''.join(c for c in cnpj if c.isdigit())
        if len(digits) != 14:
            raise forms.ValidationError('CNPJ deve conter exatamente 14 dígitos.')
        return digits

    def clean_taxa_administracao(self):
        return self._parse_br_decimal(self.cleaned_data.get('taxa_administracao'))

    def clean_taxa_gestao(self):
        return self._parse_br_decimal(self.cleaned_data.get('taxa_gestao'))

    def clean_taxa_performance(self):
        return self._parse_br_decimal(self.cleaned_data.get('taxa_performance'))

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
