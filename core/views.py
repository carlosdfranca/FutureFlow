from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from usuarios.models import *

@login_required
def limites(request):
    return render(request, "limites.html")

@login_required
def relatorios(request):
    return render(request, "relatorios.html")


@login_required
@require_POST
def trocar_empresa(request):
    def _voltar():
        referer = request.META.get("HTTP_REFERER")
        if referer and url_has_allowed_host_and_scheme(
            referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(referer)
        return redirect("fundos:listar_fundos")

    try:
        empresa_id = int(request.POST.get("empresa_id"))
    except (TypeError, ValueError):
        messages.error(request, "Empresa inválida.")
        return _voltar()

    ## SuperUser pode trocar para qualquer empresa, desde que ela exista
    if request.user.is_superuser:
        if not Empresa.objects.filter(id=empresa_id).exists():
            messages.error(request, "Empresa inválida.")
            return _voltar()
        request.session["empresa_ativa"] = empresa_id
        request.session["mostrar_popup_desenquadramento"] = True
        messages.success(request, "Empresa alterada (superusuário).")
        return _voltar()

    # Usuários normais: só empresas vinculadas
    pertence = UserEmpresa.objects.filter(
        user=request.user,
        empresa_id=empresa_id
    ).exists()

    if pertence:
        request.session["empresa_ativa"] = empresa_id
        request.session["mostrar_popup_desenquadramento"] = True
        messages.success(request, "Empresa alterada com sucesso!")
    else:
        messages.error(request, "Você não tem acesso a esta empresa.")

    return _voltar()