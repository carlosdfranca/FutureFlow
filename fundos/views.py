from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from decimal import Decimal
from datetime import date
import uuid

from .models import Fundo, Cotista, MovimentacaoCota, InformeMensal
from .forms import FundoForm, InformeUploadForm, InformeLoteUploadForm
from .services.movimentacoes import processar_aplicacao, processar_resgate
from operacoes.models import Titulo, Aplicacao


@login_required
def nova_aplicacao(request):
    """View para processar nova aplicação"""
    if request.method == 'POST':
        fundo_id = request.POST.get('fundo')
        cotista_id = request.POST.get('cotista')
        valor = request.POST.get('valor')
        
        try:
            movimentacao = processar_aplicacao(
                fundo_id,
                cotista_id,
                Decimal(valor)
            )
            
            messages.success(
                request,
                f"Aplicação processada! Cotização em {movimentacao.data_cotizacao.strftime('%d/%m/%Y')}"
            )
            return redirect('fundos:nova_aplicacao')
        
        except Exception as e:
            messages.error(request, f"Erro: {str(e)}")
    
    empresa = request.empresa_ativa
    fundos = Fundo.objects.filter(empresa=empresa, ativo=True) if empresa else Fundo.objects.none()
    cotistas = Cotista.objects.filter(ativo=True)
    ultimas_aplicacoes = MovimentacaoCota.objects.filter(
        tipo_movimentacao='APLICACAO',
        fundo__empresa=empresa
    ).select_related('fundo', 'cotista').order_by('-data_solicitacao')[:10] if empresa else MovimentacaoCota.objects.none()
    
    context = {
        'fundos': fundos,
        'cotistas': cotistas,
        'ultimas_aplicacoes': ultimas_aplicacoes
    }
    
    return render(request, 'fundos/nova_aplicacao.html', context)


@login_required
def novo_resgate(request):
    """View para processar novo resgate"""
    if request.method == 'POST':
        fundo_id = request.POST.get('fundo')
        cotista_id = request.POST.get('cotista')
        quantidade = request.POST.get('quantidade')
        
        try:
            movimentacao = processar_resgate(
                fundo_id,
                cotista_id,
                Decimal(quantidade)
            )
            
            messages.success(
                request,
                f"Resgate solicitado! Cotização em {movimentacao.data_cotizacao.strftime('%d/%m/%Y')}"
            )
            return redirect('fundos:novo_resgate')
        
        except Exception as e:
            messages.error(request, f"Erro: {str(e)}")
    
    empresa = request.empresa_ativa
    fundos = Fundo.objects.filter(empresa=empresa, ativo=True) if empresa else Fundo.objects.none()
    cotistas = Cotista.objects.filter(ativo=True)
    ultimos_resgates = MovimentacaoCota.objects.filter(
        tipo_movimentacao='RESGATE',
        fundo__empresa=empresa
    ).select_related('fundo', 'cotista').order_by('-data_solicitacao')[:10] if empresa else MovimentacaoCota.objects.none()
    
    context = {
        'fundos': fundos,
        'cotistas': cotistas,
        'ultimos_resgates': ultimos_resgates
    }
    
    return render(request, 'fundos/novo_resgate.html', context)


@login_required
def listar_fundos(request):
    """Lista todos os fundos da empresa ativa"""
    empresa = request.empresa_ativa
    if empresa:
        fundos = Fundo.objects.filter(empresa=empresa).order_by('razao_social')
    else:
        fundos = Fundo.objects.none()

    fundos_fidc = fundos.filter(tipo_fundo='FIDC')
    fundos_fii  = fundos.filter(tipo_fundo='FII')
    fundos_fip  = fundos.filter(tipo_fundo='FIP')

    context = {
        'fundos': fundos,
        'fundos_fidc': fundos_fidc,
        'fundos_fii': fundos_fii,
        'fundos_fip': fundos_fip,
        'total_fundos': fundos.count(),
        'total_ativos': fundos.filter(ativo=True).count(),
        'total_inativos': fundos.filter(ativo=False).count(),
        'total_fidc': fundos_fidc.count(),
        'total_fii': fundos_fii.count(),
        'total_fip': fundos_fip.count(),
    }
    return render(request, 'fundos/listar_fundos.html', context)


