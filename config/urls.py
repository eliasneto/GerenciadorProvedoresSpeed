from django.contrib import admin
from django.urls import path, include
from django.views.static import serve

# IMPORTAÇÕES NECESSÁRIAS PARA DOWNLOADS (MÍDIA)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),             # Raiz vai para a Home
    path('cotacao/', include('leads.urls')),   # /cotacao/ vai para o Grid
    path('prospeccao/', include('leads.urls')),   # Rota legada mantida por compatibilidade
    path('parceiros/', include('partners.urls')), 
    path('clientes/', include('clientes.urls')),
    path('ferramentas/', include('apps.core_admin.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

# ==========================================
# CONFIGURAÇÃO PARA SERVIR UPLOADS DA SPEED
# ==========================================
# Ensina o Django a entregar os arquivos físicos (PDFs, Excel, Imagens) durante o desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- 🎨 CUSTOMIZAÇÃO DO ADMIN ---
admin.site.site_header = "Control System - Admin" # O texto da barra superior
admin.site.site_title = "Portal Speed/HowBe"          # O texto da aba do navegador
admin.site.index_title = "Gestão de Parceiros"  # O subtítulo na página inicial    
