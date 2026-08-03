from django.urls import path
from django.views.generic import RedirectView
from . import views
from .views_cessao import workflow_cessao_view


urlpatterns = [
    path('', RedirectView.as_view(pattern_name='fundos:listar_fundos', permanent=False)),
    path('limites/', views.limites, name='limites'),
    path('relatorios/', views.relatorios, name='relatorios'),

    path("trocar-empresa/", views.trocar_empresa, name="trocar_empresa"),
    
    path('workflow-cessao/', workflow_cessao_view, name='workflow_cessao')
]
