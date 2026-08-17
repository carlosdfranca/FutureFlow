from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.views.decorators.clickjacking import xframe_options_exempt
from .forms import ProfileForm

@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save()

            # Atualiza a sessão caso tenha alterado a senha
            if form.cleaned_data.get("password1"):
                update_session_auth_hash(request, user)

            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect("profile")
        else:
            messages.error(request, "Por favor, corrija os erros abaixo.")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "usuarios/profile.html", {"form": form})


@xframe_options_exempt
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("fundos:listar_fundos")
        else:
            messages.error(request, "Usuário ou senha inválidos.")
    response = render(request, "registration/login.html")
    response["Content-Security-Policy"] = "frame-ancestors https://fsbuilder.com.br"
    return response