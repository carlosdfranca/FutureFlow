from django.contrib.auth.models import AbstractUser
from django.db import models
from stdimage.models import StdImageField

class CustomUser(AbstractUser):
    profile_image = StdImageField(
        upload_to="users/profile/",
        variations={"thumb": (150, 150, True)},
        default="users/profile/default.png",
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Empresa(models.Model):
    nome = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.nome


class EmpresaRole(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="roles")
    nome = models.CharField(max_length=50)
    descricao = models.TextField(blank=True)

    # Permissões dessa role — podem ser expandidas depois
    pode_gerenciar_usuarios = models.BooleanField(default=False)
    pode_ver_fundos = models.BooleanField(default=True)
    pode_ver_lastro = models.BooleanField(default=False)
    pode_ver_risco = models.BooleanField(default=False)
    pode_ver_conformidade = models.BooleanField(default=False)
    pode_ver_relatorios = models.BooleanField(default=True)
    pode_ver_informes = models.BooleanField(default=True)
    pode_importar_informes = models.BooleanField(default=False)

    class Meta:
        unique_together = ("empresa", "nome")

    def __str__(self):
        return f"{self.nome} ({self.empresa.nome})"


class UserEmpresa(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    role = models.ForeignKey(EmpresaRole, on_delete=models.PROTECT)

    class Meta:
        unique_together = ('user', 'empresa')

    def __str__(self):
        return f"{self.user} - {self.empresa} ({self.role})"