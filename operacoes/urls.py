from django.urls import path
from . import views

app_name = 'operacoes'

urlpatterns = [
    # Cessões
    path('cessoes/', views.listar_cessoes, name='listar_cessoes'),
    path('cessoes/nova/', views.workflow_cessao, name='workflow_cessao'),
    path('cessoes/<uuid:pk>/', views.detalhe_cessao, name='detalhe_cessao'),
    path('cessoes/<uuid:pk>/termo/', views.gerar_termo_cessao, name='gerar_termo_cessao'),
    path('cessoes/<uuid:pk>/cnab/', views.cnab_parametros, name='cnab_parametros'),
    path('cessoes/<uuid:pk>/cnab/download/', views.download_cnab_cessao, name='download_cnab_cessao'),
    
    # Títulos
    path('titulos/', views.listar_titulos, name='listar_titulos'),
    path('titulos/<uuid:pk>/', views.detalhe_titulo, name='detalhe_titulo'),
    path('titulos/<uuid:pk>/evento/', views.registrar_evento_titulo, name='registrar_evento_titulo'),

    # Aplicações
    path('aplicacoes/', views.listar_aplicacoes, name='listar_aplicacoes'),
    path('aplicacoes/nova/', views.nova_aplicacao, name='nova_aplicacao'),
    path('aplicacoes/<uuid:pk>/liquidar/', views.liquidar_aplicacao, name='liquidar_aplicacao'),
]
