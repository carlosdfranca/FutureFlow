from django import template

register = template.Library()

# (ícone Bootstrap Icons, variante de cor) por extensão — cobre os formatos de
# documento mais comuns para fundos: laudos e atas (PDF/Word), planilhas
# (Excel/CSV), contratos digitalizados (imagem), páginas/dados (HTML/XML/JSON)
# e pacotes (ZIP).
_TIPOS_ARQUIVO = {
    'pdf':  ('bi-filetype-pdf',  'pdf'),
    'doc':  ('bi-filetype-doc',  'word'),
    'docx': ('bi-filetype-docx', 'word'),
    'xls':  ('bi-filetype-xls',  'excel'),
    'xlsx': ('bi-filetype-xlsx', 'excel'),
    'csv':  ('bi-filetype-csv',  'excel'),
    'ppt':  ('bi-filetype-ppt',  'ppt'),
    'pptx': ('bi-filetype-pptx', 'ppt'),
    'txt':  ('bi-filetype-txt',  'text'),
    'md':   ('bi-filetype-md',   'text'),
    'html': ('bi-filetype-html', 'code'),
    'htm':  ('bi-filetype-html', 'code'),
    'xml':  ('bi-filetype-xml',  'code'),
    'json': ('bi-filetype-json', 'code'),
    'css':  ('bi-filetype-css',  'code'),
    'js':   ('bi-filetype-js',   'code'),
    'png':  ('bi-filetype-png',  'image'),
    'jpg':  ('bi-filetype-jpg',  'image'),
    'jpeg': ('bi-filetype-jpg',  'image'),
    'gif':  ('bi-filetype-gif',  'image'),
    'svg':  ('bi-filetype-svg',  'image'),
    'zip':  ('bi-filetype-zip',  'archive'),
    'rar':  ('bi-filetype-zip',  'archive'),
    '7z':   ('bi-filetype-zip',  'archive'),
}
_PADRAO = ('bi-file-earmark', 'default')


def _extensao(nome_arquivo):
    if not nome_arquivo or '.' not in nome_arquivo:
        return ''
    return nome_arquivo.rsplit('.', 1)[-1].lower()


@register.filter(name='icone_arquivo')
def icone_arquivo(nome_arquivo):
    """Retorna a classe do ícone Bootstrap Icons correspondente à extensão do arquivo."""
    icone, _ = _TIPOS_ARQUIVO.get(_extensao(nome_arquivo), _PADRAO)
    return icone


@register.filter(name='cor_arquivo')
def cor_arquivo(nome_arquivo):
    """Retorna a variante de cor (usada como modificador .file-icon--*) para a extensão do arquivo."""
    _, cor = _TIPOS_ARQUIVO.get(_extensao(nome_arquivo), _PADRAO)
    return cor
