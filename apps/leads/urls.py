from django.urls import path
from . import views

urlpatterns = [
    path('', views.lead_list, name='lead_list'),
    path('novo/', views.lead_create, name='lead_create'),
    path('editar/<int:pk>/', views.lead_update, name='lead_update'),
    path('excluir/<int:pk>/', views.lead_delete, name='lead_delete'),
    path('status/<int:pk>/', views.update_lead_status, name='update_lead_status'),
    path('<int:pk>/abrir-proposta/', views.lead_quick_proposal, name='lead_quick_proposal'),
    path('<int:pk>/converter/', views.lead_convert, name='lead_convert'),
    path('<int:pk>/historico/add/', views.lead_add_historico, name='lead_add_historico'),
    path('integracoes/', views.integracoes_view, name='integracoes_lastmile'),
    path('integracoes/modelo/', views.download_modelo_google_view, name='download_modelo_google'),
    
]
