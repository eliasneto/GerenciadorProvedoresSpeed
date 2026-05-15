from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente, Endereco
from partners.models import Partner, Proposal


class EnderecoLastmilePartnerSearchTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="senha-segura",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

        self.cliente_alvo = Cliente.objects.create(
            id_ixc="900",
            razao_social="Cliente Alvo",
            nome_fantasia="Cliente Alvo",
            cnpj_cpf="00000000000100",
        )
        self.endereco_alvo = Endereco.objects.create(
            cliente=self.cliente_alvo,
            logradouro="Rua do Recife",
            numero="100",
            bairro="Boa Viagem",
            cidade="Recife",
            estado="PE",
            em_os_comercial_lastmile=True,
            os_atual_aberta=True,
        )

        self.parceiro_pe = Partner.objects.create(
            nome_fantasia="Parceiro Pernambuco",
            razao_social="Parceiro Pernambuco LTDA",
            cnpj_cpf="11111111000111",
            status="ativo",
        )
        self.parceiro_ce = Partner.objects.create(
            nome_fantasia="Parceiro Ceara",
            razao_social="Parceiro Ceara LTDA",
            cnpj_cpf="22222222000122",
            status="ativo",
        )

        self._criar_proposta_regional(self.parceiro_pe, "Recife", "PE", "Boa Viagem")
        self._criar_proposta_regional(self.parceiro_ce, "Fortaleza", "CE", "Aldeota")

    def _criar_proposta_regional(self, partner, cidade, estado, bairro):
        cliente = Cliente.objects.create(
            id_ixc=f"{partner.id}-{estado}",
            razao_social=f"Cliente {estado}",
            nome_fantasia=f"Cliente {estado}",
            cnpj_cpf=f"{partner.id:014d}"[:14],
        )
        endereco = Endereco.objects.create(
            cliente=cliente,
            logradouro=f"Rua {cidade}",
            numero="1",
            bairro=bairro,
            cidade=cidade,
            estado=estado,
        )
        Proposal.objects.create(
            partner=partner,
            cliente=cliente,
            client_address=endereco,
            status="analise",
        )

    def test_busca_padrao_mantem_filtro_regional(self):
        response = self.client.get(
            reverse("endereco_lastmile_partner_search", args=[self.endereco_alvo.pk])
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        nomes = {item["nome"] for item in data["resultados"]}

        self.assertIn("Parceiro Pernambuco", nomes)
        self.assertNotIn("Parceiro Ceara", nomes)
        self.assertFalse(data["busca_ampla_ativa"])

    def test_busca_ampla_permte_encontrar_parceiro_por_regiao_digitada(self):
        response = self.client.get(
            reverse("endereco_lastmile_partner_search", args=[self.endereco_alvo.pk]),
            {"busca_ampla": "1", "q": "Fortaleza"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        nomes = {item["nome"] for item in data["resultados"]}

        self.assertIn("Parceiro Ceara", nomes)
        self.assertTrue(data["busca_ampla_ativa"])
