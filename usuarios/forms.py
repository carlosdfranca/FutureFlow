from django import forms
from django.contrib.auth.forms import UserChangeForm

from .models import CustomUser
from .services.avatar import normalizar_avatar

MAX_UPLOAD_MB = 5
TIPOS_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}


class ProfileForm(UserChangeForm):
    password = None  # escondemos o campo padrão

    # Checkbox escondido via atributo, nao HiddenInput: o JS alterna `.checked`
    # e o CheckboxInput so envia o valor quando marcado.
    remover_foto = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"hidden": True}),
    )

    password1 = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Digite a nova senha"}),
        required=False
    )
    password2 = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirme a nova senha"}),
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "profile_image"]
        labels = {
            "first_name": "Nome",
            "last_name": "Sobrenome",
            "email": "E-mail",
            "profile_image": "Foto de perfil",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "profile_image": forms.FileInput(attrs={
                "class": "avatar-ds__input",
                "accept": "image/jpeg,image/png,image/webp",
            }),
        }

    def clean_profile_image(self):
        imagem = self.cleaned_data.get("profile_image")

        # Sem upload novo o valor é o FieldFile já gravado — não mexer.
        if not imagem or not hasattr(imagem, "content_type"):
            return imagem

        if imagem.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"A imagem deve ter no máximo {MAX_UPLOAD_MB} MB.")

        if imagem.content_type not in TIPOS_PERMITIDOS:
            raise forms.ValidationError("Envie uma imagem JPG, PNG ou WEBP.")

        try:
            return normalizar_avatar(imagem)
        except Exception:
            raise forms.ValidationError("Não foi possível ler esta imagem. Tente outro arquivo.")

    def clean(self):
        cleaned_data = super().clean()

        # Enviar um arquivo novo vence o pedido de remoção.
        if cleaned_data.get("profile_image") and hasattr(cleaned_data["profile_image"], "content_type"):
            cleaned_data["remover_foto"] = False

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("As senhas não coincidem.")
            if len(password1) < 6:
                raise forms.ValidationError("A senha deve ter pelo menos 6 caracteres.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        # Nome do arquivo que estava gravado antes deste POST.
        anterior = self.instance.__class__.objects.filter(pk=self.instance.pk).values_list(
            "profile_image", flat=True
        ).first() if self.instance.pk else None

        if self.cleaned_data.get("remover_foto"):
            user.profile_image = None

        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)

        if commit:
            user.save()
            # Só depois de gravar sabemos o nome final do arquivo novo.
            if anterior and anterior != user.profile_image.name:
                user.profile_image.storage.delete(anterior)

        return user
