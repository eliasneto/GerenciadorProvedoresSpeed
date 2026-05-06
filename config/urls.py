from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('provedores/', include('leads.urls')),
    path('cotacao/', include('leads.urls')),
    path('prospeccao/', include('leads.urls')),
    path('parceiros/', include('partners.urls')),
    path('clientes/', include('clientes.urls')),
    path('ferramentas/', include('apps.core_admin.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Control System - Admin"
admin.site.site_title = "Portal Speed/HowBe"
admin.site.index_title = "Gestão de Parceiros"
