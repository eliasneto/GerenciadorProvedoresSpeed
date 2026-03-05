from django.urls import path
from . import views

urlpatterns = [
    path('', views.lead_list, name='lead_list'),
    path('novo/', views.lead_create, name='lead_create'),
    path('editar/<int:pk>/', views.lead_update, name='lead_update'),
    path('excluir/<int:pk>/', views.lead_delete, name='lead_delete'),
    path('status/<int:pk>/', views.update_lead_status, name='update_lead_status'),
    path('<int:pk>/converter/', views.lead_convert, name='lead_convert'),
    
]