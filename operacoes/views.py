from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.conf import settings
from decimal import Decimal

from .models import OperacaoCessao, Titulo, EventoTitulo, Aplicacao
from .forms import CessaoOperacaoForm, TituloFormSet, EventoTituloForm, AplicacaoForm
from .services.cessao import processar_cessao, criar_evento_titulo, calcular_totais_operacao

# Importar serviços existentes do core
from core.services.cessao_xml import parse_nfe_uploaded_file
from core.services.cessao_doc import render_termo_cessao_docx, render_termo_confirmacao_docx


# ============================================
# VIEWS: CESSÃO
# ============================================

@login_required
def workflow_cessao(request):
    """
    Workflow completo de cessão:
    1. Upload XML (opcional) → parse automático
    2. Preencher/editar títulos manualmente
    3. Confirmar → salvar operação + títulos + eventos
    4. Gerar documentos (termo cessão, confirmação)
    """
    cessao_form = CessaoOperacaoForm()
    titulos_formset = TituloFormSet()
    
    if request.method == "POST":
        acao = request.POST.get("acao")
        
        # ============================================
        # AÇÃO: IMPORTAR XML
        # ============================================
        if acao == "parse_xml":
            xml_file = request.FILES.get("xml_file")
            
            if not xml_file:
                messages.error(request, "Selecione um arquivo XML.")
                return render(request, "operacoes/workflow_cessao.html", {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })
            
            try:
                # Parse XML usando serviço existente
                parsed = parse_nfe_uploaded_file(xml_file)
                
                # Preparar dados iniciais dos títulos
                titulos_iniciais = []
                for t in parsed.titulos:
                    titulos_iniciais.append({
                        "numero_titulo": t.numero_titulo,
                        "sacado_nome": t.sacado_nome,
                        "sacado_cpf_cnpj": t.sacado_doc,
                        "valor_nominal": t.valor,
                        "valor_aquisicao": t.valor,  # Mesmo valor por padrão
                        "data_vencimento": t.vencimento_iso,
                    })
                
                # Criar formset com dados parseados
                titulos_formset = TituloFormSet(initial=titulos_iniciais)
                
                # Preencher dados do cedente no form de operação
                inicial_operacao = {
                    'cedente_cnpj': getattr(parsed, 'emitente_cnpj', ''),
                    'cedente_nome': getattr(parsed, 'emitente_razao_social', ''),
                }
                cessao_form = CessaoOperacaoForm(initial=inicial_operacao)
                
                messages.success(request, f"XML parseado com sucesso! {len(titulos_iniciais)} títulos encontrados.")
                
            except Exception as e:
                messages.error(request, f"Erro ao processar XML: {str(e)}")
            
            return render(request, "operacoes/workflow_cessao.html", {
                "cessao_form": cessao_form,
                "titulos_formset": titulos_formset,
            })
        
        # ============================================
        # AÇÃO: CONFIRMAR E SALVAR
        # ============================================
        elif acao == "confirmar":
            cessao_form = CessaoOperacaoForm(request.POST)
            titulos_formset = TituloFormSet(request.POST)
            
            if not (cessao_form.is_valid() and titulos_formset.is_valid()):
                messages.error(request, "Corrija os erros no formulário.")
                return render(request, "operacoes/workflow_cessao.html", {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })
            
            # Validar que há pelo menos um título
            titulos_validos = [f.cleaned_data for f in titulos_formset if f.cleaned_data and not f.cleaned_data.get('DELETE', False)]
            
            if not titulos_validos:
                messages.error(request, "Adicione pelo menos um título.")
                return render(request, "operacoes/workflow_cessao.html", {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })
            
            try:
                # Processar cessão usando service layer
                operacao = processar_cessao(
                    fundo=cessao_form.cleaned_data['fundo'],
                    cedente_dados={
                        'cnpj': _limpar_cnpj(cessao_form.cleaned_data['cedente_cnpj']),
                        'nome': cessao_form.cleaned_data['cedente_nome'],
                        'endereco': cessao_form.cleaned_data.get('cedente_endereco', ''),
                    },
                    titulos_dados=[
                        {
                            'numero_titulo': t['numero_titulo'],
                            'sacado_nome': t['sacado_nome'],
                            'sacado_cpf_cnpj': _limpar_cnpj(t['sacado_cpf_cnpj']),
                            'valor_nominal': t['valor_nominal'],
                            'valor_aquisicao': t['valor_aquisicao'],
                            'data_vencimento': t['data_vencimento'],
                        }
                        for t in titulos_validos
                    ],
                    operacao_dados={
                        'numero_contrato': cessao_form.cleaned_data['numero_contrato'],
                        'data_contrato': cessao_form.cleaned_data['data_contrato'],
                        'data_aquisicao': cessao_form.cleaned_data['data_aquisicao'],
                        'observacoes': cessao_form.cleaned_data.get('observacoes', ''),
                    },
                    usuario=request.user
                )
                
                messages.success(request, f"Operação {operacao.numero_contrato} criada com sucesso! {len(titulos_validos)} títulos registrados.")
                return redirect('operacoes:detalhe_cessao', pk=operacao.pk)
                
            except Exception as e:
                messages.error(request, f"Erro ao criar operação: {str(e)}")
                return render(request, "operacoes/workflow_cessao.html", {
                    "cessao_form": cessao_form,
                    "titulos_formset": titulos_formset,
                })
    
    return render(request, "operacoes/workflow_cessao.html", {
        "cessao_form": cessao_form,
        "titulos_formset": titulos_formset,
    })


