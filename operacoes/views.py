from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.http import HttpResponse
from django.conf import settings
from decimal import Decimal

from .models import OperacaoCessao, Titulo, EventoTitulo, TipoEventoTitulo, Aplicacao
from .forms import CessaoOperacaoForm, TituloFormSet, EventoTituloForm, AplicacaoForm, CnabParametrosForm, LiquidarAplicacaoForm
from .services.cessao import processar_cessao, criar_evento_titulo, calcular_totais_operacao
from .services.aplicacao import liquidar_aplicacao as liquidar_aplicacao_service
from .utils.cnab_service import gerar_cnab_stream
from .utils.cnab_utils import rp, remover_pontos, remover_caracteres_especiais

# Importar serviços existentes do core
from core.services.cessao_xml import parse_nfe_uploaded_file
from core.services.cessao_doc import render_termo_cessao_docx, render_termo_confirmacao_docx


# ============================================
# VIEWS: CESSÃO
# ============================================

def _novo_bloco(index, cessao_form=None, titulos_formset=None, nome_arquivo=""):
    """Um 'bloco' é um par (cessao_form, titulos_formset) com prefixo próprio,
    representando uma futura OperacaoCessao independente. Cada XML importado
    em lote vira um bloco; não há agrupamento entre blocos."""
    return {
        "index": index,
        "nome_arquivo": nome_arquivo,
        "cessao_form": cessao_form or CessaoOperacaoForm(prefix=f"op{index}"),
        "titulos_formset": titulos_formset or TituloFormSet(prefix=f"tit{index}"),
    }


def _titulos_iniciais_from_parsed(parsed):
    return [
        {
            "numero_titulo": t.numero_titulo,
            "sacado_nome": t.sacado_nome,
            "sacado_cpf_cnpj": t.sacado_doc,
            "sacado_endereco": t.sacado_endereco,
            "sacado_cep": t.sacado_cep,
            "valor_nominal": t.valor,
            "valor_aquisicao": t.valor,  # Mesmo valor por padrão
            "data_vencimento": t.vencimento_iso,
            "chave_nfe": t.chave_nfe,
            "data_emissao": t.data_emissao_iso,
        }
        for t in parsed.titulos
    ]


