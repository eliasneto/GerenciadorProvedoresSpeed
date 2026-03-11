# apps/core_admin/urls.py
from django.urls import path
from . import views

# REMOVA ou COMENTE a linha app_name se ela existir aqui
# app_name = 'core_admin' 

urlpatterns = [
    path('importar/', views.import_prospects, name='import_prospects'),
    path('modelo/', views.download_template, name='download_template'),
]