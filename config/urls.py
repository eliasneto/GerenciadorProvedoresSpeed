from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve

from apps.core_admin import quotes_views as core_admin_quotes_views
from apps.leads import views as leads_views
from apps.partners import views as partners_views

# As rotas abaixo (ate 'gestao/relatorios/cotacao-por-endereco/') compoem
# views de leads/partners/core_admin numa mesma pagina raiz. Vivem aqui, e nao
# em apps/core/urls.py, porque `config` fica fora da tabela de camadas da
# ADR-007 (core e camada 0 e nao pode importar de camadas superiores) — QA da
# PO-032.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.integracoes_api.urls')),
    path('', leads_views.home, name='home'),
    path('', include('apps.core.urls')),
    path('minhas-cotacoes/', core_admin_quotes_views.minhas_cotacoes, name='minhas_cotacoes'),
    path('minhas-cotacoes/enviar-email/', core_admin_quotes_views.minhas_cotacoes_enviar_email, name='minhas_cotacoes_enviar_email'),
    path('gestao/relatorios/login-x-usuario/', partners_views.gestao_relatorio_login_usuario, name='gestao_relatorio_login_usuario'),
    path('gestao/relatorios/login-x-status/', partners_views.gestao_relatorio_login_status, name='gestao_relatorio_login_status'),
    path('gestao/relatorios/login-x-usuario/<int:pk>/responsavel/', partners_views.gestao_relatorio_login_usuario_responsavel, name='gestao_relatorio_login_usuario_responsavel'),
    path('gestao/relatorios/proposta-x-status/', partners_views.gestao_relatorio_proposta_status, name='gestao_relatorio_proposta_status'),
    path('gestao/relatorios/status-cliente/', partners_views.gestao_relatorio_status_cliente, name='gestao_relatorio_status_cliente'),
    path('gestao/relatorios/cotacao-por-endereco/', partners_views.gestao_relatorio_cotacao_endereco, name='gestao_relatorio_cotacao_endereco'),
    path('provedores/', include('apps.leads.urls')),
    path('cotacao/', include('apps.leads.urls')),
    path('prospeccao/', include('apps.leads.urls')),
    path('parceiros/', include('apps.partners.urls')),
    path('clientes/', include('apps.clientes.urls')),
    path('ferramentas/', include('apps.core_admin.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Control System - Admin"
admin.site.site_title = "Portal Speed/HowBe"
admin.site.index_title = "Gestão de Parceiros"