@login_required
def workflow_cessao(request):
    """
    Workflow completo de cessão:
    1. Upload de um ou mais XML (opcional) → parse automático, um bloco de
       revisão por NF-e (cada bloco vira sua própria OperacaoCessao — sem
       agrupar títulos de NF-e diferentes)
    2. Preencher/editar títulos manualmente em cada bloco
    3. Confirmar → salvar todas as operações + títulos + eventos
    4. Gerar documentos (termo cessão, confirmação)
    """
    from datetime import date

    blocos = [_novo_bloco(0)]

    if request.method == "POST":
        acao = request.POST.get("acao")

        # ============================================
        # AÇÃO: IMPORTAR XML (um ou mais arquivos)
        # ============================================
        if acao == "parse_xml":
            xml_files = request.FILES.getlist("xml_file")

            if not xml_files:
                messages.error(request, "Selecione ao menos um arquivo XML.")
                return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos})

            # Preserva fundo/datas já escolhidos na tela (bloco 0), se houver —
            # esses campos não vêm do XML (fundo nunca vem; datas só têm default
            # de hoje), então reimportar não deveria forçar o usuário a escolher
            # tudo de novo. Vazio (primeira vez na página) mantém os defaults.
            fundo_preservado = request.POST.get('op0-fundo') or ''
            data_contrato_preservada = request.POST.get('op0-data_contrato') or date.today()
            data_aquisicao_preservada = request.POST.get('op0-data_aquisicao') or date.today()

            blocos_processados = []
            total_titulos = 0
            erros = 0
            for xml_file in xml_files:
                try:
                    parsed = parse_nfe_uploaded_file(xml_file)
                except Exception as e:
                    erros += 1
                    messages.error(request, f"Erro ao processar '{xml_file.name}': {str(e)}")
                    continue

                titulos_iniciais = _titulos_iniciais_from_parsed(parsed)
                inicial_operacao = {
                    'fundo': fundo_preservado,
                    'cedente_cnpj': parsed.partes.cedente_doc,
                    'cedente_nome': parsed.partes.cedente_nome,
                    'cedente_endereco': getattr(parsed.partes, 'cedente_endereco', ''),
                    'numero_contrato': f"NF-{parsed.partes.numero_nota}" if parsed.partes.numero_nota else "",
                    'data_contrato': data_contrato_preservada,
                    'data_aquisicao': data_aquisicao_preservada,
                }

                idx = len(blocos_processados)
                blocos_processados.append(_novo_bloco(
                    idx,
                    cessao_form=CessaoOperacaoForm(initial=inicial_operacao, prefix=f"op{idx}"),
                    titulos_formset=TituloFormSet(initial=titulos_iniciais, prefix=f"tit{idx}"),
                    nome_arquivo=xml_file.name,
                ))
                total_titulos += len(titulos_iniciais)

            if blocos_processados:
                blocos = blocos_processados
                messages.success(
                    request,
                    f"{len(blocos_processados)} arquivo(s) XML processado(s) com sucesso "
                    f"({total_titulos} título(s) no total)."
                )
            # Se todos os arquivos falharam, mantém o bloco vazio inicial para cadastro manual.

            if erros:
                messages.warning(request, f"{erros} arquivo(s) não puderam ser processados (veja mensagens acima).")

            return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos})

        # ============================================
        # AÇÃO: CONFIRMAR E SALVAR (todos os blocos)
        # ============================================
        elif acao == "confirmar":
            try:
                total_blocos = max(1, int(request.POST.get("total_blocos", "1")))
            except ValueError:
                total_blocos = 1

            blocos_post = []
            algum_invalido = False
            for idx in range(total_blocos):
                cessao_form = CessaoOperacaoForm(request.POST, prefix=f"op{idx}")
                titulos_formset = TituloFormSet(request.POST, prefix=f"tit{idx}")
                if not (cessao_form.is_valid() and titulos_formset.is_valid()):
                    algum_invalido = True
                blocos_post.append(_novo_bloco(idx, cessao_form=cessao_form, titulos_formset=titulos_formset))

            if algum_invalido:
                messages.error(request, "Corrija os erros indicados antes de confirmar.")
                return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos_post})

            # Cada bloco vira, no máximo, uma titulos_validos list; blocos sem
            # nenhum título (ex.: bloco extra deixado em branco) são ignorados.
            blocos_com_titulos = []
            for bloco in blocos_post:
                titulos_validos = [
                    f.cleaned_data for f in bloco["titulos_formset"]
                    if f.cleaned_data and not f.cleaned_data.get('DELETE', False)
                ]
                if titulos_validos:
                    blocos_com_titulos.append((bloco["cessao_form"], titulos_validos))

            if not blocos_com_titulos:
                messages.error(request, "Adicione pelo menos um título.")
                return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos_post})

            operacoes_criadas = []
            erros_criacao = []
            for cessao_form, titulos_validos in blocos_com_titulos:
                # Aviso (não bloqueio) de NF-e já importada anteriormente, em
                # qualquer fundo/operação — checagem contra o banco inteiro.
                chaves_nfe = [t.get('chave_nfe') for t in titulos_validos if t.get('chave_nfe')]
                chaves_duplicadas = set()
                if chaves_nfe:
                    chaves_duplicadas = set(
                        Titulo.objects.filter(chave_nfe__in=chaves_nfe).values_list('chave_nfe', flat=True)
                    )

                try:
                    operacao = processar_cessao(
                        fundo=cessao_form.cleaned_data['fundo'],
                        cedente_dados={
                            'cnpj': _limpar_cnpj(cessao_form.cleaned_data['cedente_cnpj']),
                            'nome': cessao_form.cleaned_data['cedente_nome'],
                            'endereco': cessao_form.cleaned_data.get('cedente_endereco', ''),
                        },
                        titulos_dados=[_titulo_dados_from_form(t) for t in titulos_validos],
                        operacao_dados={
                            'numero_contrato': cessao_form.cleaned_data['numero_contrato'],
                            'data_contrato': cessao_form.cleaned_data['data_contrato'],
                            'data_aquisicao': cessao_form.cleaned_data['data_aquisicao'],
                            'observacoes': cessao_form.cleaned_data.get('observacoes', ''),
                        },
                        usuario=request.user
                    )
                    operacoes_criadas.append((operacao, len(titulos_validos), chaves_duplicadas))
                except Exception as e:
                    erros_criacao.append((cessao_form.cleaned_data.get('numero_contrato', '?'), str(e)))

            for operacao, qtd_titulos, chaves_duplicadas in operacoes_criadas:
                messages.success(
                    request,
                    f"Operação {operacao.numero_contrato} criada com sucesso! {qtd_titulos} títulos registrados."
                )
                if chaves_duplicadas:
                    messages.warning(
                        request,
                        f"Atenção: {len(chaves_duplicadas)} NF-e já haviam sido importadas "
                        f"anteriormente em outra operação (chave(s): {', '.join(sorted(chaves_duplicadas))})."
                    )
            for numero_contrato, erro in erros_criacao:
                messages.error(request, f"Erro ao criar operação '{numero_contrato}': {erro}")

            if not operacoes_criadas:
                # Nenhuma operação foi criada: volta pra tela de revisão.
                return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos_post})

            if len(operacoes_criadas) == 1:
                return redirect('operacoes:detalhe_cessao', pk=operacoes_criadas[0][0].pk)
            return redirect('operacoes:listar_cessoes')

    return render(request, "operacoes/workflow_cessao.html", {"blocos": blocos})


