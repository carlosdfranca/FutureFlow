import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from fundos.models import Fundo
from usuarios.models import UserEmpresa

from .forms import DocumentoUploadForm
from .models import CATEGORIA_META, CategoriaDocumento, DocumentoFundo


# ============================================================
# PERMISSÕES
# ============================================================

def _get_user_role(request):
    """Retorna o EmpresaRole do usuário autenticado na empresa ativa, se houver."""
    if not request.empresa_ativa or not request.user.is_authenticated:
        return None
    vinculo = UserEmpresa.objects.filter(
        user=request.user, empresa=request.empresa_ativa
    ).select_related('role').first()
    return vinculo.role if vinculo else None


def _check_pode_ver_documentos(request):
    if request.user.is_superuser:
        return True
    role = _get_user_role(request)
    return bool(role and role.pode_ver_documentos)


def _check_pode_gerenciar_documentos(request):
    if request.user.is_superuser:
        return True
    role = _get_user_role(request)
    return bool(role and role.pode_gerenciar_documentos)


def _categorias_com_contagem(fundo):
    contagens = dict(
        DocumentoFundo.objects.filter(fundo=fundo)
        .order_by()
        .values_list('categoria')
        .annotate(total=Count('id'))
    )
    categorias = []
    for value, label in CategoriaDocumento.choices:
        meta = CATEGORIA_META[value]
        categorias.append({
            'value': value,
            'label': label,
            'icon': meta['icon'],
            'variant': meta['variant'],
            'count': contagens.get(value, 0),
        })
    return categorias


# ============================================================
# VIEWS
# ============================================================

@login_required
def index(request):
    """Grid de fundos da empresa ativa, com a contagem de documentos de cada um."""
    empresa = request.empresa_ativa

    if not _check_pode_ver_documentos(request):
        messages.error(request, 'Você não tem permissão para visualizar documentos.')
        return redirect('fundos:listar_fundos')

    if empresa:
        fundos = (
            Fundo.objects.filter(empresa=empresa)
            .annotate(total_documentos=Count('documentos'))
            .order_by('razao_social')
        )
    else:
        fundos = Fundo.objects.none()

    context = {
        'fundos': fundos,
        'total_fundos': len(fundos),
        'total_documentos': sum(f.total_documentos for f in fundos),
    }
    return render(request, 'documentos/index.html', context)


@login_required
def documentos_fundo(request, fundo_id):
    """As 5 pastas (categorias) de documentos de um fundo, com contagem de cada uma."""
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if not _check_pode_ver_documentos(request):
        messages.error(request, 'Você não tem permissão para visualizar documentos.')
        return redirect('documentos:index')

    context = {
        'fundo': fundo,
        'categorias': _categorias_com_contagem(fundo),
    }
    return render(request, 'documentos/documentos_fundo.html', context)


@login_required
def documentos_categoria(request, fundo_id, categoria):
    """Lista de arquivos de uma categoria/diretório do fundo, com upload."""
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if categoria not in CategoriaDocumento.values:
        raise Http404('Categoria de documento inválida.')

    if not _check_pode_ver_documentos(request):
        messages.error(request, 'Você não tem permissão para visualizar documentos.')
        return redirect('documentos:index')

    documentos = (
        DocumentoFundo.objects.filter(fundo=fundo, categoria=categoria)
        .select_related('enviado_por')
    )

    context = {
        'fundo': fundo,
        'categoria': categoria,
        'categoria_label': CategoriaDocumento(categoria).label,
        'categoria_icon': CATEGORIA_META[categoria]['icon'],
        'documentos': documentos,
        'pode_gerenciar': _check_pode_gerenciar_documentos(request),
        'form': DocumentoUploadForm(),
    }
    return render(request, 'documentos/documentos_categoria.html', context)


@login_required
def upload_documento_view(request, fundo_id, categoria):
    empresa = request.empresa_ativa
    fundo = get_object_or_404(Fundo, id=fundo_id, empresa=empresa)

    if categoria not in CategoriaDocumento.values:
        raise Http404('Categoria de documento inválida.')

    if not _check_pode_gerenciar_documentos(request):
        messages.error(request, 'Você não tem permissão para enviar documentos.')
        return redirect('documentos:documentos_categoria', fundo_id=fundo_id, categoria=categoria)

    if request.method == 'POST':
        form = DocumentoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = form.cleaned_data['arquivo']
            documento = DocumentoFundo(
                fundo=fundo,
                categoria=categoria,
                arquivo=arquivo,
                nome=form.cleaned_data.get('nome') or arquivo.name,
                descricao=form.cleaned_data.get('descricao', ''),
                enviado_por=request.user,
            )
            documento.save()
            messages.success(request, f'"{documento.nome}" enviado com sucesso!')
        else:
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(request, error)

    return redirect('documentos:documentos_categoria', fundo_id=fundo_id, categoria=categoria)


@login_required
def download_documento(request, documento_id):
    empresa = request.empresa_ativa

    if not _check_pode_ver_documentos(request):
        messages.error(request, 'Você não tem permissão para acessar documentos.')
        return redirect('documentos:index')

    documento = get_object_or_404(
        DocumentoFundo.objects.select_related('fundo'), id=documento_id, fundo__empresa=empresa
    )

    if not documento.arquivo:
        raise Http404('Arquivo não encontrado.')

    # Preserva a extensão real do arquivo no download, mesmo que o "nome" de exibição
    # tenha sido customizado sem extensão.
    nome_download = os.path.basename(documento.arquivo.name)

    return FileResponse(documento.arquivo.open('rb'), as_attachment=True, filename=nome_download)


@login_required
def excluir_documento(request, documento_id):
    empresa = request.empresa_ativa
    documento = get_object_or_404(
        DocumentoFundo.objects.select_related('fundo'), id=documento_id, fundo__empresa=empresa
    )

    fundo_id = documento.fundo_id
    categoria = documento.categoria

    if not _check_pode_gerenciar_documentos(request):
        messages.error(request, 'Você não tem permissão para excluir documentos.')
        return redirect('documentos:documentos_categoria', fundo_id=fundo_id, categoria=categoria)

    if request.method == 'POST':
        nome = documento.nome
        arquivo = documento.arquivo
        documento.delete()
        if arquivo:
            try:
                arquivo.delete(save=False)
            except OSError:
                # Arquivo pode estar temporariamente bloqueado (ex.: um download em
                # andamento no Windows). O registro já foi removido; o arquivo físico
                # órfão pode ser limpo depois — não deve impedir a exclusão.
                pass
        messages.success(request, f'"{nome}" excluído com sucesso.')

    return redirect('documentos:documentos_categoria', fundo_id=fundo_id, categoria=categoria)