@login_required
def novo_fundo(request):
    """Cadastra um novo fundo para a empresa ativa"""
    empresa = request.empresa_ativa
    if not empresa:
        messages.error(request, 'Nenhuma empresa ativa selecionada.')
        return redirect('fundos:listar_fundos')

    if request.method == 'POST':
        form = FundoForm(request.POST)
        if form.is_valid():
            fundo = form.save(commit=False)
            fundo.empresa = empresa
            fundo.save()
            messages.success(request, f'Fundo "{fundo.razao_social}" cadastrado com sucesso!')
            return redirect('fundos:listar_fundos')
    else:
        form = FundoForm()

    return render(request, 'fundos/novo_fundo.html', {'form': form, 'empresa': empresa})


@login_required
def editar_fundo(request, fundo_id):
    """Edita os dados de um fundo da empresa ativa"""
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if request.method == 'POST':
        form = FundoForm(request.POST, instance=fundo)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fundo "{fundo.razao_social}" atualizado com sucesso!')
            return redirect('fundos:listar_fundos')
    else:
        form = FundoForm(instance=fundo)

    return render(request, 'fundos/editar_fundo.html', {'form': form, 'fundo': fundo, 'empresa': empresa})


@login_required
def carteira_fundo(request, fundo_id):
    """Resumo consolidado da carteira do fundo: Direito Creditório (Cessões) + Liquidez (Aplicações)"""
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    titulos_ativos = Titulo.objects.filter(fundo=fundo, ativo=True)
    titulos_agg = titulos_ativos.aggregate(
        saldo_total=Sum('saldo_devedor'),
        nominal_total=Sum('valor_nominal'),
        count=Count('id'),
    )

    aplicacoes_ativas = Aplicacao.objects.filter(fundo=fundo, status='ATIVA')
    aplicacoes_agg = aplicacoes_ativas.aggregate(
        valor_total=Sum('valor'),
        count=Count('id'),
    )
    # .order_by() limpa a ordenação herdada do queryset -- sem isso o GROUP BY
    # gerado por values()+annotate() vaza o campo de ordenação e quebra o
    # agrupamento por tipo_aplicacao (mesmo cuidado de operacoes/views.py:listar_aplicacoes).
    aplicacoes_por_tipo = {
        item['tipo_aplicacao']: item['total']
        for item in aplicacoes_ativas.order_by().values('tipo_aplicacao').annotate(total=Sum('valor'))
    }

    saldo_dc = titulos_agg['saldo_total'] or Decimal('0')
    valor_liquidez = aplicacoes_agg['valor_total'] or Decimal('0')

    context = {
        'fundo': fundo,
        'titulos_agg': titulos_agg,
        'aplicacoes_agg': aplicacoes_agg,
        'aplicacoes_por_tipo': aplicacoes_por_tipo,
        'saldo_dc': saldo_dc,
        'valor_liquidez': valor_liquidez,
        'total_carteira': saldo_dc + valor_liquidez,
    }
    return render(request, 'fundos/carteira_fundo.html', context)


# ============================================================
# VIEWS — INFORMES MENSAIS
# ============================================================

def _check_pode_ver_informes(request):
    """Retorna True se o usuário autenticado tem permissão de visualizar informes."""
    if request.user.is_superuser:
        return True
    role = getattr(request, 'user_role', None)
    return role is not None and role.pode_ver_informes


def _check_pode_importar_informes(request):
    """Retorna True se o usuário autenticado tem permissão de importar informes."""
    if request.user.is_superuser:
        return True
    role = getattr(request, 'user_role', None)
    return role is not None and role.pode_importar_informes


@login_required
def listar_informes(request, fundo_id):
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if not _check_pode_ver_informes(request):
        messages.error(request, 'Você não tem permissão para visualizar informes mensais.')
        return redirect('fundos:listar_fundos')

    informes = InformeMensal.objects.filter(fundo=fundo).order_by('-competencia')

    context = {
        'fundo': fundo,
        'informes': informes,
        'pode_importar': _check_pode_importar_informes(request),
    }
    return render(request, 'fundos/listar_informes.html', context)


