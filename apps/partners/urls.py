from django.urls import path
from . import views

urlpatterns = [
    # Rotas do Parceiro (Cadastro Mestre)
    path('', views.partner_list, name='partner_list'),
    path('<int:pk>/', views.partner_detail, name='partner_detail'),
    
    # Rotas da Proposta (Operação Técnica)
    # Criar uma nova proposta para um parceiro específico
    path('<int:partner_pk>/proposta/nova/', views.proposal_create, name='proposal_create'),
    
    # Editar os dados técnicos (A antiga 'ativar')
    path('proposta/<int:pk>/editar/', views.proposal_update, name='proposal_update'),
    
    # Deletar uma proposta específica
    path('proposta/<int:pk>/deletar/', views.proposal_delete, name='proposal_delete'),
    
    # Nova rota para a Gestão Global de OS
    path('gestao-os/', views.proposal_global_list, name='proposal_global_list'),

    path('endereco/<int:address_id>/propostas/', views.address_proposals_list, name='address_proposals_list'),
]