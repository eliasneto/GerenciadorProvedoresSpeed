# apps/core_admin/urls.py
from django.urls import path
from . import escola_email_views, views

# REMOVA ou COMENTE a linha app_name se ela existir aqui
# app_name = 'core_admin' 

urlpatterns = [
    path('importar/', views.import_prospects, name='import_prospects'),
    path('automacoes/<str:menu>/', views.automacoes_area, name='automacoes_area'),
    path('atendimentos/desativacao/', views.desativar_atendimentos_ixc, name='desativar_atendimentos_ixc'),
    path('atendimentos/edicao-ixc/', views.editar_atendimentos_ixc, name='editar_atendimentos_ixc'),
    path('atendimentos/resolucao-os/', views.resolver_os_atendimento_ixc, name='resolver_os_atendimento_ixc'),
    path('atendimentos/resolucao-os/progresso/', views.progresso_resolucao_os_atendimento, name='progresso_resolucao_os_atendimento'),
    path('logins/edicao-ixc/', views.editar_logins_ixc, name='editar_logins_ixc'),
    path('restaurar-backup/', views.restore_backup, name='restore_backup'),
    path('importacao-exportacao/', views.importacao_exportacao, name='importacao_exportacao'),
    path('importacao-exportacao/exportar-setores-escolas/', views.exportar_setores_escolas, name='exportar_setores_escolas'),
    path('importacao-exportacao/exportar-setores-escolas/modelo/', views.exportar_setores_escolas_modelo, name='exportar_setores_escolas_modelo'),
    path('teste-smtp/', views.smtp_test, name='smtp_test'),
    path('modelo/', views.download_template, name='download_template'),
    path('atendimentos/desativacao/modelo/', views.download_template_desativacao_atendimento, name='download_template_desativacao_atendimento'),
    path('atendimentos/edicao-ixc/modelo/', views.download_template_edicao_atendimento_ixc, name='download_template_edicao_atendimento_ixc'),
    path('atendimentos/resolucao-os/modelo/', views.download_template_resolucao_os_atendimento, name='download_template_resolucao_os_atendimento'),
    path('logins/edicao-ixc/modelo/', views.download_template_edicao_login_ixc, name='download_template_edicao_login_ixc'),
    path('testar-api-ixc/', views.testar_api_ixc, name='testar_api_ixc'),
    path('processos/', views.processos_list, name='processos_list'),
    path('processos/<int:pk>/', views.processo_detail, name='processo_detail'),
    path('processos/<int:processo_pk>/setores/<int:setor_pk>/status/', views.processo_setor_status_criar, name='processo_setor_status_criar'),
    path('processos/<int:processo_pk>/setores/<int:setor_pk>/status/<int:status_pk>/excluir/', views.processo_setor_status_excluir, name='processo_setor_status_excluir'),
    path('campos/', views.campos_list, name='campos_list'),
    path('campos/<int:pk>/editar/', views.campo_editar, name='campo_editar'),
    path('campos/<int:pk>/excluir/', views.campo_excluir, name='campo_excluir'),
    path('setor-escopo/', views.setor_escopo_list, name='setor_escopo_list'),
    path('setor-escopo/<int:pk>/editar/', views.setor_escopo_editar, name='setor_escopo_editar'),
    path('enderecos/<int:escola_pk>/rede/<str:tipo>/email/', escola_email_views.escola_rede_enviar_email, name='escola_rede_enviar_email'),
    path('enderecos/<int:escola_pk>/email/', escola_email_views.escola_enviar_email, name='escola_enviar_email'),
]