@login_required
def importar_informe(request, fundo_id):
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if not _check_pode_importar_informes(request):
        messages.error(request, 'Você não tem permissão para importar informes mensais.')
        return redirect('fundos:listar_informes', fundo_id=fundo_id)

    form = InformeUploadForm()
    form_lote = InformeLoteUploadForm()
    resultados_lote = None
    aba_ativa = 'unico'

    if request.method == 'POST':
        tipo_import = request.POST.get('tipo_import', 'unico')

        if tipo_import == 'lote':
            aba_ativa = 'lote'
            form_lote = InformeLoteUploadForm(request.POST, request.FILES)
            if form_lote.is_valid():
                zip_file = request.FILES['zip_file']
                try:
                    from .services.informe_xml import parse_informe_mensal, InformeParseError
                    from .services.importar_informe import importar_lote_zip

                    zip_bytes = zip_file.read()
                    resultados_lote = importar_lote_zip(
                        zip_bytes=zip_bytes,
                        fundo=fundo,
                        user=request.user,
                    )
                    ok_count = sum(1 for r in resultados_lote if r['status'] == 'ok')
                    err_count = len(resultados_lote) - ok_count
                    if ok_count:
                        messages.success(
                            request,
                            f'{ok_count} informe(s) importado(s) com sucesso'
                            + (f'; {err_count} com erro.' if err_count else '.'),
                        )
                    else:
                        messages.error(request, 'Nenhum informe foi importado. Verifique os erros abaixo.')
                except Exception as e:
                    messages.error(request, f'Erro ao processar o ZIP: {e}')
        else:
            form = InformeUploadForm(request.POST, request.FILES)
            if form.is_valid():
                xml_file = request.FILES['xml_file']
                try:
                    from .services.informe_xml import parse_informe_mensal, InformeParseError
                    from .services.importar_informe import importar_informe_mensal

                    xml_bytes = xml_file.read()
                    parsed = parse_informe_mensal(xml_bytes)
                    informe = importar_informe_mensal(
                        fundo_id=str(fundo.id),
                        parsed_dict=parsed,
                        user=request.user,
                        arquivo_nome=xml_file.name,
                    )
                    messages.success(
                        request,
                        f'Informe de {informe.competencia_display} importado com sucesso!'
                    )
                    return redirect('fundos:detalhe_informe', fundo_id=fundo_id, informe_id=informe.id)
                except Exception as e:
                    messages.error(request, f'Erro ao importar o informe: {e}')

    context = {
        'fundo': fundo,
        'form': form,
        'form_lote': form_lote,
        'resultados_lote': resultados_lote,
        'aba_ativa': aba_ativa,
    }
    return render(request, 'fundos/importar_informe.html', context)


@login_required
def detalhe_informe(request, fundo_id, informe_id):
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if not _check_pode_ver_informes(request):
        messages.error(request, 'Você não tem permissão para visualizar informes mensais.')
        return redirect('fundos:listar_fundos')

    informe = get_object_or_404(InformeMensal, id=informe_id, fundo=fundo)

    scr_display = [
        ('AA', informe.vl_rating_aa),
        ('A', informe.vl_rating_a),
        ('B', informe.vl_rating_b),
        ('C', informe.vl_rating_c),
        ('D\u2013H', informe.vl_rating_d_h),
    ]
    liquidez_display = [
        ('Até 30 dias', informe.vl_liqdez_30),
        ('31\u201360 dias', informe.vl_liqdez_60),
        ('61\u201390 dias', informe.vl_liqdez_90),
        ('91\u2013180 dias', informe.vl_liqdez_180),
        ('181\u2013360 dias', informe.vl_liqdez_360),
        ('> 360 dias', informe.vl_liqdez_mais_360),
    ]
    vencimentos_display = [
        ('Até 30 dias', informe.vl_venc_30),
        ('31\u201360 dias', informe.vl_venc_31_60),
        ('61\u201390 dias', informe.vl_venc_61_90),
        ('91\u2013120 dias', informe.vl_venc_91_120),
        ('121\u2013180 dias', informe.vl_venc_121_180),
        ('181\u2013360 dias', informe.vl_venc_181_360),
        ('361\u2013720 dias', informe.vl_venc_361_720),
        ('> 720 dias', informe.vl_venc_mais_720),
    ]

    context = {
        'fundo': fundo,
        'informe': informe,
        'pode_importar': _check_pode_importar_informes(request),
        'scr_display': scr_display,
        'liquidez_display': liquidez_display,
        'vencimentos_display': vencimentos_display,
    }
    return render(request, 'fundos/detalhe_informe.html', context)


@login_required
def excluir_informe(request, fundo_id, informe_id):
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if not _check_pode_importar_informes(request):
        messages.error(request, 'Você não tem permissão para excluir informes mensais.')
        return redirect('fundos:listar_informes', fundo_id=fundo_id)

    informe = get_object_or_404(InformeMensal, id=informe_id, fundo=fundo)

    if request.method == 'POST':
        competencia = informe.competencia_display
        informe.delete()
        messages.success(request, f'Informe de {competencia} excluído com sucesso.')
        return redirect('fundos:listar_informes', fundo_id=fundo_id)

    return redirect('fundos:listar_informes', fundo_id=fundo_id)