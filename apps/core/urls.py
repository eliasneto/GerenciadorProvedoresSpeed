# Core/urls
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
]