from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("usuarios/", include("usuarios.urls")),             # login, perfil, password reset
    path("", include("core.urls")),                          # base da plataforma   
    path('fundos/', include('fundos.urls')),                 # Fundos
    path('operacoes/', include('operacoes.urls')),           # Operações (Cessões e Aplicações)
    path('documentos/', include('documentos.urls')),         # Documentos dos Fundos
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)