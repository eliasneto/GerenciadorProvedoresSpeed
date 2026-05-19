from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente, Endereco
from leads.models import LeadEmpresa, LeadEndereco
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
        self.parceiro_sp = Partner.objects.create(
            nome_fantasia="Parceiro Sao Paulo",
            razao_social="Parceiro Sao Paulo LTDA",
            cnpj_cpf="33333333000133",
            status="ativo",
        )

        self._criar_proposta_regional(self.parceiro_pe, "Recife", "PE", "Boa Viagem")
        self._criar_proposta_regional(self.parceiro_ce, "Fortaleza", "CE", "Aldeota")
        self._criar_proposta_regional(self.parceiro_sp, "Sao Paulo", "SP", "Pinheiros")

        self.lead_empresa_pe = LeadEmpresa.objects.create(
            razao_social="Lead PE",
            nome_fantasia="Lead PE",
            cnpj_cpf="44444444000144",
        )
        self.lead_empresa_sp = LeadEmpresa.objects.create(
            razao_social="Lead SP",
            nome_fantasia="Lead SP",
            cnpj_cpf="55555555000155",
        )
        self.lead_endereco_pe = LeadEndereco.objects.create(
            empresa=self.lead_empresa_pe,
            endereco="Rua Recife",
            numero="10",
            bairro="Boa Viagem",
            cidade="Recife",
            estado="PE",
            cep="50000-000",
        )
        self.lead_endereco_sp = LeadEndereco.objects.create(
            empresa=self.lead_empresa_sp,
            endereco="Rua Sao Paulo",
            numero="20",
            bairro="Pinheiros",
            cidade="Sao Paulo",
            estado="SP",
            cep="01000-000",
        )

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

    def test_busca_ampla_sem_filtros_nao_fica_presa_a_regiao_do_endereco(self):
        response = self.client.get(
            reverse("endereco_lastmile_partner_search", args=[self.endereco_alvo.pk]),
            {"busca_ampla": "1"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        nomes = {item["nome"] for item in data["resultados"]}

        self.assertIn("Parceiro Pernambuco", nomes)
        self.assertIn("Parceiro Ceara", nomes)
        self.assertIn("Parceiro Sao Paulo", nomes)
        self.assertTrue(data["busca_ampla_ativa"])

    def test_busca_ampla_respeita_cidade_esvaziada_ao_filtrar_por_uf(self):
        response = self.client.get(
            reverse("endereco_lastmile_partner_search", args=[self.endereco_alvo.pk]),
            {"busca_ampla": "1", "estado": "SP", "cidade": ""},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        nomes = {item["nome"] for item in data["resultados"]}

        self.assertIn("Parceiro Sao Paulo", nomes)
        self.assertNotIn("Parceiro Pernambuco", nomes)
        self.assertNotIn("Parceiro Ceara", nomes)
        self.assertTrue(data["busca_ampla_ativa"])

    def test_grid_de_enderecos_respeita_cidade_esvaziada_ao_filtrar_por_uf(self):
        response = self.client.get(
            reverse("endereco_lastmile_lead_address_grid", args=[self.endereco_alvo.pk]),
            {"estado": "SP", "cidade": ""},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        nomes = {item["lead_nome"] for item in data["results"]}

        self.assertIn("Lead SP", nomes)
        self.assertNotIn("Lead PE", nomes)
        self.assertEqual(data["filtros"]["cidade"], "")
        self.assertEqual(data["filtros"]["estado"], "SP")

    def test_criacao_de_cotacao_aceita_partner_ids_sem_lead_endereco(self):
        response = self.client.post(
            reverse("endereco_lastmile_batch_proposal_create", args=[self.endereco_alvo.pk]),
            {
                "partner_ids": [str(self.parceiro_sp.id)],
                "next": reverse("enderecos_lastmile"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Proposal.objects.filter(
                client_address=self.endereco_alvo,
                partner=self.parceiro_sp,
                status="analise",
            ).exists()
        )
