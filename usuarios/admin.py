from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import (
    CustomUser,
    Empresa,
    EmpresaRole,
    UserEmpresa
)

# ===============================
# INLINE PARA VÍNCULO USER ↔ EMPRESA
# ===============================

class UserEmpresaInline(admin.TabularInline):
    model = UserEmpresa
    extra = 1
    autocomplete_fields = ["empresa", "role"]


# ===============================
# CUSTOM USER ADMIN
# ===============================

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    inlines = [UserEmpresaInline]

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "empresa_principal",
        "imagem_perfil",
    )

    search_fields = ("username", "email", "first_name", "last_name")

    fieldsets = (
        ("Credenciais", {
            "fields": ("username", "password")
        }),
        ("Informações pessoais", {
            "fields": ("first_name", "last_name", "email", "profile_image"),
        }),
        ("Permissões", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("Datas importantes", {
            "fields": ("last_login", "date_joined")
        }),
    )

    def empresa_principal(self, obj):
        vinculo = obj.userempresa_set.first()
        return vinculo.empresa.nome if vinculo else "-"

    empresa_principal.short_description = "Empresa Vinculada"

    def imagem_perfil(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%; object-fit:cover;">',
                obj.profile_image.url,
            )
        return "-"
    imagem_perfil.short_description = "Foto"


# ===============================
# ADMIN DE EMPRESA
# ===============================

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):

    list_display = ("nome", "cnpj")
    search_fields = ("nome", "cnpj")
    ordering = ("nome",)


# ===============================
# ADMIN DE ROLES (PERFIS)
# ===============================

@admin.register(EmpresaRole)
class EmpresaRoleAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "pode_gerenciar_usuarios", "pode_ver_fundos", "pode_ver_documentos", "pode_gerenciar_documentos")
    search_fields = ("nome", "empresa__nome")
    list_filter = ("empresa",)
    autocomplete_fields = ["empresa"]


# ===============================
# ADMIN DE VÍNCULOS (UserEmpresa)
# ===============================

@admin.register(UserEmpresa)
class UserEmpresaAdmin(admin.ModelAdmin):

    list_display = ("user", "empresa", "role")
    search_fields = ("user__username", "user__email", "empresa__nome", "role__nome")
    list_filter = ("empresa", "role")
    autocomplete_fields = ["user", "empresa", "role"]
