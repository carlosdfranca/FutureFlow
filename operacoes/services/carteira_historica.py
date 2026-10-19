"""
operacoes/services/carteira_historica.py

Reconstrução do estado da carteira (Titulo/Aplicacao) numa data de
referência no passado, a partir do histórico de eventos -- não do estado
atual denormalizado (Titulo.ativo/saldo_devedor, Aplicacao.status).

Motivação: telas como a Lâmina de Acompanhamento (fundos/services/lamina.py)
precisam mostrar a carteira "como estava" na competência de um informe, não
"como está agora". Antes desta reconstrução, gerar a lâmina de uma
competência passada produzia o MESMO resultado que a competência mais
recente, porque tudo lia só o estado atual.

Titulo.ativo/saldo_devedor são campos desnormalizados, mutados como efeito
colateral de cada EventoTitulo (ver operacoes/services/cessao.py::
criar_evento_titulo). Para saber o estado numa data D é preciso "reproduzir"
(replay) os eventos até D em ordem cronológica -- não dá pra fazer com um
filtro simples, porque AJUSTE_VALOR sobrescreve o saldo enquanto
LIQUIDACAO_PARCIAL subtrai dele.

Aplicacao não tem event-sourcing, mas seu ciclo de vida (2 datas + status
binário, sem resgate parcial) é simples o bastante pra um filtro de data
já ser exato -- não precisa de replay.
"""
from calendar import monthrange
from decimal import Decimal

from django.db.models import Q

from ..models import Aplicacao, Titulo, TipoEventoTitulo


def fim_do_mes(data):
    """Último dia do mês de `data`. É essa a data de corte usada pra
    reconstrução: informes CVM reportam a posição de FECHAMENTO do mês,
    mas InformeMensal.competencia é sempre gravado como o 1º dia do mês
    (models.py). Cortar no dia 1º deixaria escapar eventos do resto do mês
    (ex.: uma liquidação no dia 30 ainda apareceria na lâmina daquele mês)."""
    ultimo_dia = monthrange(data.year, data.month)[1]
    return data.replace(day=ultimo_dia)


def _replay_titulo(titulo, eventos_ordenados):
    """Reconstrói (ativo, saldo_devedor) de um título a partir de uma lista
    de eventos JÁ FILTRADA (data_evento <= data de corte) e ordenada
    cronologicamente. Não decide sozinho o caso "sem evento nenhum" --
    isso é responsabilidade de quem chama (ver titulos_ativos_em), porque
    "sem evento até a data de corte" (o título ainda não existia) e "sem
    evento em toda a vida do título" (dado incompleto) são coisas
    diferentes e exigem tratamentos opostos.

    Efeitos por tipo de evento (espelha operacoes/services/cessao.py::
    criar_evento_titulo):
    - AQUISICAO: saldo = titulo.valor_nominal. IMPORTANTE: não usar
      evento.valor_evento aqui -- esse campo guarda titulo.valor_aquisicao
      (valor presente, o último passo da cascata), que é DIFERENTE do
      valor_nominal quando a operação tem taxa_desconto > 0. O saldo_devedor
      real do título nasce do valor_nominal.
      Nota: valor_nominal é o valor da duplicata JÁ LÍQUIDO DE IOF (o
      primeiro passo da cascata), não o valor bruto do vDup da NF-e -- é o
      que o sacado paga e o que sai no CNAB pos. 127-139. Ver
      operacoes/services/cessao.py.
    - LIQUIDACAO_PARCIAL: saldo -= evento.valor_evento
    - LIQUIDACAO_TOTAL: saldo = 0; inativo
    - BAIXA: inativo (saldo mantido)
    - REATIVACAO: ativo (saldo mantido)
    - AJUSTE_VALOR: saldo = evento.valor_evento (sobrescreve, não soma)
    - PRORROGACAO / SUBSTITUICAO / PROTESTO: sem efeito no saldo/ativo hoje
      (também não têm efeito em criar_evento_titulo)
    """
    ativo = False
    saldo = Decimal('0')

    for evento in eventos_ordenados:
        tipo = evento.tipo_evento
        if tipo == TipoEventoTitulo.AQUISICAO:
            ativo = True
            saldo = titulo.valor_nominal
        elif tipo == TipoEventoTitulo.LIQUIDACAO_PARCIAL and evento.valor_evento:
            saldo -= evento.valor_evento
        elif tipo == TipoEventoTitulo.LIQUIDACAO_TOTAL:
            saldo = Decimal('0')
            ativo = False
        elif tipo == TipoEventoTitulo.BAIXA:
            ativo = False
        elif tipo == TipoEventoTitulo.REATIVACAO:
            ativo = True
        elif tipo == TipoEventoTitulo.AJUSTE_VALOR and evento.valor_evento:
            saldo = evento.valor_evento
        # PRORROGACAO, SUBSTITUICAO, PROTESTO: sem efeito de estado

    return ativo, saldo


def titulos_ativos_em(fundo, data_referencia):
    """Lista de dicts {'titulo': Titulo, 'saldo_devedor': Decimal} para os
    títulos do fundo que estavam ativos (saldo > 0) em `data_referencia`,
    reconstruído via replay de EventoTitulo -- não é um filtro simples."""
    titulos = Titulo.objects.filter(fundo=fundo).prefetch_related('eventos')
    resultado = []
    for titulo in titulos:
        todos_eventos = list(titulo.eventos.all())

        if not todos_eventos:
            # Rede de segurança: hoje todo Titulo tem um evento de
            # AQUISICAO (verificado -- processar_cessao e o comando de
            # migração legado migrar_recebiveis.py sempre criam os dois
            # juntos), mas se algum título ficar sem nenhum evento em
            # TODA a sua vida (não só antes da data de corte), cair em
            # "não existia" seria pior que o comportamento anterior a
            # esta mudança. Fallback: reporta o estado atual do título.
            if titulo.ativo and titulo.saldo_devedor > 0:
                resultado.append({'titulo': titulo, 'saldo_devedor': titulo.saldo_devedor})
            continue

        eventos_ate_data = sorted(
            (e for e in todos_eventos if e.data_evento <= data_referencia),
            key=lambda e: (e.data_evento, e.criado_em),
        )
        ativo, saldo = _replay_titulo(titulo, eventos_ate_data)
        if ativo and saldo > 0:
            resultado.append({'titulo': titulo, 'saldo_devedor': saldo})
    return resultado


def aplicacoes_ativas_em(fundo, data_referencia):
    """Aplicações ativas em `data_referencia`. Sem replay -- o ciclo de
    vida de Aplicacao não modela resgate parcial, um filtro por data já é
    exato: estava ativa se já tinha sido aplicada e (ainda não foi
    liquidada, ou só foi liquidada depois da data de referência)."""
    return Aplicacao.objects.filter(
        fundo=fundo, data_aplicacao__lte=data_referencia,
    ).filter(Q(data_liquidacao__isnull=True) | Q(data_liquidacao__gt=data_referencia))
