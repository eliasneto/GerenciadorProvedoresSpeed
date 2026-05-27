from django.urls import path

from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONOpenAPIRenderer
from rest_framework.schemas import get_schema_view

from .views import (
    ApiHealthcheckView,
    ClienteDetailAPIView,
    ClienteEnderecoListAPIView,
    ClienteListAPIView,
    PartnerListAPIView,
    ProposalDetailAPIView,
    ProposalListAPIView,
    PublicApiRootView,
    SwaggerUIView,
)


app_name = "integracoes_api"

api_patterns = [
    path("", PublicApiRootView.as_view(), name="root"),
    path("health/", ApiHealthcheckView.as_view(), name="health"),
    path("clientes/", ClienteListAPIView.as_view(), name="cliente-list"),
    path("clientes/<int:pk>/", ClienteDetailAPIView.as_view(), name="cliente-detail"),
    path(
        "clientes/<int:cliente_pk>/enderecos/",
        ClienteEnderecoListAPIView.as_view(),
        name="cliente-endereco-list",
    ),
    path("parceiros/", PartnerListAPIView.as_view(), name="partner-list"),
    path("propostas/", ProposalListAPIView.as_view(), name="proposal-list"),
    path("propostas/<int:pk>/", ProposalDetailAPIView.as_view(), name="proposal-detail"),
]

schema_view = get_schema_view(
    title="GerenciadorProvedores API",
    url="/api/v1/",
    description="Documentacao OpenAPI da camada publica de integracoes.",
    version="1.0.0",
    public=True,
    patterns=api_patterns,
    renderer_classes=[JSONOpenAPIRenderer],
    authentication_classes=[],
    permission_classes=[AllowAny],
)

urlpatterns = [
    path("schema/", schema_view, name="schema"),
    path("swagger/", SwaggerUIView.as_view(), name="swagger-ui"),
    *api_patterns,
]
