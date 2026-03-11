# apps/clientes/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Rotas de Interface
    path('', views.cliente_list, name='cliente_list'),
    path('novo/', views.cliente_create, name='cliente_create'),
    path('<int:pk>/endereco/novo/', views.endereco_create, name='endereco_create'),
    path('<int:pk>/enderecos/', views.endereco_list, name='endereco_list'),

    # ROTAS DE API (Endpoints para o Modal e Chained Dropdown)
    path('api/search/', views.api_cliente_search, name='api_cliente_search'),
    
    # Padronize esta rota para ser a que o JS do ProposalForm vai consumir
    path('api/addresses/<int:pk>/', views.api_cliente_enderecos, name='api_cliente_addresses'),

    path('api/unidade/<int:pk>/status/', views.api_update_unit_status, name='api_unit_status_update'),
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_edit'),
    path('unidade/<int:pk>/editar/', views.EnderecoUpdateView.as_view(), name='endereco_edit'),
]