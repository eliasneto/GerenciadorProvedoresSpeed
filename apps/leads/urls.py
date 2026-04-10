from django.urls import path
from . import views

urlpatterns = [
    path('', views.lead_empresa_list, name='lead_list'),
    path('legado/', views.lead_list, name='lead_list_legacy'),
    path('empresa/<int:pk>/', views.lead_empresa_detail, name='lead_empresa_detail'),
    path('api/empresas/search/', views.api_lead_empresa_search, name='api_lead_empresa_search'),
    path('api/empresas/<int:pk>/enderecos/', views.api_lead_empresa_enderecos, name='api_lead_empresa_enderecos'),
    path('novo/', views.lead_create, name='lead_create'),
    path('editar/<int:pk>/', views.lead_update, name='lead_update'),
    path('excluir/<int:pk>/', views.lead_delete, name='lead_delete'),
    path('status/<int:pk>/', views.update_lead_status, name='update_lead_status'),
    path('<int:pk>/abrir-proposta/', views.lead_quick_proposal, name='lead_quick_proposal'),
    path('<int:pk>/converter/', views.lead_convert, name='lead_convert'),
    path('<int:pk>/historico/add/', views.lead_add_historico, name='lead_add_historico'),
    path('integracoes/', views.integracoes_view, name='integracoes_lastmile'),
    path('enderecos/', views.enderecos_lastmile_view, name='enderecos_lastmile'),
    path('enderecos/<int:endereco_pk>/leads-enderecos-grid/', views.endereco_lastmile_lead_address_grid, name='endereco_lastmile_lead_address_grid'),
    path('enderecos/<int:endereco_pk>/parceiros/', views.endereco_lastmile_partner_search, name='endereco_lastmile_partner_search'),
    path('enderecos/<int:endereco_pk>/cotacoes/criar/', views.endereco_lastmile_batch_proposal_create, name='endereco_lastmile_batch_proposal_create'),
    path('enderecos/<int:pk>/', views.enderecos_lastmile_cliente_view, name='enderecos_lastmile_cliente'),
    path('integracoes/modelo/', views.download_modelo_google_view, name='download_modelo_google'),
    
]
