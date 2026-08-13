from django.urls import path, include  # 🚀 CORREÇÃO: Adicionado o 'include' aqui!
from django.contrib.auth import views as auth_views
from . import views
# As rotas que compõem views de outros apps (home, minhas-cotações, relatórios
# de gestão) moraram aqui e foram corrigidas para `config/urls.py` (QA da
# PO-032): `core` é camada 0 na ADR-007 e não pode importar `leads`/`partners`/
# `core_admin` (camadas 1 e 2), nem mesmo em urls.py.

urlpatterns = [
    path('health/', views.system_health, name='system_health'),
    path('docs/', views.docs_index, name='docs_index'),
    path('docs/<str:nome_arquivo>/', views.docs_documento, name='docs_documento'),
    path('gestao/', views.gestao_home, name='gestao_home'),
    path('gestao/relatorios/', views.gestao_relatorios, name='gestao_relatorios'),

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
