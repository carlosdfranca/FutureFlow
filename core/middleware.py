class EmpresaAtivaMiddleware:
    """
    Armazena na request a empresa ativa do usuário
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from usuarios.models import Empresa, UserEmpresa

        request.empresa_ativa = None

        if request.user.is_authenticated:
            empresa_id = request.session.get("empresa_ativa")

            if empresa_id:
                try:
                    request.empresa_ativa = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    request.empresa_ativa = None

            # Se ainda não há empresa na sessão, inicializa com a primeira disponível
            if request.empresa_ativa is None:
                if request.user.is_superuser:
                    primeira = Empresa.objects.first()
                else:
                    primeira = Empresa.objects.filter(
                        userempresa__user=request.user
                    ).first()

                if primeira:
                    request.empresa_ativa = primeira
                    request.session["empresa_ativa"] = primeira.id

        return self.get_response(request)
