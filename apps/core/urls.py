from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    
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
]