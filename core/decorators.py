from django.shortcuts import redirect
from django.contrib import messages

def permissao_necessaria(attr):
    """
    Exemplo: @permissao_necessaria("pode_ver_lastro")
    """

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect("login")

            if not request.empresa_ativa:
                messages.error(request, "Selecione uma empresa para continuar.")
                return redirect("selecionar_empresa")

            user_empresa = request.user.userempresa_set.filter(
                empresa=request.empresa_ativa
            ).first()

            # Superuser ignora restrições
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Usuário não pertence à empresa ativa
            if not user_empresa:
                messages.error(request, "Você não tem acesso a esta empresa.")
                return redirect("selecionar_empresa")

            role = user_empresa.role

            if not getattr(role, attr, False):
                messages.error(request, "Você não tem permissão para acessar esta área.")
                return redirect("fundos:listar_fundos")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