@login_required
def listar_cessoes(request):
    """Lista todas as operações de cessão"""
    operacoes = OperacaoCessao.objects.select_related('fundo').order_by('-data_aquisicao')

    fundo_id = request.GET.get('fundo')
    status = request.GET.get('status')

    if fundo_id:
        operacoes = operacoes.filter(fundo_id=fundo_id)
    if status:
        operacoes = operacoes.filter(status=status)

    totais = operacoes.aggregate(
        count=Count('id'),
        total_nominal=Sum('valor_total_nominal'),
        total_aquisicao=Sum('valor_total_aquisicao'),
    )

    return render(request, "operacoes/listar_cessoes.html", {
        "operacoes": operacoes,
        "totais": totais,
    })


@login_required
def detalhe_cessao(request, pk):
    """Detalha uma operação de cessão com seus títulos"""
    operacao = get_object_or_404(OperacaoCessao.objects.select_related('fundo'), pk=pk)
    titulos = operacao.titulos.all().order_by('data_vencimento')

    desagio_pct = Decimal('0')
    if operacao.valor_total_nominal and operacao.valor_total_nominal > 0:
        desagio_pct = round(
            (1 - operacao.valor_total_aquisicao / operacao.valor_total_nominal) * 100, 2
        )

    return render(request, "operacoes/detalhe_cessao.html", {
        "operacao": operacao,
        "titulos": titulos,
        "desagio_pct": desagio_pct,
    })


