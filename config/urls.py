from django.contrib import admin
from django.urls import path, include

# IMPORTAÇÕES NECESSÁRIAS PARA DOWNLOADS (MÍDIA)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),             # Raiz vai para a Home
    path('prospeccao/', include('leads.urls')),   # /prospeccao/ vai para o Grid
    path('parceiros/', include('partners.urls')), 
    path('clientes/', include('clientes.urls')),
    path('ferramentas/', include('apps.core_admin.urls')),
]

handler403 = 'django.views.defaults.permission_denied' # Isso já é o padrão
# Mas se você quiser uma lógica extra, pode apontar para uma view específica.
# Por padrão, o Django já busca por um arquivo '403.html' na pasta templates.

# ==========================================
# CONFIGURAÇÃO PARA SERVIR UPLOADS DA SPEED
# ==========================================
# Ensina o Django a entregar os arquivos físicos (PDFs, Excel, Imagens) durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)