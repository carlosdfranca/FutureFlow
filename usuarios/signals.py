from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def marcar_popup_desenquadramento(sender, request, user, **kwargs):
    """Sinaliza que a Home deve exibir o popup de fundos desenquadrados na próxima carga."""
    request.session['mostrar_popup_desenquadramento'] = True