@login_required
def gerar_termo_cessao(request, pk):
    """Gera documento DOCX do termo de cessão"""
    operacao = get_object_or_404(OperacaoCessao.objects.prefetch_related('titulos'), pk=pk)
    
    # Preparar dados para o template DOCX
    class TituloDoc:
        def __init__(self, titulo):
            self.numero_titulo = titulo.numero_titulo
            self.sacado_nome = titulo.sacado_nome
            self.sacado_doc = titulo.sacado_cpf_cnpj
            self.valor = titulo.valor_nominal
            self.vencimento_iso = titulo.data_vencimento.isoformat()
            self.tipo_credito = "Duplicata"  # Pode ser parametrizado depois
    
    titulos_doc = [TituloDoc(t) for t in operacao.titulos.all()]
    
    # Preparar partes
    class Partes:
        pass
    
    partes = Partes()
    partes.cedente_nome = operacao.cedente_nome
    partes.cedente_doc = operacao.cedente_cnpj
    partes.sacado_nome = titulos_doc[0].sacado_nome if titulos_doc else ""
    partes.sacado_doc = titulos_doc[0].sacado_doc if titulos_doc else ""
    
    # Dados da operação
    dados_operacao = {
        'data_contrato': operacao.data_contrato,
        'numero_contrato': operacao.numero_contrato,
    }
    
    # Gerar documento
    template_path = str(settings.BASE_DIR / "doc_templates" / "termo_cessao.docx")
    doc_bytes = render_termo_cessao_docx(template_path, partes=partes, titulos=titulos_doc, dados_operacao=dados_operacao)
    
    filename = f"termo_cessao_{operacao.numero_contrato}.docx"
    
    return HttpResponse(
        doc_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@login_required
def listar_titulos(request):
    """Lista todos os títulos com filtros"""
    titulos = Titulo.objects.select_related('fundo', 'operacao_cessao').order_by('-data_vencimento')

    fundo_id = request.GET.get('fundo')
    ativo = request.GET.get('ativo')

    if fundo_id:
        titulos = titulos.filter(fundo_id=fundo_id)
    if ativo == 'true':
        titulos = titulos.filter(ativo=True)
    elif ativo == 'false':
        titulos = titulos.filter(ativo=False)

    totais = titulos.aggregate(
        count=Count('id'),
        ativos=Count('id', filter=Q(ativo=True)),
        baixados=Count('id', filter=Q(ativo=False)),
    )

    return render(request, "operacoes/listar_titulos.html", {
        "titulos": titulos,
        "totais": totais,
    })


@login_required
def detalhe_titulo(request, pk):
    """Detalha um título com seu histórico de eventos"""
    titulo = get_object_or_404(
        Titulo.objects.select_related('fundo', 'operacao_cessao'),
        pk=pk
    )
    eventos = titulo.eventos.all().order_by('-data_evento')
    evento_form = EventoTituloForm(titulo=titulo)

    return render(request, "operacoes/detalhe_titulo.html", {
        "titulo": titulo,
        "eventos": eventos,
        "evento_form": evento_form,
    })


@login_required
def registrar_evento_titulo(request, pk):
    """Registra um evento de liquidação/baixa/reativação sobre um título"""
    titulo = get_object_or_404(Titulo, pk=pk)

    if request.method == "POST":
        form = EventoTituloForm(request.POST, titulo=titulo)

        if form.is_valid():
            try:
                criar_evento_titulo(
                    titulo=titulo,
                    tipo_evento=form.cleaned_data['tipo_evento'],
                    data_evento=form.cleaned_data['data_evento'],
                    usuario=request.user,
                    valor_evento=form.cleaned_data.get('valor_evento'),
                    descricao=form.cleaned_data.get('descricao', ''),
                    documento_referencia=form.cleaned_data.get('documento_referencia', ''),
                )
                messages.success(request, "Evento registrado com sucesso.")
            except Exception as e:
                messages.error(request, f"Erro ao registrar evento: {str(e)}")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)

    return redirect('operacoes:detalhe_titulo', pk=pk)


# ============================================
# VIEWS: APLICAÇÃO
# ============================================

@login_required
def nova_aplicacao(request):
    """Cria nova aplicação em ativo"""
    if request.method == "POST":
        form = AplicacaoForm(request.POST)
        
        if form.is_valid():
            aplicacao = form.save(commit=False)
            aplicacao.criado_por = request.user
            aplicacao.save()
            
            messages.success(request, "Aplicação registrada com sucesso!")
            return redirect('operacoes:listar_aplicacoes')
    else:
        form = AplicacaoForm()
    
    return render(request, "operacoes/nova_aplicacao.html", {
        "form": form,
    })


