from django.db import connection
from django.db.utils import DatabaseError, OperationalError
from django.shortcuts import render
from rest_framework.reverse import reverse

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import Cliente, Endereco
from partners.models import Partner, Proposal

from .schema import IntegracoesApiSchema
from .serializers import (
    ClienteCreateSerializer,
    ClienteSerializer,
    EnderecoCreateSerializer,
    EnderecoSerializer,
    PartnerCreateSerializer,
    PartnerSerializer,
    ProposalCreateSerializer,
    ProposalSerializer,
)


class PublicApiRootView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    schema = IntegracoesApiSchema(tags=["Infraestrutura"])

    def get(self, request, *args, **kwargs):
        return Response(
            {
                "nome": "API publica GerenciadorProvedores",
                "versao": "v1",
                "schema": reverse("integracoes_api:schema", request=request),
                "swagger": reverse("integracoes_api:swagger-ui", request=request),
                "health": reverse("integracoes_api:health", request=request),
                "clientes": reverse("integracoes_api:cliente-list", request=request),
                "parceiros": reverse("integracoes_api:partner-list", request=request),
                "propostas": reverse("integracoes_api:proposal-list", request=request),
            }
        )


class ApiHealthcheckView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    schema = IntegracoesApiSchema(tags=["Infraestrutura"])

    def get(self, request, *args, **kwargs):
        db_ok = True
        db_message = "ok"

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except (DatabaseError, OperationalError) as exc:
            db_ok = False
            db_message = str(exc)

        payload = {
            "status": "ok" if db_ok else "degraded",
            "service": "gerenciadorProvedores",
            "api_version": "v1",
            "database": {
                "status": "ok" if db_ok else "error",
                "detail": db_message,
            },
        }
        return Response(payload, status=200 if db_ok else 503)


class ClienteListAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    queryset = Cliente.objects.order_by("-criado_em")
    schema = IntegracoesApiSchema(tags=["Clientes"])

    def get_serializer_class(self):
        if getattr(self.request, "method", None) == "POST":
            return ClienteCreateSerializer
        return ClienteSerializer


class ClienteDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = ClienteSerializer
    queryset = Cliente.objects.order_by("-criado_em")
    schema = IntegracoesApiSchema(tags=["Clientes"])


class ClienteEnderecoListAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    schema = IntegracoesApiSchema(tags=["Clientes"])

    def get_serializer_class(self):
        if getattr(self.request, "method", None) == "POST":
            return EnderecoCreateSerializer
        return EnderecoSerializer

    def get_queryset(self):
        return Endereco.objects.filter(cliente_id=self.kwargs["cliente_pk"]).order_by("id")

    def perform_create(self, serializer):
        serializer.save(cliente_id=self.kwargs["cliente_pk"])


class PartnerListAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    queryset = Partner.objects.order_by("-data_cadastro")
    schema = IntegracoesApiSchema(tags=["Parceiros"])

    def get_serializer_class(self):
        if getattr(self.request, "method", None) == "POST":
            return PartnerCreateSerializer
        return PartnerSerializer


class ProposalListAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    schema = IntegracoesApiSchema(tags=["Propostas"])

    def get_serializer_class(self):
        if getattr(self.request, "method", None) == "POST":
            return ProposalCreateSerializer
        return ProposalSerializer

    def get_queryset(self):
        return (
            Proposal.objects.select_related("partner", "cliente", "client_address", "responsavel")
            .order_by("-id")
        )


class ProposalDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = ProposalSerializer
    schema = IntegracoesApiSchema(tags=["Propostas"])

    def get_queryset(self):
        return Proposal.objects.select_related("partner", "cliente", "client_address", "responsavel")


class SwaggerUIView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    schema = None

    def get(self, request, *args, **kwargs):
        return render(
            request,
            "integracoes_api/swagger_ui.html",
            {"schema_url": reverse("integracoes_api:schema")},
        )
