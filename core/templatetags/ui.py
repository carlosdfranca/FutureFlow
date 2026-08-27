from urllib.parse import urlencode

from django import template

from core.navigation import resolver_pagina_pai

register = template.Library()


@register.inclusion_tag("partials/back_button.html", takes_context=True)
def back_button(context, url=None, label=None, **query):
    """
    Botão de "Voltar" padronizado (quadrado com seta, `.btn-back`).

    Sem argumentos, resolve o destino pelo mapa central em
    `core.navigation.PARENT_PAGES`, usando a rota atual (`request.resolver_match`).

    Uso:
        {% back_button %}
        {% back_button url=minha_url %}                  {# override total #}
        {% back_button fundo=operacao.fundo_id %}         {# some parent + ?fundo=... #}
        {% back_button label="Cessões" %}                 {# sobrescreve o rótulo #}

    Pares em `**query` com valor vazio/None são ignorados (não viram query
    string) — permite usar `{% back_button fundo=fundo_id %}` mesmo quando
    `fundo_id` pode estar vazio.
    """
    request = context.get("request")
    back_url = url
    back_label = label

    if back_url is None and request is not None:
        back_url, rotulo_padrao = resolver_pagina_pai(request)
        if back_label is None:
            back_label = rotulo_padrao

    if back_url:
        params = {chave: valor for chave, valor in query.items() if valor}
        if params:
            back_url = f"{back_url}?{urlencode(params)}"

    return {"back_url": back_url, "back_label": back_label}
