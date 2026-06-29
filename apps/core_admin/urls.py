# apps/core_admin/urls.py
from django.urls import path
from . import views

# REMOVA ou COMENTE a linha app_name se ela existir aqui
# app_name = 'core_admin' 

urlpatterns = [
    path('importar/', views.import_prospects, name='import_prospects'),
    path('atendimentos/desativacao/', views.desativar_atendimentos_ixc, name='desativar_atendimentos_ixc'),
    path('atendimentos/edicao-ixc/', views.editar_atendimentos_ixc, name='editar_atendimentos_ixc'),
    path('logins/edicao-ixc/', views.editar_logins_ixc, name='editar_logins_ixc'),
    path('restaurar-backup/', views.restore_backup, name='restore_backup'),
    path('teste-smtp/', views.smtp_test, name='smtp_test'),
    path('modelo/', views.download_template, name='download_template'),
    path('atendimentos/desativacao/modelo/', views.download_template_desativacao_atendimento, name='download_template_desativacao_atendimento'),
    path('atendimentos/edicao-ixc/modelo/', views.download_template_edicao_atendimento_ixc, name='download_template_edicao_atendimento_ixc'),
    path('logins/edicao-ixc/modelo/', views.download_template_edicao_login_ixc, name='download_template_edicao_login_ixc'),
    path('testar-api-ixc/', views.testar_api_ixc, name='testar_api_ixc'),
]
