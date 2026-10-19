"""
Service layer para a remessa CNAB de baixa: título liquidado/baixado -> uma
linha de detalhe com o código de movimento correto (pos. 109-110), agrupadas
num arquivo por fundo e persistidas em RemessaCnab para rastreio/re-download.

Ver docs/plano de implementação: `Documentação CNAB.pdf` (pág. 2, "Tipos de
Movimento") é a fonte da tabela MOVIMENTO_CNAB abaixo.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from ..models import RemessaCnab, RemessaCnabTitulo, TipoEventoTitulo, TipoRemessaCnab
from ..utils.cnab_service import gerar_cnab_stream
from .cnab import montar_registro_base

# Tradução TipoEventoTitulo -> código de movimento do CNAB (pos. 109-110),
# conforme a tabela "Tipos de Movimento" da Documentação CNAB da FIDD.
#
# NÃO é o valor do enum: `TipoEventoTitulo.LIQUIDACAO_TOTAL=6`,
# `PRORROGACAO=10` e `AJUSTE_VALOR=31` não existem na tabela da FIDD (que usa
# 02, 20 e 46 para esses movimentos) — só BAIXA=2, LIQUIDACAO_PARCIAL=14 e
# REATIVACAO=99 batem com o código de movimento real por coincidência. Por
# isso este mapa é explícito e nunca `str(tipo_evento)`.
MOVIMENTO_CNAB = {
    TipoEventoTitulo.AQUISICAO: '01',
    TipoEventoTitulo.BAIXA: '02',
    TipoEventoTitulo.LIQUIDACAO_TOTAL: '02',  # doc FIDD: "baixa total"
    TipoEventoTitulo.LIQUIDACAO_PARCIAL: '14',
    TipoEventoTitulo.REATIVACAO: '99',
}

# Eventos que tornam um título elegível para uma remessa CNAB de baixa. Não
# dá para usar `Titulo.ativo` como proxy: uma liquidação parcial mantém o
# título ativo (só reduz o saldo), e uma baixa/liquidação total o inativa —
# os dois têm que poder gerar uma linha de baixa no CNAB.
EVENTOS_DE_BAIXA = (
    TipoEventoTitulo.BAIXA,
    TipoEventoTitulo.LIQUIDACAO_TOTAL,
    TipoEventoTitulo.LIQUIDACAO_PARCIAL,
)


def evento_de_baixa_mais_recente(titulo):
    """Último EventoTitulo de baixa/liquidação do título, ou None.

    `EventoTitulo.Meta.ordering = ['-data_evento', '-criado_em']`, então
    `.first()` já devolve o mais recente.
    """
    return titulo.eventos.filter(tipo_evento__in=EVENTOS_DE_BAIXA).first()


def titulos_elegiveis(queryset):
    """Filtra um queryset de Titulo para os que têm ao menos um evento de
    baixa/liquidação (total ou parcial) — os candidatos a entrar numa
    remessa CNAB de baixa."""
    return queryset.filter(eventos__tipo_evento__in=EVENTOS_DE_BAIXA).distinct()


def valor_pago_pendente(titulo) -> Decimal:
    """
    Soma dos eventos de liquidação (parcial + total) do título, menos o que
    já foi reportado em remessas de baixa anteriores — evita que uma
    liquidação já enviada seja subtraída de novo pelo banco se o título
    entrar numa remessa de baixa outra vez (reenvio/correção).
    """
    liquidado = titulo.eventos.filter(
        tipo_evento__in=[TipoEventoTitulo.LIQUIDACAO_PARCIAL, TipoEventoTitulo.LIQUIDACAO_TOTAL]
    ).aggregate(total=Sum('valor_evento'))['total'] or Decimal('0')

    ja_enviado = RemessaCnabTitulo.objects.filter(titulo=titulo).aggregate(
        total=Sum('valor_pago')
    )['total'] or Decimal('0')

    pendente = liquidado - ja_enviado
    return pendente if pendente > 0 else Decimal('0')


def movimento_para_titulo(titulo) -> str:
    """
    Código de movimento CNAB (pos. 109-110) para o evento de baixa/liquidação
    mais recente do título.

    Raises:
        ValueError: título sem evento de baixa/liquidação, ou tipo de evento
            sem código de movimento mapeado.
    """
    evento = evento_de_baixa_mais_recente(titulo)
    if evento is None:
        raise ValueError(
            f"Título {titulo.numero_titulo} não tem evento de baixa/liquidação registrado."
        )
    movimento = MOVIMENTO_CNAB.get(evento.tipo_evento)
    if movimento is None:
        raise ValueError(
            f"Título {titulo.numero_titulo}: evento "
            f"'{evento.get_tipo_evento_display()}' não tem código de movimento CNAB mapeado."
        )
    return movimento


@transaction.atomic
def gerar_remessa_baixa(titulos, dtl, usuario) -> tuple:
    """
    Gera e persiste uma remessa CNAB de baixa para os títulos informados.

    Args:
        titulos: iterável de Titulo (todos precisam ser do mesmo fundo — o
            header do CNAB carrega um único código originador)
        dtl: date, data de liquidação
        usuario: User que está gerando a remessa

    Returns:
        (RemessaCnab, str) — a remessa persistida e o conteúdo do arquivo

    Raises:
        ValueError: lista vazia, títulos de fundos diferentes, fundo sem
            CDO, ou título sem evento de baixa/liquidação
    """
    titulos = list(titulos)
    if not titulos:
        raise ValueError("Nenhum título selecionado.")

    fundos = {t.fundo_id for t in titulos}
    if len(fundos) > 1:
        raise ValueError(
            "Todos os títulos precisam ser do mesmo fundo — o header do CNAB "
            "carrega um único código originador (CDO)."
        )

    fundo = titulos[0].fundo
    if not fundo.codigo_originador_cnab:
        raise ValueError(
            f"O fundo {fundo.razao_social} não tem Código Originador (CDO) "
            "configurado. Cadastre-o na tela do fundo antes de gerar o CNAB."
        )

    base_data = []
    linhas_remessa = []  # (titulo, movimento, valor_pago), persistidas após o transaction.atomic
    for titulo in titulos:
        movimento = movimento_para_titulo(titulo)
        valor_pago = valor_pago_pendente(titulo)
        base_data.append(
            montar_registro_base(
                titulo, titulo.operacao_cessao, valor_pago=valor_pago, ocorrencia=movimento
            )
        )
        linhas_remessa.append((titulo, movimento, valor_pago))

    menu_data = {
        "DTL": dtl.strftime('%d/%m/%Y'),
        "CDO": fundo.codigo_originador_cnab,
        # Fallback do gerador quando uma linha não traz OCORRENCIA própria —
        # não deve acontecer aqui, já que toda linha acima recebe `ocorrencia`.
        "OCORRENCIA": fundo.ocorrencia_cnab_padrao or '01',
    }

    buffer = gerar_cnab_stream(base_data, menu_data)
    conteudo = buffer.read()

    nome_arquivo = f"CNAB_BAIXA_{fundo.cnpj}_{dtl.strftime('%Y%m%d')}.txt"
    remessa = RemessaCnab.objects.create(
        fundo=fundo,
        tipo=TipoRemessaCnab.BAIXA,
        data_liquidacao=dtl,
        nome_arquivo=nome_arquivo,
        conteudo=conteudo,
        quantidade_titulos=len(titulos),
        gerado_por=usuario,
    )
    RemessaCnabTitulo.objects.bulk_create([
        RemessaCnabTitulo(remessa=remessa, titulo=titulo, codigo_movimento=movimento, valor_pago=valor_pago)
        for titulo, movimento, valor_pago in linhas_remessa
    ])

    return remessa, conteudo
