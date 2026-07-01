from django.urls import path
from . import views

app_name = 'backoffice'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),

    path('cotacao/importar/', views.cotacao_import, name='cotacao_import'),
    path('cotacao/modelo/', views.download_modelo_cotacao, name='download_modelo'), # 🚀 Rota do download

    path('atendimentos/modelo/', views.download_modelo_atendimento, name='download_modelo_atendimento'),
    path('atendimentos/importar/', views.atendimento_import, name='atendimento_import'),

    path('clientes/cadastro-ixc/', views.cadastrar_clientes_ixc, name='cadastrar_clientes_ixc'),
    path('clientes/cadastro-ixc/modelo/', views.download_template_cadastro_cliente_ixc, name='download_template_cadastro_cliente_ixc'),
]