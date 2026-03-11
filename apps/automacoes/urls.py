from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_automacoes, name='lista_automacoes'),
    path('iniciar/<int:pk>/', views.iniciar_automacao, name='iniciar_automacao'),
]