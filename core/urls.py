from django.urls import path
from . import views
from .views_cpv import workflow_cessao_view


urlpatterns = [
    path('', views.home, name='home'),
    path('limites/', views.limites, name='limites'),
    path('operacoes/', views.operacoes, name='operacoes'),
    path('risco/', views.risco, name='risco'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('conformidade/', views.conformidade, name='conformidade'),
    path('integracoes/', views.integracoes, name='integracoes'),

    path("trocar-empresa/", views.trocar_empresa, name="trocar_empresa"),
    
    path('workflow-cessao/', workflow_cessao_view, name='workflow_cessao')
]
