from django.urls import path

from . import views

app_name = 'documentos'

urlpatterns = [
    path('', views.index, name='index'),
    path('<uuid:fundo_id>/', views.documentos_fundo, name='documentos_fundo'),
    path('<uuid:fundo_id>/<str:categoria>/', views.documentos_categoria, name='documentos_categoria'),
    path('<uuid:fundo_id>/<str:categoria>/upload/', views.upload_documento_view, name='upload_documento'),
    path('doc/<uuid:documento_id>/download/', views.download_documento, name='download_documento'),
    path('doc/<uuid:documento_id>/excluir/', views.excluir_documento, name='excluir_documento'),
]
