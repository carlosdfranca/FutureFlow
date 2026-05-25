from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout do Django
    path("usuarios/", include("usuarios.urls")),             # perfil e futuros endpoints
    path("", include("core.urls")),                          # base da plataforma   
    path('fundos/', include('fundos.urls')),                 # Fundos
    path('operacoes/', include('operacoes.urls')),           # Operações (Cessões e Aplicações)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)