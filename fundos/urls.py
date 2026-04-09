from django.urls import path
from . import views

app_name = 'fundos'

urlpatterns = [
    path('', views.listar_fundos, name='listar_fundos'),
    path('novo/', views.novo_fundo, name='novo_fundo'),
    path('<uuid:fundo_id>/editar/', views.editar_fundo, name='editar_fundo'),
    path('aplicacao/nova/', views.nova_aplicacao, name='nova_aplicacao'),
    path('resgate/novo/', views.novo_resgate, name='novo_resgate'),
    # Informes Mensais
    path('<uuid:fundo_id>/informes/', views.listar_informes, name='listar_informes'),
    path('<uuid:fundo_id>/informes/importar/', views.importar_informe, name='importar_informe'),
    path('<uuid:fundo_id>/informes/<uuid:informe_id>/', views.detalhe_informe, name='detalhe_informe'),
]