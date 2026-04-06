from django.urls import path, include  # 🚀 CORREÇÃO: Adicionado o 'include' aqui!
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('minhas-cotacoes/', views.minhas_cotacoes, name='minhas_cotacoes'),
    path('gestao/', views.gestao_home, name='gestao_home'),
    path('gestao/relatorios/', views.gestao_relatorios, name='gestao_relatorios'),
    path('gestao/relatorios/login-x-usuario/', views.gestao_relatorio_login_usuario, name='gestao_relatorio_login_usuario'),
    path('gestao/relatorios/login-x-status/', views.gestao_relatorio_login_status, name='gestao_relatorio_login_status'),
    path('gestao/relatorios/login-x-usuario/<int:pk>/responsavel/', views.gestao_relatorio_login_usuario_responsavel, name='gestao_relatorio_login_usuario_responsavel'),
    path('gestao/relatorios/proposta-x-status/', views.gestao_relatorio_proposta_status, name='gestao_relatorio_proposta_status'),
    path('gestao/relatorios/status-cliente/', views.gestao_relatorio_status_cliente, name='gestao_relatorio_status_cliente'),
    path('gestao/relatorios/cotacao-por-endereco/', views.gestao_relatorio_cotacao_endereco, name='gestao_relatorio_cotacao_endereco'),
    
    # Rota de Login (aponta para o template que você já criou)
    path('login/', auth_views.LoginView.as_view(
        template_name='core/login.html',
        redirect_authenticated_user=True
    ), name='login'),
    
    # Rota de Logout
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ==========================================================
    # ROTA MÁGICA DA TIMELINE (Funciona para o sistema inteiro)
    # ==========================================================
    path('historico/<str:app_label>/<str:model_name>/<int:object_id>/', views.timeline_global, name='timeline_global'),

    path('alterar-senha/', auth_views.PasswordChangeView.as_view(
        # Adicionamos o "/includes/" no caminho abaixo
        template_name='core/includes/alterar_senha.html', 
        success_url='/' 
    ), name='password_change'),

    path('backoffice/', include('apps.backoffice.urls')), # 🚀 LIGANDO O BACKOFFICE
]
