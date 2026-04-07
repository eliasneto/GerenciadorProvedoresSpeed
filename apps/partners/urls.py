from django.urls import path
from . import views

urlpatterns = [
    # Rotas do Parceiro (Cadastro Mestre)
    path('', views.partner_list, name='partner_list'),
    
    # NOVAS ROTAS DA ESTEIRA DE REATIVAÇÃO:
    path('inativos/', views.partner_inactive_list, name='partner_inactive_list'), 
    path('winback/status/<int:pk>/', views.update_winback_status, name='update_winback_status'),

    # ... Suas outras rotas que já existem continuam aqui para baixo ...
    path('gestao-os/', views.proposal_global_list, name='proposal_global_list'),
    path('<int:pk>/', views.partner_detail, name='partner_detail'),
    path('<int:pk>/planos/', views.partner_plan_manage, name='partner_plan_manage'),
    path('<int:pk>/planos/add/', views.partner_plan_add, name='partner_plan_add'),
    path('<int:partner_pk>/planos/<int:plan_pk>/delete/', views.partner_plan_delete, name='partner_plan_delete'),
    path('<int:pk>/clientes/', views.partner_clients_list, name='partner_clients_list'),
    path('<int:pk>/historico/add/', views.partner_add_historico, name='partner_add_historico'),
    path('status/<int:pk>/', views.update_partner_status, name='update_partner_status'),
    path('<int:partner_pk>/proposta/nova/', views.proposal_create, name='proposal_create'),
    path('proposta/<int:pk>/lote/', views.proposal_batch_detail, name='proposal_batch_detail'),
    path('proposta/<int:pk>/lote/logins/', views.proposal_batch_logins, name='proposal_batch_logins'),
    path('proposta/<int:pk>/lote/status/', views.proposal_batch_status_update, name='proposal_batch_status_update'),
    path('proposta/<int:pk>/lote/historico/add/', views.proposal_batch_add_historico, name='proposal_batch_add_historico'),
    path('proposta/<int:pk>/', views.proposal_detail, name='proposal_detail'),
    path('proposta/<int:pk>/responsavel/', views.proposal_assumir_responsavel, name='proposal_assumir_responsavel'),
    path('proposta/<int:pk>/editar/', views.proposal_update, name='proposal_update'),
    path('proposta/<int:pk>/historico/add/', views.proposal_add_historico, name='proposal_add_historico'),
    path('proposta/<int:pk>/status/', views.proposal_status_update, name='proposal_status_update'),
    path('proposta/<int:pk>/deletar/', views.proposal_delete, name='proposal_delete'),
    path('endereco/<int:address_id>/propostas/', views.address_proposals_list, name='address_proposals_list'),
]
