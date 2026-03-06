from django.urls import path
from . import views

urlpatterns = [
    # Rotas do Parceiro (Cadastro Mestre)
    path('', views.partner_list, name='partner_list'),
    
    # Nova rota para a Gestão Global de OS (Rotas de texto fixo ficam no topo)
    path('gestao-os/', views.proposal_global_list, name='proposal_global_list'),
    
    # Detalhes e Visões do Parceiro
    path('<int:pk>/', views.partner_detail, name='partner_detail'),
    path('<int:pk>/clientes/', views.partner_clients_list, name='partner_clients_list'), # ROTA CORRIGIDA AQUI!
    path('<int:pk>/historico/add/', views.partner_add_historico, name='partner_add_historico'),

    # Rotas da Proposta (Operação Técnica)
    path('<int:partner_pk>/proposta/nova/', views.proposal_create, name='proposal_create'),
    path('proposta/<int:pk>/editar/', views.proposal_update, name='proposal_update'),
    path('proposta/<int:pk>/deletar/', views.proposal_delete, name='proposal_delete'),
    
    # Rastreabilidade de Endereços
    path('endereco/<int:address_id>/propostas/', views.address_proposals_list, name='address_proposals_list'),
]