from django.urls import reverse

from rest_framework.test import APITestCase

from clientes.models import Cliente, Endereco
from partners.models import Partner, Proposal


class IntegracoesApiTests(APITestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            id_ixc="CLI-100",
            razao_social="Cliente Exemplo LTDA",
            nome_fantasia="Cliente Exemplo",
            cnpj_cpf="12345678000199",
            contato_nome="Maria Cliente",
            email="cliente@example.com",
            telefone="85999999999",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente,
            tipo="Matriz",
            cep="60000-000",
            logradouro="Rua Principal",
            numero="100",
            bairro="Centro",
            cidade="Fortaleza",
            estado="CE",
            login_ixc="cliente.login",
            status="ativo",
            principal=True,
        )
        self.partner = Partner.objects.create(
            razao_social="Parceiro Exemplo SA",
            nome_fantasia="Parceiro Exemplo",
            cnpj_cpf="99887766000155",
            contato_nome="Joao Parceiro",
            email="parceiro@example.com",
            telefone="85888888888",
            status="ativo",
        )
        self.proposal = Proposal.objects.create(
            partner=self.partner,
            cliente=self.cliente,
            client_address=self.endereco,
            codigo_proposta="COT-2026-001",
            nome_proposta="Cotacao API",
            os_numero="OS-500",
            status="analise",
        )

    def test_swagger_ui_disponivel(self):
        response = self.client.get(reverse("integracoes_api:swagger-ui"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("integracoes_api:schema"))

    def test_schema_lista_rotas_publicas(self):
        response = self.client.get(reverse("integracoes_api:schema"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/clientes/", response.data["paths"])
        self.assertIn("/api/v1/parceiros/", response.data["paths"])
        self.assertIn("/api/v1/propostas/{id}/", response.data["paths"])

    def test_healthcheck_retorna_ok(self):
        response = self.client.get(reverse("integracoes_api:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["database"]["status"], "ok")

    def test_listagem_de_clientes(self):
        response = self.client.get(reverse("integracoes_api:cliente-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.cliente.id)

    def test_detalhe_de_cliente(self):
        response = self.client.get(reverse("integracoes_api:cliente-detail", args=[self.cliente.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id_ixc"], "CLI-100")

    def test_enderecos_por_cliente(self):
        response = self.client.get(
            reverse("integracoes_api:cliente-endereco-list", args=[self.cliente.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["cliente_id"], self.cliente.id)

    def test_listagem_de_parceiros(self):
        response = self.client.get(reverse("integracoes_api:partner-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["nome_fantasia"], "Parceiro Exemplo")

    def test_listagem_e_detalhe_de_propostas(self):
        list_response = self.client.get(reverse("integracoes_api:proposal-list"))
        detail_response = self.client.get(reverse("integracoes_api:proposal-detail", args=[self.proposal.id]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.data["count"], 1)
        self.assertEqual(list_response.data["results"][0]["partner_id"], self.partner.id)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["codigo_proposta"], "COT-2026-001")
