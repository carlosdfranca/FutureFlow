from django.urls import path
from . import views
from .views_cessao import workflow_cessao_view


urlpatterns = [
    path('', views.home, name='home'),
    path('limites/', views.limites, name='limites'),
    path('operacoes/', views.operacoes, name='operacoes'),
    path('relatorios/', views.relatorios, name='relatorios'),

    path("trocar-empresa/", views.trocar_empresa, name="trocar_empresa"),
    
    path('workflow-cessao/', workflow_cessao_view, name='workflow_cessao')
]