@login_required
def listar_aplicacoes(request):
    """Lista todas as aplicações"""
    aplicacoes = Aplicacao.objects.select_related('fundo', 'criado_por').order_by('-data_aplicacao')

    fundo_id = request.GET.get('fundo')
    tipo = request.GET.get('tipo')
    status = request.GET.get('status')

    if fundo_id:
        aplicacoes = aplicacoes.filter(fundo_id=fundo_id)
    if tipo:
        aplicacoes = aplicacoes.filter(tipo_aplicacao=tipo)
    if status:
        aplicacoes = aplicacoes.filter(status=status)

    # Totais consideram apenas aplicações ATIVAS: refletem o que ainda
    # está de fato aplicado/na carteira do fundo.
    # `.order_by()` limpa o order_by('-data_aplicacao') herdado de `aplicacoes`:
    # sem isso, o GROUP BY gerado pelo values()+annotate() inclui data_aplicacao
    # (o campo de ordenação), quebrando o agrupamento por tipo_aplicacao e
    # fazendo cada data virar seu próprio grupo — resultando numa soma errada
    # sempre que houver mais de uma aplicação do mesmo tipo em datas diferentes.
    totais_por_tipo = {
        item['tipo_aplicacao']: item['total']
        for item in aplicacoes.filter(status='ATIVA').order_by().values('tipo_aplicacao').annotate(total=Sum('valor'))
    }

    return render(request, "operacoes/listar_aplicacoes.html", {
        "aplicacoes": aplicacoes,
        "totais_por_tipo": totais_por_tipo,
        "liquidar_form": LiquidarAplicacaoForm(),
    })


@login_required
def liquidar_aplicacao(request, pk):
    """Registra a liquidação/resgate de uma aplicação"""
    aplicacao = get_object_or_404(Aplicacao, pk=pk)

    if request.method == "POST":
        form = LiquidarAplicacaoForm(request.POST)

        if form.is_valid():
            try:
                liquidar_aplicacao_service(
                    aplicacao,
                    data_liquidacao=form.cleaned_data['data_liquidacao'],
                    valor_resgate=form.cleaned_data['valor_resgate'],
                    usuario=request.user,
                )
                messages.success(request, "Aplicação liquidada com sucesso.")
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Erro ao liquidar aplicação: {str(e)}")
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)

    return redirect('operacoes:listar_aplicacoes')


# ============================================
# VIEWS: CNAB
# ============================================

@login_required
def cnab_parametros(request, pk):
    """Exibe formulário de parâmetros antes de gerar o CNAB"""
    operacao = get_object_or_404(OperacaoCessao.objects.select_related('fundo'), pk=pk)
    form = CnabParametrosForm()
    if not operacao.fundo.codigo_originador_cnab:
        messages.warning(
            request,
            f"O fundo {operacao.fundo.razao_social} não tem Código Originador (CDO) "
            "configurado. Cadastre-o na tela do fundo antes de gerar o CNAB."
        )
    return render(request, 'operacoes/cnab_parametros.html', {
        'form': form,
        'operacao': operacao,
    })


