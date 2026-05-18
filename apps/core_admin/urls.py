# apps/core_admin/urls.py
from django.urls import path
from . import views

# REMOVA ou COMENTE a linha app_name se ela existir aqui
# app_name = 'core_admin' 

urlpatterns = [
    path('importar/', views.import_prospects, name='import_prospects'),
    path('atendimentos/desativacao/', views.desativar_atendimentos_ixc, name='desativar_atendimentos_ixc'),
    path('clientes/cadastro-ixc/', views.cadastrar_clientes_ixc, name='cadastrar_clientes_ixc'),
    path('restaurar-backup/', views.restore_backup, name='restore_backup'),
    path('teste-smtp/', views.smtp_test, name='smtp_test'),
    path('modelo/', views.download_template, name='download_template'),
    path('atendimentos/desativacao/modelo/', views.download_template_desativacao_atendimento, name='download_template_desativacao_atendimento'),
    path('clientes/cadastro-ixc/modelo/', views.download_template_cadastro_cliente_ixc, name='download_template_cadastro_cliente_ixc'),
]