@login_required
def listar_cessoes(request):
    """Lista todas as operações de cessão"""
    operacoes = OperacaoCessao.objects.select_related('fundo').order_by('-data_aquisicao')
    
    # Filtros opcionais
    fundo_id = request.GET.get('fundo')
    status = request.GET.get('status')
    
    if fundo_id:
        operacoes = operacoes.filter(fundo_id=fundo_id)
    if status:
        operacoes = operacoes.filter(status=status)
    
    return render(request, "operacoes/listar_cessoes.html", {
        "operacoes": operacoes,
    })


@login_required
def detalhe_cessao(request, pk):
    """Detalha uma operação de cessão com seus títulos"""
    operacao = get_object_or_404(OperacaoCessao.objects.select_related('fundo'), pk=pk)
    titulos = operacao.titulos.all().order_by('data_vencimento')
    
    return render(request, "operacoes/detalhe_cessao.html", {
        "operacao": operacao,
        "titulos": titulos,
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
    
    # Filtros
    fundo_id = request.GET.get('fundo')
    ativo = request.GET.get('ativo')
    
    if fundo_id:
        titulos = titulos.filter(fundo_id=fundo_id)
    if ativo == 'true':
        titulos = titulos.filter(ativo=True)
    elif ativo == 'false':
        titulos = titulos.filter(ativo=False)
    
    return render(request, "operacoes/listar_titulos.html", {
        "titulos": titulos,
    })


@login_required
def detalhe_titulo(request, pk):
    """Detalha um título com seu histórico de eventos"""
    titulo = get_object_or_404(
        Titulo.objects.select_related('fundo', 'operacao_cessao'),
        pk=pk
    )
    eventos = titulo.eventos.all().order_by('-data_evento')
    
    return render(request, "operacoes/detalhe_titulo.html", {
        "titulo": titulo,
        "eventos": eventos,
    })


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
    
    # Filtros
    fundo_id = request.GET.get('fundo')
    tipo = request.GET.get('tipo')
    
    if fundo_id:
        aplicacoes = aplicacoes.filter(fundo_id=fundo_id)
    if tipo:
        aplicacoes = aplicacoes.filter(tipo_aplicacao=tipo)
    
    return render(request, "operacoes/listar_aplicacoes.html", {
        "aplicacoes": aplicacoes,
    })


# ============================================
# HELPERS
# ============================================

def _limpar_cnpj(valor):
    """Remove formatação de CNPJ/CPF"""
    return ''.join(c for c in valor if c.isdigit())
