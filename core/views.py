from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from usuarios.models import *

@login_required
def limites(request):
    return render(request, "limites.html")

@login_required
def relatorios(request):
    return render(request, "relatorios.html")


@login_required
def trocar_empresa(request):
    if request.method == "POST":
        empresa_id = request.POST.get("empresa_id")

    ## SuperUser pode trocar para qualquer empresa
    if request.user.is_superuser:
        request.session["empresa_ativa"] = empresa_id
        request.session["mostrar_popup_desenquadramento"] = True
        messages.success(request, "Empresa alterada (superusuário).")
        return redirect(request.META.get("HTTP_REFERER", "fundos:listar_fundos"))

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

    return redirect(request.META.get("HTTP_REFERER", "fundos:listar_fundos"))