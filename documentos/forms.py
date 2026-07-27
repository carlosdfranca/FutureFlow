from django import forms

EXTENSOES_PERMITIDAS = (
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.ppt', '.pptx',
    '.txt', '.md', '.html', '.htm', '.xml', '.json',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.zip',
)
TAMANHO_MAXIMO = 25 * 1024 * 1024  # 25 MB


class DocumentoUploadForm(forms.Form):
    arquivo = forms.FileField(
        label='Arquivo',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        help_text='PDF, Word, Excel, CSV, PowerPoint, HTML, imagem ou ZIP — máx. 25 MB.',
    )
    nome = forms.CharField(
        label='Nome de exibição',
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional — usa o nome do arquivo se vazio'}),
    )
    descricao = forms.CharField(
        label='Descrição',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observações (opcional)'}),
    )

    def clean_arquivo(self):
        f = self.cleaned_data.get('arquivo')
        if not f:
            return f
        if not f.name.lower().endswith(EXTENSOES_PERMITIDAS):
            raise forms.ValidationError(
                'Extensão não permitida. Use PDF, Word, Excel, CSV, PowerPoint, HTML, imagem ou ZIP.'
            )
        if f.size > TAMANHO_MAXIMO:
            raise forms.ValidationError('O arquivo não pode ultrapassar 25 MB.')
        return f
