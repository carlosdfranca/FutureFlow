from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

from usuarios.models import *

import markdown
import os

@login_required
def home(request):
    # Caminho do release_notes.md
    release_path = os.path.join(settings.BASE_DIR, "static", "docs", "release_notes.md")

    release_html = ""
    if os.path.exists(release_path):
        with open(release_path, "r", encoding="utf-8") as f:
            text = f.read()
            release_html = markdown.markdown(text)

    return render(request, "home.html", {
        "release_notes": release_html
    })

@login_required
def limites(request):
    return render(request, "limites.html")

@login_required
def operacoes(request):
    return render(request, "operacoes.html")

@login_required
def risco(request):
    return render(request, "risco.html")

@login_required
def relatorios(request):
    return render(request, "relatorios.html")

@login_required
def conformidade(request):
    return render(request, "conformidade.html")

@login_required
def integracoes(request):
    return render(request, "integracoes.html")

@login_required
def workflow_cessao(request):
    return render(request, "workflow_cessao.html")


@login_required
def gerenciar_usuarios(request):
    empresa = request.empresa_ativa
    if not empresa:
        return redirect("selecionar_empresa")

    usuarios = UserEmpresa.objects.filter(empresa=empresa)
    roles = UserRole.objects.all()

    if request.method == "POST":
        email = request.POST.get("email")
        role_id = request.POST.get("role")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, "Usuário não encontrado.")
            return redirect("gerenciar_usuarios")

        role = UserRole.objects.get(id=role_id)

        UserEmpresa.objects.get_or_create(
            user=user,
            empresa=empresa,
            defaults={"role": role}
        )

        messages.success(request, "Usuário vinculado com sucesso!")
        return redirect("gerenciar_usuarios")

    return render(request, "usuarios.html", {
        "empresa": empresa,
        "usuarios": usuarios,
        "roles": roles
    })


@login_required
def trocar_empresa(request):
    if request.method == "POST":
        empresa_id = request.POST.get("empresa_id")

    ## SuperUser pode trocar para qualquer empresa
    if request.user.is_superuser:
        request.session["empresa_ativa"] = empresa_id
        messages.success(request, "Empresa alterada (superusuário).")
        return redirect(request.META.get("HTTP_REFERER", "home"))

    # Usuários normais: só empresas vinculadas
    pertence = UserEmpresa.objects.filter(
        user=request.user,
        empresa_id=empresa_id
    ).exists()

    if pertence:
        request.session["empresa_ativa"] = empresa_id
        messages.success(request, "Empresa alterada com sucesso!")
    else:
        messages.error(request, "Você não tem acesso a esta empresa.")

    return redirect(request.META.get("HTTP_REFERER", "home"))