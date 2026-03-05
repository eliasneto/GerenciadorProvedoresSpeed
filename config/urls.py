from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),             # Raiz vai para a Home
    path('prospeccao/', include('leads.urls')),   # /prospeccao/ vai para o Grid
    
    # ADICIONE ESTA LINHA:
    path('parceiros/', include('partners.urls')), 
    path('clientes/', include('clientes.urls')),
    path('ferramentas/', include('apps.core_admin.urls')),
]