@login_required
def download_cnab_cessao(request, pk):
    """Gera e retorna o arquivo CNAB da cessão como download"""
    operacao = get_object_or_404(
        OperacaoCessao.objects.select_related('fundo').prefetch_related('titulos'), pk=pk
    )
    form = CnabParametrosForm(request.POST)
    if not form.is_valid():
        return render(request, 'operacoes/cnab_parametros.html', {
            'form': form,
            'operacao': operacao,
        })

    if not operacao.fundo.codigo_originador_cnab:
        messages.error(
            request,
            f"O fundo {operacao.fundo.razao_social} não tem Código Originador (CDO) "
            "configurado. Cadastre-o na tela do fundo antes de gerar o CNAB."
        )
        return render(request, 'operacoes/cnab_parametros.html', {
            'form': form,
            'operacao': operacao,
        })

    titulos = operacao.titulos.filter(ativo=True).prefetch_related('eventos')

    base_data = []
    for titulo in titulos:
        valor_liquidado = titulo.eventos.filter(
            tipo_evento__in=[
                TipoEventoTitulo.LIQUIDACAO_PARCIAL,
                TipoEventoTitulo.LIQUIDACAO_TOTAL,
            ]
        ).aggregate(total=Sum('valor_evento'))['total'] or Decimal('0')

        cpf_cnpj_limpo = rp(titulo.sacado_cpf_cnpj)
        identificacao_sacado = "1" if len(cpf_cnpj_limpo) <= 11 else "2"

        # VL_PAGO e VALOR_PAGO_TITULO representam a mesma coisa (valor já
        # liquidado do título) e devem sair iguais no CNAB — confirmado com
        # a origem das macros, que sempre preenche as duas colunas (BASE
        # col 9 e col 18) com o mesmo valor.
        valor_pago_str = str(valor_liquidado).replace('.', ',')

        base_data.append({
            "CNPJ_CEDENTE": operacao.cedente_cnpj,
            "NOME_CEDENTE": remover_pontos(operacao.cedente_nome),
            "SEU_NUMERO": titulo.numero_titulo,
            "NU_DOCUMENTO": titulo.numero_titulo,
            "DT_VENCIMENTO": titulo.data_vencimento.strftime('%d/%m/%Y'),
            "VL_NOMINAL": str(titulo.valor_nominal).replace('.', ','),
            "NU_CPF_CNPJ_SACADO": titulo.sacado_cpf_cnpj,
            "NM_SACADO": remover_caracteres_especiais(titulo.sacado_nome),
            "VL_PAGO": valor_pago_str,
            "IDENTIFICACAO_CPF_CNPJ_SACADO": identificacao_sacado,
            "ENDERECO": titulo.sacado_endereco,
            "CEP": titulo.sacado_cep,
            "TP_TITULO": titulo.tipo_titulo,
            "DT_EMISSAO_TITULO": titulo.data_emissao.strftime('%d/%m/%Y'),
            "COOBRIGACAO": titulo.coobrigacao,
            "IDENTIFICACAO_CPF_CNPJ_CEDENTE": "02",
            "NFE": titulo.chave_nfe,
            "VALOR_PAGO_TITULO": valor_pago_str,
        })

    menu_data = {
        "DTL": form.cleaned_data['dtl'].strftime('%d/%m/%Y'),
        "CDO": operacao.fundo.codigo_originador_cnab,
        "OCORRENCIA": operacao.fundo.ocorrencia_cnab_padrao or '01',
    }

    buffer = gerar_cnab_stream(base_data, menu_data)
    filename = f"CNAB_{operacao.numero_contrato}.txt"
    response = HttpResponse(buffer.read(), content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================
# HELPERS
# ============================================

def _limpar_cnpj(valor):
    """Remove formatação de CNPJ/CPF"""
    return ''.join(c for c in valor if c.isdigit())


def _titulo_dados_from_form(t):
    """
    Monta o dict de título esperado por `processar_cessao` a partir do
    cleaned_data de um TituloForm. `chave_nfe`, `sacado_endereco` e
    `sacado_cep` vêm do XML (campos ocultos no formset) e precisam ser
    repassados; `data_emissao` só é incluída quando informada, para que
    `processar_cessao` continue caindo no fallback (data de aquisição) nos
    títulos cadastrados manualmente sem XML.
    """
    dados = {
        'numero_titulo': t['numero_titulo'],
        'sacado_nome': t['sacado_nome'],
        'sacado_cpf_cnpj': _limpar_cnpj(t['sacado_cpf_cnpj']),
        'valor_nominal': t['valor_nominal'],
        'valor_aquisicao': t['valor_aquisicao'],
        'data_vencimento': t['data_vencimento'],
        'chave_nfe': t.get('chave_nfe') or '',
        'sacado_endereco': t.get('sacado_endereco') or '',
        'sacado_cep': t.get('sacado_cep') or '',
    }
    if t.get('data_emissao'):
        dados['data_emissao'] = t['data_emissao']
    return dados
