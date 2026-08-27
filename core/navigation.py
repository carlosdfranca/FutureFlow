"""
Mapa central de "página pai" usado pelo botão de Voltar padronizado
(ver `core.templatetags.ui.back_button`).

Cada entrada mapeia a URL atual (`app_name:url_name`, ou apenas `url_name`
quando o app não tem namespace, como `core` e `usuarios`) para:

    (nome_da_rota_pai, kwargs_repassados, rótulo)

`kwargs_repassados` são os nomes dos kwargs capturados pela URL *atual*
(via `request.resolver_match.kwargs`) que devem ser reencaminhados para a
rota pai ao montar o `reverse()`. `rótulo` é usado apenas no title/aria-label
do botão (não é exibido como texto).

Páginas de topo (sem pai — ex.: `fundos:listar_fundos`) não precisam de
entrada aqui: `resolver_pagina_pai` simplesmente devolve `None` e o
componente não renderiza nenhum botão.
"""
from django.urls import NoReverseMatch, reverse

PARENT_PAGES = {
    # fundos
    "fundos:novo_fundo": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:editar_fundo": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:carteira_fundo": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:dashboard_fundo": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:listar_informes": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:importar_informe": ("fundos:listar_informes", ("fundo_id",), "Informes"),
    "fundos:detalhe_informe": ("fundos:listar_informes", ("fundo_id",), "Informes"),
    "fundos:nova_aplicacao": ("fundos:listar_fundos", (), "Fundos"),
    "fundos:novo_resgate": ("fundos:listar_fundos", (), "Fundos"),
    # operacoes
    "operacoes:listar_cessoes": ("operacoes:painel_fundos", (), "Operações"),
    "operacoes:workflow_cessao": ("operacoes:listar_cessoes", (), "Cessões"),
    "operacoes:detalhe_cessao": ("operacoes:listar_cessoes", (), "Cessões"),
    "operacoes:cnab_parametros": ("operacoes:detalhe_cessao", ("pk",), "Cessão"),
    "operacoes:listar_titulos": ("operacoes:painel_fundos", (), "Operações"),
    "operacoes:detalhe_titulo": ("operacoes:listar_titulos", (), "Títulos"),
    "operacoes:listar_aplicacoes": ("operacoes:painel_fundos", (), "Operações"),
    "operacoes:nova_aplicacao": ("operacoes:listar_aplicacoes", (), "Aplicações"),
    # documentos
    "documentos:documentos_fundo": ("documentos:index", (), "Documentos"),
    "documentos:documentos_categoria": (
        "documentos:documentos_fundo",
        ("fundo_id",),
        "Documentos do Fundo",
    ),
}


def resolver_pagina_pai(request):
    """
    Retorna (url, rótulo) da página pai da rota atual, ou (None, None) se a
    rota não estiver mapeada ou não puder ser resolvida.
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return None, None

    if resolver_match.app_name:
        chave = f"{resolver_match.app_name}:{resolver_match.url_name}"
    else:
        chave = resolver_match.url_name

    entrada = PARENT_PAGES.get(chave)
    if entrada is None:
        return None, None

    rota_pai, kwargs_repassados, rotulo = entrada
    kwargs = {
        nome: resolver_match.kwargs[nome]
        for nome in kwargs_repassados
        if nome in resolver_match.kwargs
    }

    try:
        return reverse(rota_pai, kwargs=kwargs), rotulo
    except NoReverseMatch:
        return None, None
