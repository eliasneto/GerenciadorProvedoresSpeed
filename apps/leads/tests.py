from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.clientes.models import Cliente, Endereco
from apps.core.models import RegistroHistorico
from apps.escolas.models import (
    Campo, CampoObrigatoriedadeTransicao, CampoValor, CotacaoParceiro, Escola, MapaCalor, Processo, RedeExterna,
    RedeInterna, Setor, SetorEscopo, SetorStatus, TargetRedeExterna,
)
from apps.leads import context_processors, services
from apps.leads.models import AcessoSetor, Lead, LeadEmpresa, LeadEndereco
from apps.partners.models import Partner, Proposal


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


class LeadViewsTests(TestCase):
    """Cobertura HTTP (PO-011, fatia leads) dos fluxos de apps/leads/views.py
    que ainda nao tinham teste no nivel de view."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester",
            password="senha-segura",
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

        self.cliente = Cliente.objects.create(
            id_ixc="800",
            razao_social="Cliente Convert",
            nome_fantasia="Cliente Convert",
            cnpj_cpf="00000000000200",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente,
            logradouro="Rua Teste",
            numero="10",
            bairro="Centro",
            cidade="Fortaleza",
            estado="CE",
        )
        self.lead = Lead.objects.create(
            razao_social="Provedor Teste LTDA",
            nome_fantasia="Provedor Teste",
            cnpj_cpf="11122233000144",
            telefone="85999990000",
            email="contato@provedorteste.com.br",
            cidade="Fortaleza",
            estado="CE",
        )

    def _proposal_payload(self, **overrides):
        data = {
            'status': 'analise',
            'velocidade': '100 Mbps',
            'tecnologia': 'Fibra',
            'disponibilidade': '99,50%',
            'mttr': '4',
            'perda_pacote': '<1%',
            'latencia': '50',
            'interfaces': 'Gigabit Ethernet',
            'ipv4_bloco': 'IPv4 bloco/30',
            'trunk': 'Não',
            'dhcp': 'Sim',
            'tempo_contrato': '24',
        }
        data.update(overrides)
        return data

    def test_lead_list_legado_exige_grupo_lastmile(self):
        outro_user = get_user_model().objects.create_user(username="sem-grupo", password="outra-senha")
        self.client.force_login(outro_user)
        response = self.client.get(reverse('lead_list_legacy'))
        self.assertEqual(response.status_code, 403)

    def test_lead_list_legado_aplica_filtro_de_cidade(self):
        response = self.client.get(reverse('lead_list_legacy'), {'cidade': 'Fortaleza'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Provedor Teste")

    def test_lead_create_sincroniza_empresa_estruturada_e_redireciona(self):
        response = self.client.post(reverse('lead_create'), {
            'razao_social': 'Nova Prospeccao LTDA',
            'nome_fantasia': 'Nova Prospeccao',
            'cnpj_cpf': '22233344000155',
        })

        lead_criado = Lead.objects.get(cnpj_cpf='22233344000155')
        self.assertIsNotNone(lead_criado.empresa_estruturada)
        self.assertRedirects(
            response,
            reverse('lead_empresa_endereco_create', args=[lead_criado.empresa_estruturada_id]),
        )

    def test_lead_update_atualiza_dados_e_sincroniza_espelho(self):
        response = self.client.post(reverse('lead_update', args=[self.lead.pk]), {
            'razao_social': 'Provedor Teste Atualizado',
            'nome_fantasia': 'Provedor Teste',
            'cnpj_cpf': self.lead.cnpj_cpf,
        })

        self.assertRedirects(response, reverse('lead_list'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.razao_social, 'Provedor Teste Atualizado')
        self.assertIsNotNone(self.lead.empresa_estruturada)

    def test_lead_add_historico_com_descricao_cria_registro(self):
        response = self.client.post(reverse('lead_add_historico', args=[self.lead.pk]), {
            'descricao': 'Cliente pediu retorno amanha.',
        })

        self.assertRedirects(response, reverse('lead_update', args=[self.lead.pk]))
        lead_type = ContentType.objects.get_for_model(Lead)
        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=lead_type, object_id=self.lead.id).exists()
        )

    def test_lead_add_historico_sem_dados_nao_cria_registro(self):
        self.client.post(reverse('lead_add_historico', args=[self.lead.pk]), {})

        lead_type = ContentType.objects.get_for_model(Lead)
        self.assertFalse(
            RegistroHistorico.objects.filter(content_type=lead_type, object_id=self.lead.id).exists()
        )

    def test_lead_delete_remove_lead_da_base(self):
        response = self.client.post(reverse('lead_delete', args=[self.lead.pk]))

        self.assertRedirects(response, reverse('lead_list'))
        self.assertFalse(Lead.objects.filter(pk=self.lead.pk).exists())

    def test_update_status_andamento_bloqueia_quando_cnpj_ja_e_parceiro(self):
        Partner.objects.create(
            nome_fantasia="Parceiro Duplicado",
            razao_social="Parceiro Duplicado LTDA",
            cnpj_cpf=self.lead.cnpj_cpf,
            status='ativo',
        )

        response = self.client.post(reverse('update_lead_status', args=[self.lead.pk]), {'status': 'andamento'})

        self.assertRedirects(response, reverse('lead_list'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'novo')

    def test_update_status_andamento_sem_conflito_redireciona_para_conversao(self):
        response = self.client.post(reverse('update_lead_status', args=[self.lead.pk]), {'status': 'andamento'})

        self.assertRedirects(response, reverse('lead_convert', args=[self.lead.pk]))

    def test_update_status_inviavel_registra_historico_e_altera_status(self):
        response = self.client.post(reverse('update_lead_status', args=[self.lead.pk]), {
            'status': 'inviavel',
            'observacao': 'Regiao sem viabilidade tecnica.',
        })

        self.assertRedirects(response, reverse('lead_list'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'inviavel')
        lead_type = ContentType.objects.get_for_model(Lead)
        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=lead_type, object_id=self.lead.id).exists()
        )

    def test_update_status_negociacao_quando_ja_em_negociacao_nao_gera_erro(self):
        self.lead.status = 'negociacao'
        self.lead.save(update_fields=['status'])

        response = self.client.post(reverse('update_lead_status', args=[self.lead.pk]), {'status': 'negociacao'})

        self.assertRedirects(response, reverse('lead_list'))

    def test_update_status_negociacao_a_partir_de_outro_status_registra_historico(self):
        """PO-037: `mover_lead_para_negociacao` referenciava `Lead.STATUS_CHOICES`
        (inexistente; o certo e o `LEAD_STATUS_CHOICES` de apps/leads/models.py)
        e quebrava com AttributeError sempre que o lead mudava de fato de status
        para "negociacao", sem registrar o historico da transicao."""
        response = self.client.post(reverse('update_lead_status', args=[self.lead.pk]), {'status': 'negociacao'})

        self.assertRedirects(response, reverse('lead_list'))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'negociacao')
        lead_type = ContentType.objects.get_for_model(Lead)
        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=lead_type, object_id=self.lead.id).exists()
        )

    def test_lead_quick_proposal_cria_proposta_sem_remover_lead(self):
        response = self.client.post(reverse('lead_quick_proposal', args=[self.lead.pk]), {
            'cliente_id': str(self.cliente.pk),
            'enderecos_selecionados': [str(self.endereco.pk)],
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lead.objects.filter(pk=self.lead.pk).exists())
        self.assertTrue(
            Proposal.objects.filter(lead=self.lead, client_address=self.endereco).exists()
        )

    def test_lead_quick_proposal_sem_cliente_exibe_erro_e_nao_cria_proposta(self):
        response = self.client.post(reverse('lead_quick_proposal', args=[self.lead.pk]), {
            'enderecos_selecionados': [str(self.endereco.pk)],
        })

        self.assertRedirects(response, reverse('lead_list'))
        self.assertFalse(Proposal.objects.filter(lead=self.lead).exists())

    def test_lead_convert_get_exibe_formulario_com_rascunho_do_parceiro(self):
        response = self.client.get(reverse('lead_convert', args=[self.lead.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lead.nome_fantasia)

    def test_lead_convert_post_converte_lead_em_parceiro_e_remove_lead(self):
        response = self.client.post(
            reverse('lead_convert', args=[self.lead.pk]),
            self._proposal_payload(enderecos_selecionados=[str(self.endereco.pk)]),
        )

        self.assertFalse(Lead.objects.filter(pk=self.lead.pk).exists())
        partner = Partner.objects.get(cnpj_cpf='11122233000144')
        self.assertRedirects(response, reverse('partner_detail', args=[partner.pk]))
        self.assertTrue(
            Proposal.objects.filter(partner=partner, client_address=self.endereco).exists()
        )

    def test_integracoes_view_sem_arquivo_retorna_erro_400(self):
        response = self.client.post(reverse('integracoes_lastmile'), {})

        self.assertEqual(response.status_code, 400)
        self.assertIn('erro', response.json())

    def test_enderecos_lastmile_view_lista_escolas_do_dashboard_eace(self):
        Escola.objects.create(
            jira_key='EACE-1',
            uf='SP',
            status_escola='Conectado',
            inep='12345678',
            nome='ESCOLA MUNICIPAL TESTE',
            municipio='Sao Paulo',
            endereco_descricao='Rua Teste, 100',
        )

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ESCOLA MUNICIPAL TESTE')
        self.assertContains(response, '12345678')
        self.assertContains(response, 'Sao Paulo')

    def test_enderecos_lastmile_view_busca_por_inep(self):
        Escola.objects.create(jira_key='EACE-1', uf='SP', nome='ESCOLA A', inep='11111111')
        Escola.objects.create(jira_key='EACE-2', uf='SP', nome='ESCOLA B', inep='22222222')

        response = self.client.get(reverse('enderecos_lastmile'), {'q': '11111111'})

        self.assertContains(response, 'ESCOLA A')
        self.assertNotContains(response, 'ESCOLA B')

    def test_enderecos_lastmile_view_exibe_referencia_re_ri_da_api(self):
        Escola.objects.create(
            jira_key='EACE-1',
            nome='ESCOLA COM RE RI',
            dados_api={
                'parceiro_re': 'Parceiro RE Ltda',
                'parceiro_ri': 'Parceiro RI Ltda',
                'velocidade_dl_ofertada': 100,
            },
        )

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, 'Parceiro RE Ltda')
        self.assertContains(response, 'Parceiro RI Ltda')
        # RN-053: "Velocidade ofertada" nao e mais exibida na linha expandida.

    def test_enderecos_lastmile_view_sem_dados_re_ri_mostra_nao_informado(self):
        Escola.objects.create(jira_key='EACE-2', nome='ESCOLA SEM RE RI')

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, 'Não informado')

    def test_enderecos_lastmile_view_nao_depende_mais_de_endereco(self):
        # Endereco vazio/nao elegivel (cenario da ADR-008); tela deve mesmo
        # assim renderizar normalmente pois nao depende mais de Endereco.
        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertEqual(response.status_code, 200)

    def test_enderecos_lastmile_view_mostra_bolinha_de_conectividade_vermelha_sem_re_ri(self):
        # RN-062: a coluna "Status" deixou de exibir o texto de status_escola
        # (API) e passa a mostrar a bolinha de conectividade derivada de RE/RI.
        Escola.objects.create(jira_key='EACE-STATUS', nome='ESCOLA STATUS', status_escola='Conectado')

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertNotContains(response, 'Conectado')
        self.assertContains(response, 'bg-red-500')
        self.assertContains(response, 'Desconectada')

    def test_enderecos_lastmile_view_mostra_bolinha_verde_quando_re_e_ri_concluidas(self):
        escola = Escola.objects.create(jira_key='EACE-CONECTADA', nome='ESCOLA CONECTADA')
        setor = Setor.objects.create(processo=Processo.objects.create(nome='Processo QA Bolinha'), nome='Setor Bolinha')
        status_concluido = SetorStatus.objects.create(setor=setor, nome='Concluido')
        RedeExterna.objects.create(escola=escola, setor=setor, status=status_concluido)
        RedeInterna.objects.create(escola=escola, setor=setor, status=status_concluido)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, 'bg-green-500')
        self.assertContains(response, 'Conectada')


    def test_enderecos_lastmile_cliente_view_lista_status_200(self):
        response = self.client.get(reverse('enderecos_lastmile_cliente', args=[self.cliente.pk]))

        self.assertEqual(response.status_code, 200)

    def test_lead_empresa_list_status_200(self):
        response = self.client.get(reverse('lead_list'))

        self.assertEqual(response.status_code, 200)

    def test_lead_empresa_endereco_create_sincroniza_lead_espelho(self):
        empresa = LeadEmpresa.objects.create(razao_social='Empresa X', nome_fantasia='Empresa X')

        response = self.client.post(reverse('lead_empresa_endereco_create', args=[empresa.pk]), {
            'cidade': 'Fortaleza',
            'estado': 'CE',
            'bairro': 'Aldeota',
        })

        self.assertRedirects(response, reverse('lead_empresa_detail', args=[empresa.pk]))
        self.assertTrue(empresa.enderecos.exists())
        self.assertTrue(empresa.enderecos.first().leads_legados.exists())

    def test_api_lead_empresa_search_retorna_json(self):
        LeadEmpresa.objects.create(razao_social='API Search LTDA', nome_fantasia='API Search')

        response = self.client.get(reverse('api_lead_empresa_search'), {'q': 'API Search'})

        self.assertEqual(response.status_code, 200)
        nomes = {item['nome'] for item in response.json()['results']}
        self.assertIn('API Search', nomes)

    def test_download_modelo_google_view_retorna_planilha(self):
        response = self.client.get(reverse('download_modelo_google'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )


class EscolaRedeEditarViewTests(TestCase):
    """PO-051/ADR-015: Setor e Status do processo interno (RedeExterna/
    RedeInterna) editaveis no grid. Processo e fixo por tipo
    (NOME_PROCESSO_PADRAO) — nao e escolhido na tela."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-rede", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-REDE", nome="Escola Rede")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.setor = Setor.objects.create(processo=self.processo_re, nome="Lastmile QA")
        self.status = SetorStatus.objects.create(setor=self.setor, nome="Em andamento")

    def test_post_cria_rede_externa_com_processo_fixo(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'responsavel': self.user.pk},
        )

        self.assertEqual(response.status_code, 200)
        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.processo, self.processo_re)
        self.assertEqual(re.setor, self.setor)
        # RN-035: grid global ignora o Status enviado no POST — fica "Novo".
        self.assertEqual(re.status.nome, "Novo")
        self.assertContains(response, "atualizada")

    def test_grid_global_ignora_status_do_post_e_usa_novo_automaticamente(self):
        """RN-035: no grid global (sem setor_atual), o Status enviado no
        POST nao decide nada — o RE/RI e salvo com o Status "Novo" do
        Setor escolhido, criado automaticamente se ainda nao existir."""
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido QA")

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status.nome, "Novo")
        self.assertEqual(re.status.setor, self.setor)

    def test_grid_global_reaproveita_status_novo_existente(self):
        """RN-035: se o Setor escolhido ja tiver um Status "Novo", ele e
        reaproveitado em vez de duplicado (mesmo padrao da RN-033)."""
        novo_existente = SetorStatus.objects.create(setor=self.setor, nome="Novo")

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': '', 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status_id, novo_existente.pk)
        self.assertEqual(SetorStatus.objects.filter(setor=self.setor, nome="Novo").count(), 1)

    def test_grid_global_nao_exibe_select_de_status(self):
        """RN-035: no grid global, so o Setor e editavel — o campo Status
        nao aparece como select, mesmo na primeira atribuicao."""
        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, f'id="setor-select-re-{self.escola.pk}"')
        self.assertNotContains(response, f'id="status-select-re-{self.escola.pk}"')

    def test_primeira_atribuicao_de_setor_e_permitida_na_tela_global(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': '', 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, self.setor)
        self.assertContains(response, "atualizada")

    def test_alterar_setor_de_atividade_ja_atribuida_e_bloqueado_na_tela_global(self):
        """RN-056: este bloqueio (nao a obrigatoriedade de Responsavel) e o
        motivo pelo qual mover uma subatividade ja atribuida para outro
        Setor pelo grid global nunca chega a exigir Responsavel — so a
        Tela do proprio Setor pode mover, e la a excecao ja existe."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Bloqueio")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': ''},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, self.setor)
        self.assertEqual(re.status, self.status)
        self.assertContains(response, "So e possivel alterar pela tela desse Setor")

    def test_alterar_status_de_atividade_ja_atribuida_e_bloqueado_na_tela_global(self):
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido QA")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status, self.status)
        self.assertContains(response, "So e possivel alterar pela tela desse Setor")

    def test_alterar_setor_e_permitido_na_tela_do_proprio_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Bloqueio")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, outro_setor)
        self.assertContains(response, "atualizada")

    def test_tela_global_mostra_campos_read_only_quando_ja_tem_setor(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertNotContains(response, f'id="setor-select-re-{self.escola.pk}"')
        self.assertContains(response, "Ver Setor")
        self.assertContains(response, reverse('setor_detail', args=[self.setor.nome]))

    def test_tela_global_mostra_select_quando_ainda_nao_tem_setor(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, f'id="setor-select-re-{self.escola.pk}"')

    def test_post_com_setor_atual_igual_ao_novo_setor_pertence_a_tela(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        self.assertContains(response, 'data-pertence-ao-setor="sim"')

    def test_post_com_setor_atual_diferente_do_novo_setor_nao_pertence_a_tela(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Saida")

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        self.assertContains(response, 'data-pertence-ao-setor="nao"')

    def test_post_sem_setor_atual_sempre_pertence_a_tela(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': ''},
        )

        self.assertContains(response, 'data-pertence-ao-setor="sim"')

    def test_rede_interna_usa_processo_padrao_diferente_do_externo(self):
        setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RI QA")

        self.client.post(reverse('escola_rede_editar', args=[self.escola.pk, 're']), {'setor': self.setor.pk, 'status': '', 'responsavel': self.user.pk})
        self.client.post(reverse('escola_rede_editar', args=[self.escola.pk, 'ri']), {'setor': setor_ri.pk, 'status': '', 'responsavel': self.user.pk})

        re = RedeExterna.objects.get(escola=self.escola)
        ri = RedeInterna.objects.get(escola=self.escola)
        self.assertEqual(re.processo, self.processo_re)
        self.assertEqual(ri.processo, self.processo_ri)

    def test_post_atualiza_rede_existente_em_vez_de_duplicar(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        self.assertEqual(RedeExterna.objects.filter(escola=self.escola).count(), 1)
        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status, self.status)

    def test_post_com_setor_de_outro_processo_nao_salva(self):
        setor_do_processo_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RI QA")

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': setor_do_processo_ri.pk, 'status': ''},
        )

        self.assertFalse(RedeExterna.objects.filter(escola=self.escola).exists())
        self.assertContains(response, "setor")

    def test_post_com_status_de_outro_setor_nao_salva(self):
        """A validacao de integridade Setor/Status (RN-026) so e alcancavel
        onde o Status ainda vem do POST — na Tela de Setor (RN-033); no
        grid global o Status deixou de vir do POST (RN-035)."""
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor)
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Outro")
        status_de_outro_setor = SetorStatus.objects.create(setor=outro_setor, nome="Concluido")

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': status_de_outro_setor.pk, 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertIsNone(re.status)
        self.assertContains(response, "status")

    def test_post_sem_processo_padrao_cadastrado_mostra_erro(self):
        self.processo_re.delete()

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': '', 'status': ''},
        )

        self.assertFalse(RedeExterna.objects.filter(escola=self.escola).exists())
        self.assertContains(response, "nao esta cadastrado")

    def test_get_tipo_invalido_404(self):
        response = self.client.get(reverse('escola_rede_editar', args=[self.escola.pk, 'xx']))

        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_permissao_e_bloqueado(self):
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-rede", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': '', 'status': ''},
        )

        self.assertEqual(response.status_code, 403)

    def test_setor_status_opcoes_filtra_por_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Outro")
        SetorStatus.objects.create(setor=outro_setor, nome="Status de outro setor")

        response = self.client.get(reverse('setor_status_opcoes'), {'setor': self.setor.pk})

        self.assertContains(response, "Em andamento")
        self.assertNotContains(response, "Status de outro setor")

    def test_setor_status_opcoes_sem_setor_devolve_lista_vazia(self):
        response = self.client.get(reverse('setor_status_opcoes'))

        self.assertNotContains(response, "Em andamento")

    def test_enviar_para_outro_setor_define_status_aguardando_automaticamente(self):
        """RN-033: ao enviar a subatividade para outro Setor pela Tela de
        Setor, o Status vai automaticamente para "Aguardando" do Setor de
        destino, mesmo sem nenhum Status enviado no POST."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Destino")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, outro_setor)
        self.assertEqual(re.status.nome, "Aguardando")
        self.assertEqual(re.status.setor, outro_setor)
        self.assertContains(response, "atualizada")

    def test_enviar_para_outro_setor_ignora_status_escolhido_no_post(self):
        """RN-033: o Status enviado no POST nao decide nada quando o Setor
        selecionado deixa de ser o Setor atual — quem envia nao escolhe o
        status do Setor de destino."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Destino")
        status_de_outro_setor = SetorStatus.objects.create(setor=outro_setor, nome="Concluido")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': status_de_outro_setor.pk, 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status.nome, "Aguardando")

    def test_enviar_para_outro_setor_reaproveita_status_aguardando_existente(self):
        """RN-033: se o Setor de destino ja tiver um Status "Aguardando",
        ele e reaproveitado em vez de duplicado."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Destino")
        aguardando_existente = SetorStatus.objects.create(setor=outro_setor, nome="Aguardando")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status_id, aguardando_existente.pk)
        self.assertEqual(SetorStatus.objects.filter(setor=outro_setor, nome="Aguardando").count(), 1)

    def test_manter_no_proprio_setor_respeita_status_escolhido_no_post(self):
        """RN-033: a trava e so para quando o Setor muda — permanecendo no
        Setor atual, o Status escolhido continua valendo normalmente."""
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido QA")
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.status, outro_status)
        # PO: a resposta do POST precisa continuar editavel (selects), nao
        # cair no modo somente-leitura da tela global so porque a
        # subatividade ja tem Setor — senao os inputs somem apos Salvar
        # dentro da Tela do proprio Setor.
        self.assertContains(response, f'id="setor-select-re-{self.escola.pk}"')

    def test_subatividade_ja_em_setor_nao_mostra_opcao_selecione(self):
        """Subatividade ja dentro de um Setor so vai para outro Setor —
        nao existe a opcao de deixar Setor/Status em branco."""
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome},
        )

        # PO: verificar so dentro do <select> de Setor — o de Responsavel
        # tem a mesma opcao "Selecione" como placeholder legitimo (RN-060),
        # entao uma checagem na resposta inteira daria falso negativo.
        conteudo = response.content.decode()
        select_setor = conteudo.split(f'id="setor-select-re-{self.escola.pk}"')[1].split('</select>')[0]
        self.assertNotIn('<option value="">Selecione</option>', select_setor)
        self.assertNotContains(response, '<option value="">Selecione um setor</option>')

    def test_subatividade_sem_setor_ainda_mostra_opcao_selecione(self):
        """Sem Setor atribuido ainda (tela global), a opcao de deixar em
        branco continua disponivel para a primeira atribuicao no select de
        Setor. RN-035: ausencia do select de Status e verificada em
        test_grid_global_nao_exibe_select_de_status (aqui o texto isolado
        tambem aparece no JS de carregarStatusRede, entao nao serve de
        evidencia)."""
        response = self.client.get(reverse('enderecos_lastmile'))

        # Escola criada no setUp ainda nao tem RedeExterna/RedeInterna.
        self.assertContains(response, '<option value="">Selecione</option>')


class CampoObrigatorioNaTransicaoDeSetorTests(TestCase):
    """PO-079/RN-061/ADR-031: Campo (RN-031) com regra de obrigatoriedade
    (`CampoObrigatoriedadeTransicao`) bloqueia a troca de Setor enquanto o
    `CampoValor` daquele Campo estiver vazio."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-obrigatorio", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-OBRIG", nome="Escola Obrigatorio")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.setor_origem = Setor.objects.create(processo=self.processo_re, nome="Cotacao QA")
        self.setor_destino = Setor.objects.create(processo=self.processo_re, nome="Suprimentos QA")
        self.setor_destino_livre = Setor.objects.create(processo=self.processo_re, nome="Compras QA")
        self.status_origem = SetorStatus.objects.create(setor=self.setor_origem, nome="Em andamento")

        self.campo = Campo.objects.create(nome="Numero do pedido", tipo=Campo.TIPO_TEXTO, setor_nome=self.setor_origem.nome)
        CampoObrigatoriedadeTransicao.objects.create(campo=self.campo, setor_destino_nome=self.setor_destino.nome)

        self.re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor_origem, status=self.status_origem,
        )

    def test_bloqueia_troca_quando_campo_obrigatorio_esta_vazio(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor_destino.pk, 'status': '', 'setor_atual': self.setor_origem.nome},
        )

        re = RedeExterna.objects.get(pk=self.re.pk)
        self.assertEqual(re.setor, self.setor_origem)
        self.assertContains(response, "Numero do pedido")
        self.assertContains(response, "RN-061")
        # PO: nada foi salvo (RE continua no setor_origem) — a linha nao
        # pode ser marcada como tendo saido do Setor atual da tela, senao o
        # front a remove do DOM mesmo sem a troca ter sido persistida.
        self.assertContains(response, 'data-pertence-ao-setor="sim"')

    def test_permite_troca_quando_campo_obrigatorio_esta_preenchido(self):
        CampoValor.objects.create(
            campo=self.campo, content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=self.re.pk, valor="PED-123",
        )

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor_destino.pk, 'status': '', 'setor_atual': self.setor_origem.nome},
        )

        re = RedeExterna.objects.get(pk=self.re.pk)
        self.assertEqual(re.setor, self.setor_destino)
        self.assertContains(response, "atualizada")

    def test_nao_bloqueia_transicao_para_setor_sem_regra_cadastrada(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor_destino_livre.pk, 'status': '', 'setor_atual': self.setor_origem.nome},
        )

        re = RedeExterna.objects.get(pk=self.re.pk)
        self.assertEqual(re.setor, self.setor_destino_livre)

    def test_nao_bloqueia_primeira_atribuicao_de_setor_sem_setor_anterior(self):
        """RN-061: a regra so vale numa troca real — RE sem Setor anterior
        (primeira atribuicao) nunca aciona a obrigatoriedade, mesmo indo
        direto para o Setor de destino da regra."""
        escola_nova = Escola.objects.create(jira_key="EACE-OBRIG-NOVA", nome="Escola Obrigatorio Nova")

        response = self.client.post(
            reverse('escola_rede_editar', args=[escola_nova.pk, 're']),
            {'setor': self.setor_destino.pk, 'status': '', 'setor_atual': self.setor_destino.nome},
        )

        re = RedeExterna.objects.get(escola=escola_nova)
        self.assertEqual(re.setor, self.setor_destino)
        self.assertContains(response, "atualizada")

    def test_campo_de_outro_setor_nao_bloqueia_a_transicao(self):
        """A regra so olha Campos do proprio Setor de origem — um Campo com
        o mesmo nome de Setor de destino cadastrado, mas dono de outro
        Setor, nao interfere."""
        CampoObrigatoriedadeTransicao.objects.filter(campo=self.campo).delete()
        outro_campo = Campo.objects.create(
            nome="Campo de outro setor", tipo=Campo.TIPO_TEXTO, setor_nome=self.setor_destino_livre.nome,
        )
        CampoObrigatoriedadeTransicao.objects.create(campo=outro_campo, setor_destino_nome=self.setor_destino.nome)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor_destino.pk, 'status': '', 'setor_atual': self.setor_origem.nome},
        )

        re = RedeExterna.objects.get(pk=self.re.pk)
        self.assertEqual(re.setor, self.setor_destino)


class EscolaRedeResponsavelTests(TestCase):
    """PO-073/RN-052/ADR-027: Responsavel (usuario do sistema) de RE/RI/
    MapaCalor, atribuivel/reatribuivel manualmente nas mesmas telas que
    editam Setor/Status (grid global RN-026 e Tela de Setor RN-027/028),
    zerado junto com o Status ao trocar de Setor (RN-033), com historico
    De/Para (RN-029/041)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-responsavel", password="senha-segura", is_superuser=True,
        )
        self.outro_usuario = get_user_model().objects.create_user(
            username="outro-responsavel", password="senha-segura", first_name="Outro", last_name="Responsavel",
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-RESP-VIEW", nome="Escola Responsavel View")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.setor = Setor.objects.create(processo=self.processo_re, nome="Setor Responsavel QA")
        self.status = SetorStatus.objects.create(setor=self.setor, nome="Em andamento")
        # RN-060: sem AcessoSetor concedido, outro_usuario nao seria mais
        # elegivel como Responsavel deste Setor — concedido aqui para nao
        # misturar essa regra nova com o que estes testes de reatribuicao
        # ja cobriam antes dela.
        AcessoSetor.objects.create(usuario=self.outro_usuario, setor_nome=self.setor.nome)

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_responsavel_e_atribuido_manualmente_na_tela_do_setor(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor.pk, 'status': self.status.pk,
                'setor_atual': self.setor.nome, 'responsavel': self.user.pk,
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.responsavel, self.user)
        self.assertContains(response, "atualizada")

    def test_responsavel_e_reatribuivel_para_outro_usuario(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor.pk, 'status': self.status.pk,
                'setor_atual': self.setor.nome, 'responsavel': self.outro_usuario.pk,
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.responsavel, self.outro_usuario)

    def test_responsavel_editavel_na_primeira_atribuicao_do_grid_global(self):
        """RN-052/ADR-027 (pendencia resolvida): no grid global, Responsavel
        segue a mesma trava de edicao ja usada para Setor — editavel na
        primeira atribuicao, junto com o Setor."""
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': '', 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.responsavel, self.user)
        self.assertContains(response, "atualizada")

    def test_obrigatoriedade_nao_se_aplica_na_primeira_atribuicao_do_grid_global(self):
        """RN-056: a primeira atribuicao de Setor pelo grid global (sem
        setor_atual, subatividade que ainda nao tinha nenhum Setor) nunca
        exige Responsavel — quem atribui por ali nao esta necessariamente
        dentro do Setor de destino."""
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': ''},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, self.setor)
        self.assertIsNone(re.responsavel)
        self.assertContains(response, "atualizada")

    def test_responsavel_e_zerado_ao_enviar_para_outro_setor(self):
        """RN-052/ADR-027: RN-033 ja zera o Status para "Aguardando" ao
        enviar a subatividade a outro Setor — Responsavel e zerado no
        mesmo momento, liberando a subatividade para reatribuicao."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor Responsavel Destino")
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, outro_setor)
        self.assertEqual(re.status.nome, "Aguardando")
        self.assertIsNone(re.responsavel)
        self.assertContains(response, "atualizada")

    def test_obrigatoriedade_bloqueia_salvar_sem_responsavel_quando_setor_e_status_ficam_preenchidos(self):
        """RN-052: Setor/Status/Responsavel continuam opcionais no banco,
        mas o fluxo de edicao nao permite concluir a atribuicao (Setor e
        Status preenchidos) sem Responsavel."""
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome},
        )

        self.assertFalse(RedeExterna.objects.filter(escola=self.escola).exists())
        self.assertContains(response, "Responsável")
        # PO: erro nao pode derrubar a linha para o modo somente-leitura —
        # o usuario precisa continuar com o select de Responsavel na tela
        # para corrigir e tentar salvar de novo, sem precisar de F5.
        self.assertContains(response, f'id="responsavel-select-re-{self.escola.pk}"')

    def test_obrigatoriedade_nao_bloqueia_edicao_parcial_com_status_em_branco(self):
        """Edicao que deixa Status em branco (ex.: so ajustando outro campo
        na Tela de Setor) nao e bloqueada pela obrigatoriedade — o par
        Setor+Status preenchidos e que exige Responsavel junto."""
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertIsNone(re.status)
        self.assertContains(response, "atualizada")

    def test_obrigatoriedade_nao_se_aplica_ao_enviar_para_outro_setor(self):
        """RN-056: a zeragem automatica de Responsavel ao trocar de Setor
        (RN-033) nao e bloqueada pela obrigatoriedade — e o unico caso em
        que a subatividade fica, de proposito, sem Responsavel apos salvar."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor Responsavel Destino 2")
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.setor, outro_setor)
        self.assertContains(response, "atualizada")

    def test_historico_de_para_ao_atribuir_responsavel(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor.pk, 'status': self.status.pk,
                'setor_atual': self.setor.nome, 'responsavel': self.user.pk,
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(
            content_type=self._content_type_re(), object_id=re.id, rotulo="Responsavel",
        )
        self.assertEqual(registro.valor_anterior, "Vazio")
        self.assertEqual(registro.valor_novo, self.user.username)
        self.assertIn("Responsavel", registro.acao)

    def test_historico_de_para_ao_reatribuir_responsavel(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor.pk, 'status': self.status.pk,
                'setor_atual': self.setor.nome, 'responsavel': self.outro_usuario.pk,
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(
            content_type=self._content_type_re(), object_id=re.id, rotulo="Responsavel",
        )
        self.assertEqual(registro.valor_anterior, self.user.username)
        self.assertEqual(registro.valor_novo, self.outro_usuario.get_full_name())

    def test_historico_de_para_ao_zerar_responsavel_por_troca_de_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor Responsavel Destino 3")
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(
            content_type=self._content_type_re(), object_id=re.id, rotulo="Responsavel",
        )
        self.assertEqual(registro.valor_anterior, self.user.username)
        self.assertEqual(registro.valor_novo, "Vazio")

    def test_reatribuir_para_o_mesmo_responsavel_nao_gera_historico_duplicado(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor.pk, 'status': self.status.pk,
                'setor_atual': self.setor.nome, 'responsavel': self.user.pk,
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertFalse(
            RegistroHistorico.objects.filter(
                content_type=self._content_type_re(), object_id=re.id, rotulo="Responsavel",
            ).exists()
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-responsavel", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'responsavel': self.user.pk},
        )

        self.assertEqual(response.status_code, 403)

    def test_select_de_responsavel_aparece_no_grid_com_usuarios_ativos(self):
        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, f'id="responsavel-select-re-{self.escola.pk}"')
        self.assertContains(response, self.outro_usuario.get_full_name())

    def test_mapa_calor_tambem_aceita_responsavel(self):
        """RN-052: a regra vale igualmente para as tres subatividades —
        RedeExterna, RedeInterna e MapaCalor, sem excecao."""
        processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)
        setor_mc = Setor.objects.create(processo=processo_mc, nome="Setor MC Responsavel QA")
        status_mc = SetorStatus.objects.create(setor=setor_mc, nome="Em andamento MC")
        MapaCalor.objects.create(escola=self.escola, processo=processo_mc, setor=setor_mc, status=status_mc)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {
                'setor': setor_mc.pk, 'status': status_mc.pk,
                'setor_atual': setor_mc.nome, 'responsavel': self.user.pk,
            },
        )

        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertEqual(mc.responsavel, self.user)

    def test_servico_usuarios_responsavel_opcoes_filtra_por_acesso_ao_setor(self):
        """RN-060: sem AcessoSetor para o nome do Setor, o usuario nao
        aparece entre as opcoes de Responsavel — mesmo estando ativo no
        sistema. Superusuario continua elegivel em qualquer Setor
        (mesma excecao ja usada pela RN-055)."""
        setor_sem_acesso = Setor.objects.create(processo=self.processo_re, nome="Setor Sem Acesso QA")

        opcoes = services.usuarios_responsavel_opcoes(setor_sem_acesso)

        self.assertIn(self.user, opcoes)
        self.assertNotIn(self.outro_usuario, opcoes)

    def test_servico_usuarios_responsavel_opcoes_sem_setor_devolve_todos_ativos(self):
        """RN-060: subatividade ainda sem Setor definido nao aplica
        nenhum filtro — mesmo comportamento de antes da regra."""
        opcoes = services.usuarios_responsavel_opcoes(None)

        self.assertIn(self.user, opcoes)
        self.assertIn(self.outro_usuario, opcoes)

    def test_salvar_responsavel_sem_acesso_ao_setor_e_rejeitado(self):
        """RN-060: o servidor rejeita salvar um Responsavel sem AcessoSetor
        para o Setor da linha, mesmo enviado no POST — nao confia somente
        na lista de opcoes do HTML do formulario."""
        setor_sem_acesso = Setor.objects.create(processo=self.processo_re, nome="Setor Sem Acesso Salvar QA")
        status_sem_acesso = SetorStatus.objects.create(setor=setor_sem_acesso, nome="Em andamento")

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': setor_sem_acesso.pk, 'status': status_sem_acesso.pk,
                'setor_atual': setor_sem_acesso.nome, 'responsavel': self.outro_usuario.pk,
            },
        )

        self.assertFalse(RedeExterna.objects.filter(escola=self.escola).exists())
        self.assertContains(response, "não tem acesso")

    def test_grid_calcula_responsavel_opcoes_por_setor_da_linha(self):
        """RN-060: cada linha do grid usa a lista de Responsavel do seu
        proprio Setor — nao uma lista unica para a pagina inteira."""
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status)

        setor_privado = Setor.objects.create(processo=self.processo_re, nome="Setor Privado QA")
        outra_escola = Escola.objects.create(jira_key="EACE-RESP-PRIVADO", nome="Escola Responsavel Privada")
        RedeExterna.objects.create(escola=outra_escola, processo=self.processo_re, setor=setor_privado)

        response = self.client.get(reverse('enderecos_lastmile'))
        escolas_por_pk = {escola.pk: escola for escola in response.context['page_obj']}

        # self.setor concede acesso a outro_usuario (setUp desta classe).
        self.assertIn(self.outro_usuario, escolas_por_pk[self.escola.pk].responsavel_opcoes_re)
        # "Setor Privado QA" nao concede acesso a ninguem alem do superusuario.
        self.assertNotIn(self.outro_usuario, escolas_por_pk[outra_escola.pk].responsavel_opcoes_re)
        self.assertIn(self.user, escolas_por_pk[outra_escola.pk].responsavel_opcoes_re)


class EscolaRedeHistoricoTests(TestCase):
    """PO-054/RN-029: historico e anexo individuais de RedeExterna/
    RedeInterna, com log automatico de alteracao de Setor/Status feita
    pela tela, e visao combinada na Escola (RE + RI)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-historico-rede", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-HIST", nome="Escola Historico")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.setor = Setor.objects.create(processo=self.processo_re, nome="Setor Historico QA")
        self.status = SetorStatus.objects.create(setor=self.setor, nome="Em andamento")
        self.setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RI Historico QA")

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_editar_rede_gera_historico_sistema_com_antes_e_depois(self):
        # setor_atual: RN-035 faz o grid global ignorar o Status do POST,
        # o que esconderia o "Status: Em andamento" verificado abaixo.
        # RN-041 ampliada: Setor e Status mudam juntos (cascata) nesse
        # submit, entao cada um gera o seu proprio RegistroHistorico.
        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registros = RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id)
        # RN-052: Responsavel tambem muda (de Vazio para self.user) nesse
        # mesmo submit, gerando seu proprio registro (Setor + Status +
        # Responsavel).
        self.assertEqual(registros.count(), 3)
        for registro in registros:
            self.assertEqual(registro.tipo, 'sistema')
            self.assertIn("Antes:", registro.acao)

        registro_setor = registros.get(rotulo="Setor")
        self.assertIn(f"Setor: {self.setor.nome}", registro_setor.acao)
        self.assertEqual(registro_setor.valor_novo, self.setor.nome)
        self.assertEqual(registro_setor.valor_anterior, "Vazio")

        registro_status = registros.get(rotulo="Status")
        self.assertIn(f"Status: {self.status.nome}", registro_status.acao)
        self.assertEqual(registro_status.valor_novo, self.status.nome)
        self.assertEqual(registro_status.valor_anterior, "Vazio")

        registro_responsavel = registros.get(rotulo="Responsavel")
        self.assertEqual(registro_responsavel.valor_novo, self.user.username)
        self.assertEqual(registro_responsavel.valor_anterior, "Vazio")

    def test_reenviar_mesmo_setor_e_status_nao_duplica_historico(self):
        url = reverse('escola_rede_editar', args=[self.escola.pk, 're'])
        self.client.post(url, {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk})

        re = RedeExterna.objects.get(escola=self.escola)
        total_apos_primeira = RegistroHistorico.objects.filter(
            content_type=self._content_type_re(), object_id=re.id,
        ).count()

        self.client.post(url, {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk})

        total_apos_segunda = RegistroHistorico.objects.filter(
            content_type=self._content_type_re(), object_id=re.id,
        ).count()
        self.assertEqual(total_apos_primeira, total_apos_segunda)

    def test_alterar_so_status_gera_historico_so_com_status(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido QA")

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertIn(f"Status: {outro_status.nome}", registro.acao)
        self.assertNotIn("Setor:", registro.acao)

    def test_alterar_so_status_preenche_de_para_estruturado(self):
        """RN-041: quando so um dos tres campos (Setor/Status/Parceiro)
        muda no mesmo submit, o registro preenche rotulo/valor_anterior/
        valor_novo/setor_nome, alem de manter `acao`."""
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido Estruturado")

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.rotulo, "Status")
        self.assertEqual(registro.valor_anterior, self.status.nome)
        self.assertEqual(registro.valor_novo, outro_status.nome)
        self.assertEqual(registro.setor_nome, self.setor.nome)

    def test_alterar_setor_e_status_juntos_gera_um_registro_estruturado_por_campo(self):
        """RN-041 (ampliada): quando mais de um campo muda no mesmo submit
        (cascata Setor->Status), cada campo alterado gera o seu proprio
        RegistroHistorico estruturado — nao mais um unico registro com
        frase combinada. Os dois registros compartilham o mesmo instante
        (`data`) e o mesmo Setor capturado (`setor_nome`)."""
        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registros = RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id)
        # RN-052: Responsavel muda junto (de Vazio para self.user) neste
        # mesmo submit, entao tambem gera o seu proprio registro.
        self.assertEqual(registros.count(), 3)

        registro_setor = registros.get(rotulo="Setor")
        self.assertEqual(registro_setor.valor_anterior, "Vazio")
        self.assertEqual(registro_setor.valor_novo, self.setor.nome)
        self.assertEqual(registro_setor.setor_nome, self.setor.nome)

        registro_status = registros.get(rotulo="Status")
        self.assertEqual(registro_status.valor_anterior, "Vazio")
        self.assertEqual(registro_status.valor_novo, self.status.nome)
        self.assertEqual(registro_status.setor_nome, self.setor.nome)

        registro_responsavel = registros.get(rotulo="Responsavel")
        self.assertEqual(registro_responsavel.valor_anterior, "Vazio")
        self.assertEqual(registro_responsavel.valor_novo, self.user.username)

        self.assertEqual(registro_setor.data, registro_status.data)
        self.assertEqual(registro_setor.data, registro_responsavel.data)

    def test_modal_exibe_formato_de_para_para_registro_estruturado(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status,
            responsavel=self.user,
        )
        outro_status = SetorStatus.objects.create(setor=self.setor, nome="Concluido Modal")
        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': self.setor.pk, 'status': outro_status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertContains(response, "Status")
        self.assertContains(response, self.status.nome)
        self.assertContains(response, outro_status.nome)
        self.assertContains(response, self.setor.nome)

    def test_modal_mostra_traco_quando_registro_estruturado_sem_setor(self):
        """RN-041: Setor nao capturado nesse registro mostra "—", sem
        quebrar o layout."""
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        RegistroHistorico.objects.create(
            tipo='sistema', acao='Atualizado:\n• Setor: Setor X', rotulo='Setor',
            valor_anterior='Vazio', valor_novo='Setor X', setor_nome=None,
            content_type=self._content_type_re(), object_id=re.id,
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertContains(response, "—")

    def test_modal_de_historico_e_20_por_cento_mais_largo(self):
        """RN-041: modal de historico com 20% mais de largura em relacao
        ao tamanho anterior (590px -> ~710px)."""
        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, "max-w-[710px]")

    def test_modal_lista_historico_individual_do_re(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Comentario exclusivo do RE', usuario=self.user,
            content_type=self._content_type_re(), object_id=re.id,
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comentario exclusivo do RE")

    def test_modal_do_re_exibe_nome_do_autor_em_vez_do_email(self):
        """PO-080: card do historico mostra o nome da pessoa, sem o dominio
        do e-mail/AD (`item.usuario.email` trocado por
        `get_full_name|default:username`)."""
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        autor = get_user_model().objects.create_user(
            username="autor.re", email="autor.re@howbe.local", password="senha-segura",
            first_name="Autor", last_name="Historico",
        )
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Comentario com autor identificado', usuario=autor,
            content_type=self._content_type_re(), object_id=re.id,
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertContains(response, "Autor Historico")
        self.assertNotContains(response, "autor.re@howbe.local")

    def test_anexo_e_comentario_de_re_nao_aparecem_no_historico_do_ri(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        ri = RedeInterna.objects.create(escola=self.escola, processo=self.processo_ri)
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Somente do RE', usuario=self.user,
            content_type=self._content_type_re(), object_id=re.id,
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 'ri']))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Somente do RE")

    def test_post_no_modal_adiciona_comentario(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(
            reverse('escola_rede_historico', args=[self.escola.pk, 're']),
            {'descricao': 'Novo comentario pelo modal'},
        )

        self.assertEqual(response.status_code, 200)
        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.tipo, 'comentario')
        self.assertEqual(registro.acao, 'Novo comentario pelo modal')

    def test_post_no_modal_com_anexo_cria_tipo_anexo(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        arquivo = SimpleUploadedFile("nota.txt", b"conteudo", content_type="text/plain")

        response = self.client.post(
            reverse('escola_rede_historico', args=[self.escola.pk, 're']),
            {'arquivo': arquivo},
        )

        self.assertEqual(response.status_code, 200)
        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.tipo, 'anexo')

    def test_post_no_modal_vazio_mostra_erro_e_nao_cria_registro(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(reverse('escola_rede_historico', args=[self.escola.pk, 're']), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe um comentario")
        re = RedeExterna.objects.get(escola=self.escola)
        self.assertFalse(RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id).exists())

    def test_modal_404_quando_rede_ainda_nao_existe(self):
        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertEqual(response.status_code, 404)

    def test_modal_404_com_tipo_invalido(self):
        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 'xx']))

        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_permissao_e_bloqueado_no_modal(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-historico", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertEqual(response.status_code, 403)

    def test_historico_combinado_da_escola_mostra_re_e_ri_marcados_e_ordenados(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        ri = RedeInterna.objects.create(escola=self.escola, processo=self.processo_ri)
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Entrada do RE', usuario=self.user,
            content_type=self._content_type_re(), object_id=re.id,
        )
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Entrada do RI', usuario=self.user,
            content_type=ContentType.objects.get_for_model(RedeInterna), object_id=ri.id,
        )

        response = self.client.get(reverse('escola_historico', args=[self.escola.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Entrada do RE")
        self.assertContains(response, "Entrada do RI")

    def test_historico_combinado_funciona_mesmo_sem_ri_cadastrado(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(reverse('escola_historico', args=[self.escola.pk]))

        self.assertEqual(response.status_code, 200)

    def test_historico_combinado_inclui_registro_gravado_no_nivel_da_escola(self):
        """PO-066/RN-042: registro gravado direto no content_type da Escola
        (ex.: e-mail enviado a partir da tela da Escola) tambem aparece na
        visao combinada — e a mesma tela chamada de "Histórico da Escola"."""
        RegistroHistorico.objects.create(
            tipo='sistema', acao='E-mail enviado pela tela de Escola.', usuario=self.user,
            content_type=ContentType.objects.get_for_model(Escola), object_id=self.escola.id,
        )

        entradas = services.historico_combinado_escola(self.escola)

        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0].origem_tipo, 'escola')

        response = self.client.get(reverse('escola_historico', args=[self.escola.pk]))
        self.assertContains(response, 'E-mail enviado pela tela de Escola.')
        self.assertContains(response, 'ESCOLA')

    def test_historico_combinado_exibe_nome_do_autor_em_vez_do_email(self):
        """PO-080: mesmo padrao no historico combinado (Escola + RE + RI)."""
        autor = get_user_model().objects.create_user(
            username="autor.escola", email="autor.escola@howbe.local", password="senha-segura",
            first_name="Autor", last_name="Escola",
        )
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Comentario no nivel da Escola', usuario=autor,
            content_type=ContentType.objects.get_for_model(Escola), object_id=self.escola.id,
        )

        response = self.client.get(reverse('escola_historico', args=[self.escola.pk]))

        self.assertContains(response, "Autor Escola")
        self.assertNotContains(response, "autor.escola@howbe.local")


class EscolaRedeParceiroTests(TestCase):
    """PO-056/RN-030/ADR-018: Parceiro de RedeExterna/RedeInterna editavel
    somente na tela do Setor de negocio "Lastmile", via modal de selecao."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-parceiro-rede", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(
            jira_key="EACE-PARC", nome="Escola Parceiro", municipio="Recife", uf="PE",
        )
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        # Migration 0006 ja semeia Setor "Lastmile"/"Suprimentos" para o
        # Processo padrao de RE — get_or_create evita duplicidade
        # (escolas_setor.setor_unico_por_processo).
        self.setor_lastmile, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Lastmile")
        self.setor_suprimentos, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Suprimentos")

        self.parceiro = Partner.objects.create(
            nome_fantasia="Parceiro Recife", razao_social="Parceiro Recife LTDA",
            cnpj_cpf="99999999000199", status="ativo",
        )

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_parceiro_e_salvo_na_tela_do_setor_lastmile(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor_lastmile)

        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor_lastmile.pk, 'status': '',
                'parceiro': self.parceiro.pk, 'setor_atual': 'Lastmile',
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertEqual(re.parceiro, self.parceiro)
        self.assertContains(response, str(self.parceiro))
        self.assertContains(response, f'value="{self.parceiro.pk}"')

    def test_parceiro_e_ignorado_fora_da_tela_do_setor_lastmile(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor_suprimentos)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor_suprimentos.pk, 'status': '',
                'parceiro': self.parceiro.pk, 'setor_atual': 'Suprimentos',
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertIsNone(re.parceiro)

    def test_parceiro_e_ignorado_na_tela_global_mesmo_sem_setor_ainda(self):
        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {'setor': '', 'status': '', 'parceiro': self.parceiro.pk},
        )

        re = RedeExterna.objects.get(escola=self.escola)
        self.assertIsNone(re.parceiro)

    def test_botao_de_parceiro_so_aparece_na_tela_do_setor_lastmile(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor_lastmile)

        response_lastmile = self.client.get(reverse('setor_detail', args=['Lastmile']))
        self.assertContains(response_lastmile, f'id="parceiro-btn-re-{self.escola.pk}"')

        response_global = self.client.get(reverse('enderecos_lastmile'))
        self.assertNotContains(response_global, f'id="parceiro-btn-re-{self.escola.pk}"')

    def test_alterar_parceiro_gera_historico_com_antes_e_depois(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor_lastmile)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor_lastmile.pk, 'status': '',
                'parceiro': self.parceiro.pk, 'setor_atual': 'Lastmile',
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertIn(f"Parceiro: {self.parceiro}", registro.acao)
        self.assertIn("Antes:", registro.acao)

    def test_alterar_parceiro_preenche_de_para_estruturado(self):
        """RN-041: alteracao so de Parceiro (unico campo mudando no
        submit) preenche rotulo/valor_anterior/valor_novo/setor_nome."""
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor_lastmile)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 're']),
            {
                'setor': self.setor_lastmile.pk, 'status': '',
                'parceiro': self.parceiro.pk, 'setor_atual': 'Lastmile',
            },
        )

        re = RedeExterna.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.rotulo, "Parceiro")
        self.assertEqual(registro.valor_anterior, "Vazio")
        self.assertEqual(registro.valor_novo, str(self.parceiro))
        self.assertEqual(registro.setor_nome, "Lastmile")

    def test_modal_bloqueado_fora_da_tela_do_setor_lastmile(self):
        response = self.client.get(
            reverse('escola_rede_parceiro_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Suprimentos'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Setor Lastmile")
        self.assertNotContains(response, "Parceiro Recife")

    def test_modal_lista_parceiros_na_tela_do_setor_lastmile(self):
        response = self.client.get(
            reverse('escola_rede_parceiro_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Parceiro Recife")

    def test_modal_filtra_por_nome(self):
        outro_parceiro = Partner.objects.create(
            nome_fantasia="Outro Parceiro", razao_social="Outro Parceiro LTDA",
            cnpj_cpf="88888888000188", status="ativo",
        )

        response = self.client.get(
            reverse('escola_rede_parceiro_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', 'q': 'Recife'},
        )

        self.assertContains(response, "Parceiro Recife")
        self.assertNotContains(response, outro_parceiro.nome_fantasia)


class SeedStatusCotacaoLastmileTests(TestCase):
    """RN-044/ADR-026: migration 0016_seed_status_cotacao_lastmile garante
    que "Cotacao" existe como SetorStatus do Setor "Lastmile", nos
    Processos de RE e de RI (RN-025), sem exigir cadastro manual."""

    def test_status_cotacao_existe_para_re_e_ri_no_setor_lastmile(self):
        for nome_processo in [RedeExterna.NOME_PROCESSO_PADRAO, RedeInterna.NOME_PROCESSO_PADRAO]:
            processo = Processo.objects.get(nome=nome_processo)
            setor = Setor.objects.get(processo=processo, nome="Lastmile")
            self.assertTrue(SetorStatus.objects.filter(setor=setor, nome="Cotacao").exists())


class EscolaRedeCotacaoTests(TestCase):
    """PO-068/RN-044/ADR-026: modal de gestao de cotacao (N Parceiros
    candidatos, um vencedor) de RedeExterna/RedeInterna, disponivel so na
    Tela do Setor "Lastmile" com o RE/RI no Status "Cotacao"."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-cotacao", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-COT", nome="Escola Cotacao")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        # Migration 0016 ja semeia o Status "Cotacao" para o Setor "Lastmile"
        # do Processo padrao de RE — get_or_create evita duplicidade.
        self.setor_lastmile, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Lastmile")
        self.status_cotacao, _ = SetorStatus.objects.get_or_create(setor=self.setor_lastmile, nome="Cotacao")
        self.status_outro = SetorStatus.objects.create(setor=self.setor_lastmile, nome="Em andamento QA")

        self.re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor_lastmile, status=self.status_cotacao,
        )

        self.parceiro1 = Partner.objects.create(
            nome_fantasia="Parceiro Um", razao_social="Parceiro Um LTDA", cnpj_cpf="11111111000111", status="ativo",
        )
        self.parceiro2 = Partner.objects.create(
            nome_fantasia="Parceiro Dois", razao_social="Parceiro Dois LTDA", cnpj_cpf="22222222000122", status="ativo",
        )

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def _adicionar(self, parceiro, setor_atual="Lastmile"):
        return self.client.post(
            reverse('escola_rede_cotacao_adicionar', args=[self.escola.pk, 're']),
            {'parceiro': parceiro.pk, 'setor_atual': setor_atual},
        )

    def test_modal_bloqueado_fora_da_tela_do_setor_lastmile(self):
        response = self.client.get(
            reverse('escola_rede_cotacao_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Suprimentos'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Setor Lastmile")

    def test_modal_bloqueado_quando_status_nao_e_cotacao(self):
        self.re.status = self.status_outro
        self.re.save()

        response = self.client.get(
            reverse('escola_rede_cotacao_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile'},
        )
        self.assertContains(response, "Cotacao")

    def test_modal_disponivel_na_tela_do_setor_lastmile_com_status_cotacao(self):
        response = self.client.get(
            reverse('escola_rede_cotacao_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum candidato adicionado ainda")

    def test_tipo_mapa_calor_e_404_fora_do_escopo(self):
        response = self.client.get(
            reverse('escola_rede_cotacao_modal', args=[self.escola.pk, 'mc']),
            {'setor_atual': 'Lastmile'},
        )
        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_permissao_e_bloqueado(self):
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-cotacao", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.get(
            reverse('escola_rede_cotacao_modal', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile'},
        )
        self.assertEqual(response.status_code, 403)

    def test_adicionar_candidato_cria_em_cotacao(self):
        self._adicionar(self.parceiro1)

        candidato = CotacaoParceiro.objects.get(content_type=self._content_type_re(), object_id=self.re.id)
        self.assertEqual(candidato.parceiro, self.parceiro1)
        self.assertEqual(candidato.situacao, CotacaoParceiro.SITUACAO_EM_COTACAO)

    def test_adicionar_mesmo_parceiro_duas_vezes_nao_duplica(self):
        self._adicionar(self.parceiro1)
        self._adicionar(self.parceiro1)

        self.assertEqual(
            CotacaoParceiro.objects.filter(content_type=self._content_type_re(), object_id=self.re.id).count(), 1,
        )

    def test_adicionar_fora_da_tela_do_setor_lastmile_e_bloqueado(self):
        self._adicionar(self.parceiro1, setor_atual="Suprimentos")

        self.assertFalse(
            CotacaoParceiro.objects.filter(content_type=self._content_type_re(), object_id=self.re.id).exists()
        )

    def test_selecionar_candidato_move_demais_para_recusado(self):
        self._adicionar(self.parceiro1)
        self._adicionar(self.parceiro2)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)
        candidato2 = CotacaoParceiro.objects.get(parceiro=self.parceiro2)

        self.client.post(
            reverse('escola_rede_cotacao_selecionar', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        candidato1.refresh_from_db()
        candidato2.refresh_from_db()
        self.assertEqual(candidato1.situacao, CotacaoParceiro.SITUACAO_SELECIONADO)
        self.assertEqual(candidato2.situacao, CotacaoParceiro.SITUACAO_RECUSADO)

    def test_selecionar_candidato_preenche_parceiro_do_re(self):
        self._adicionar(self.parceiro1)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)

        self.client.post(
            reverse('escola_rede_cotacao_selecionar', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        self.re.refresh_from_db()
        self.assertEqual(self.re.parceiro, self.parceiro1)

    def test_selecionar_candidato_gera_historico_antes_depois(self):
        self._adicionar(self.parceiro1)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)

        self.client.post(
            reverse('escola_rede_cotacao_selecionar', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=self.re.id)
        self.assertEqual(registro.rotulo, "Parceiro")
        self.assertEqual(registro.valor_anterior, "Vazio")
        self.assertEqual(registro.valor_novo, str(self.parceiro1))

    def test_selecionar_nao_move_status_automaticamente(self):
        """RN-044/ADR-026: selecionar o vencedor nao dispara transicao
        automatica de Status — trocar de Status continua manual (RN-033)."""
        self._adicionar(self.parceiro1)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)

        self.client.post(
            reverse('escola_rede_cotacao_selecionar', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        self.re.refresh_from_db()
        self.assertEqual(self.re.status, self.status_cotacao)

    def test_remover_candidato_em_cotacao(self):
        self._adicionar(self.parceiro1)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)

        self.client.post(
            reverse('escola_rede_cotacao_remover', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        self.assertFalse(CotacaoParceiro.objects.filter(pk=candidato1.pk).exists())

    def test_remover_candidato_ja_selecionado_e_bloqueado(self):
        self._adicionar(self.parceiro1)
        candidato1 = CotacaoParceiro.objects.get(parceiro=self.parceiro1)
        self.client.post(
            reverse('escola_rede_cotacao_selecionar', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        response = self.client.post(
            reverse('escola_rede_cotacao_remover', args=[self.escola.pk, 're', candidato1.pk]),
            {'setor_atual': 'Lastmile'},
        )

        candidato1.refresh_from_db()
        self.assertEqual(candidato1.situacao, CotacaoParceiro.SITUACAO_SELECIONADO)
        self.assertContains(response, "já selecionado")

    def test_botao_de_cotacao_so_aparece_com_status_cotacao_na_tela_do_setor(self):
        response = self.client.get(reverse('setor_detail', args=['Lastmile']))
        self.assertContains(response, f"window.abrirCotacaoRede('re', {self.escola.pk})")

    def test_botao_de_cotacao_nao_aparece_com_outro_status(self):
        self.re.status = self.status_outro
        self.re.save()

        response = self.client.get(reverse('setor_detail', args=['Lastmile']))
        self.assertNotContains(response, f"window.abrirCotacaoRede('re', {self.escola.pk})")

    def test_botao_de_cotacao_nao_aparece_fora_da_tela_do_setor(self):
        response = self.client.get(reverse('enderecos_lastmile'))
        self.assertNotContains(response, f"window.abrirCotacaoRede('re', {self.escola.pk})")


class EscolaRedeCamposTests(TestCase):
    """PO-058/RN-032/ADR-019: modal de Campos personalizados (RN-031) no
    grid de Enderecos Lastmile, agrupados por Setor dono e editaveis
    somente no Setor da tela atual (mesma regra do Parceiro, RN-030)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-campos-rede", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-CAMPOS", nome="Escola Campos")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)

        self.campo_lastmile = Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Lastmile")
        self.campo_suprimentos = Campo.objects.create(
            nome="Categoria", tipo=Campo.TIPO_LISTA, setor_nome="Suprimentos", opcoes=["A", "B"],
        )

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_usuario_sem_permissao_e_bloqueado(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-campos-rede", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 're']))

        self.assertEqual(response.status_code, 403)

    def test_modal_404_quando_rede_ainda_nao_existe(self):
        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 're']))

        self.assertEqual(response.status_code, 404)

    def test_modal_404_com_tipo_invalido(self):
        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 'xx']))

        self.assertEqual(response.status_code, 404)

    def test_modal_mostra_campos_agrupados_por_setor(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Lastmile'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data de instalação")
        self.assertContains(response, "Categoria")
        self.assertContains(response, "Lastmile")
        self.assertContains(response, "Suprimentos")

    def test_salva_valor_do_campo_do_setor_atual(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_lastmile.pk}': '2026-08-10'},
        )

        self.assertEqual(response.status_code, 200)
        valor = CampoValor.objects.get(campo=self.campo_lastmile, content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(valor.valor, '2026-08-10')

    def test_valor_numerico_e_reexibido_com_ponto_decimal(self):
        """Regressao: LANGUAGE_CODE=pt-br faz o Django trocar o ponto por
        virgula ao exibir um float no template; um input type=number so
        aceita ponto, entao o navegador descartava o valor ja salvo e a
        pessoa via o campo "vazio" apos reabrir o modal."""
        campo_numero = Campo.objects.create(nome="Velocidade", tipo=Campo.TIPO_NUMERO, setor_nome="Lastmile")
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{campo_numero.pk}': '150'},
        )
        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Lastmile'},
        )

        self.assertContains(response, f'name="campo_{campo_numero.pk}" value="150.0"')
        self.assertNotContains(response, f'name="campo_{campo_numero.pk}" value="150,0"')

    def test_campo_de_outro_setor_e_ignorado_mesmo_enviado_no_post(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_suprimentos.pk}': 'A'},
        )

        self.assertFalse(
            CampoValor.objects.filter(campo=self.campo_suprimentos, content_type=self._content_type_re(), object_id=re.id).exists()
        )

    def test_lista_com_valor_fora_das_opcoes_nao_salva_e_mostra_erro(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Suprimentos', f'campo_{self.campo_suprimentos.pk}': 'Z'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "selecione uma das opcoes cadastradas")
        self.assertFalse(
            CampoValor.objects.filter(campo=self.campo_suprimentos, content_type=self._content_type_re(), object_id=re.id).exists()
        )

    def test_edicao_bloqueada_fora_da_tela_de_um_setor(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {f'campo_{self.campo_lastmile.pk}': '2026-08-10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CampoValor.objects.filter(campo=self.campo_lastmile, content_type=self._content_type_re(), object_id=re.id).exists()
        )


class RegistroHistoricoDeCampoTests(TestCase):
    """PO-064/RN-040: alteracao de CampoValor feita pela tela do grid de
    Enderecos Lastmile gera RegistroHistorico tipo sistema, com valor
    anterior/novo (RN-041: tambem estruturado em rotulo/valor_anterior/
    valor_novo/setor_nome)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-historico-campo", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-HIST-CAMPO", nome="Escola Historico Campo")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.campo_data = Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Lastmile")

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_alterar_campo_gera_historico_sistema_estruturado(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10'},
        )

        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.tipo, 'sistema')
        self.assertEqual(registro.rotulo, 'Data de instalação')
        self.assertEqual(registro.valor_anterior, '(vazio)')
        self.assertEqual(registro.valor_novo, '10/08/2026')
        self.assertEqual(registro.setor_nome, 'Lastmile')
        self.assertIn('Data de instalação', registro.acao)

    def test_primeiro_valor_sem_campovalor_anterior_registra_vazio(self):
        """RN-040: criacao do primeiro valor de um Campo (sem CampoValor
        anterior) registra "anterior: (vazio)"."""
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10'},
        )

        registro = RegistroHistorico.objects.get(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registro.valor_anterior, '(vazio)')

    def test_reenviar_mesmo_valor_nao_duplica_historico(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        url = reverse('escola_rede_campos', args=[self.escola.pk, 're'])
        dados = {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10'}

        self.client.post(url, dados)
        total_apos_primeira = RegistroHistorico.objects.filter(
            content_type=self._content_type_re(), object_id=re.id,
        ).count()

        self.client.post(url, dados)
        total_apos_segunda = RegistroHistorico.objects.filter(
            content_type=self._content_type_re(), object_id=re.id,
        ).count()

        self.assertEqual(total_apos_primeira, total_apos_segunda)

    def test_alterar_campo_de_outro_setor_nao_gera_historico_no_setor_atual(self):
        campo_suprimentos = Campo.objects.create(nome="Categoria", tipo=Campo.TIPO_TEXTO, setor_nome="Suprimentos")
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{campo_suprimentos.pk}': 'A'},
        )

        self.assertFalse(RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id).exists())

    def test_alterar_campo_base_de_calculado_embute_valor_calculado_no_mesmo_registro(self):
        """RN-040: quando o Campo alterado e `campo_base` de um Campo
        Calculado (RN-039), o MESMO registro de historico tambem traz o
        valor calculado resultante — sem RegistroHistorico separado para o
        Calculado (que nunca tem CampoValor proprio)."""
        campo_final = Campo.objects.create(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Lastmile",
            campo_base=self.campo_data, horas_prazo=72,
        )
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10'},
        )

        registros = RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registros.count(), 1)
        registro = registros.get()
        self.assertEqual(registro.rotulo, 'Data de instalação')
        self.assertIn('Data Final Implantação: 13/08/2026', registro.valor_novo)
        self.assertFalse(CampoValor.objects.filter(campo=campo_final).exists())

    def test_campo_calculado_nunca_gera_historico_proprio(self):
        campo_final = Campo.objects.create(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Lastmile",
            campo_base=self.campo_data, horas_prazo=72,
        )
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10', f'campo_{campo_final.pk}': '2099-01-01'},
        )

        registros = RegistroHistorico.objects.filter(content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(registros.count(), 1)
        self.assertNotEqual(registros.get().rotulo, 'Data Final Implantação')

    def test_historico_do_campo_aparece_no_modal_de_historico(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_data.pk}': '2026-08-10'},
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertContains(response, 'Data de instalação')
        self.assertContains(response, '10/08/2026')
        self.assertContains(response, 'Lastmile')


class SetorEscopoFiltraCamposDeRedeTests(TestCase):
    """PO-062/RN-037/ADR-022: Campo cujo Setor tem escopo "Escola", ou
    "Sub-atividades" sem aplicar aquele tipo (RE/RI), sai do modal de
    Campos de RE/RI (RN-032). Setor sem SetorEscopo mantem o comportamento
    legado (Sub-atividades: RE e RI)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-escopo-rede", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-ESCOPO", nome="Escola Escopo")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.campo_lastmile = Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Lastmile")

    def test_campo_sem_setorescopo_aparece_normalmente_no_modal_de_re(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 're']))

        self.assertContains(response, "Data de instalação")

    def test_campo_com_escopo_escola_nao_aparece_no_modal_de_re(self):
        SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 're']))

        self.assertNotContains(response, "Data de instalação")

    def test_campo_com_sub_atividades_somente_ri_nao_aparece_no_modal_de_re(self):
        SetorEscopo.objects.create(
            setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES, aplica_re=False, aplica_ri=True,
        )
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 're']))

        self.assertNotContains(response, "Data de instalação")

    def test_campo_com_sub_atividades_somente_ri_aparece_no_modal_de_ri(self):
        SetorEscopo.objects.create(
            setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES, aplica_re=False, aplica_ri=True,
        )
        processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        RedeInterna.objects.create(escola=self.escola, processo=processo_ri)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 'ri']))

        self.assertContains(response, "Data de instalação")

    def test_salvar_bloqueado_quando_setor_atual_tem_escopo_escola(self):
        SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Lastmile', f'campo_{self.campo_lastmile.pk}': '2026-08-10'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CampoValor.objects.filter(
                campo=self.campo_lastmile, content_type=ContentType.objects.get_for_model(RedeExterna), object_id=re.id,
            ).exists()
        )


class CampoCondicionadoEStatusECalculadoTests(TestCase):
    """PO-063/RN-039/ADR-024: Campo com Status condicionante so aparece no
    modal (RN-032) quando o Status atual do RE bate; Campo tipo Calculado
    nunca e editavel e tem o valor derivado ao vivo do Campo base (dias
    corridos equivalentes as Horas de prazo, arredondado para cima)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-campo-calculado", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-CALC", nome="Escola Calculado")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        # PO-050 (migration 0006) ja semeia um Setor "Implantacao" para este
        # Processo — reaproveita em vez de criar (colidiria com a
        # UniqueConstraint setor_unico_por_processo).
        self.setor, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Implantacao")
        self.status_agendando = SetorStatus.objects.create(setor=self.setor, nome="Agendando Parceiro")
        self.status_outro = SetorStatus.objects.create(setor=self.setor, nome="Outro Status")

        self.campo_inicio = Campo.objects.create(
            nome="Início Implantação", tipo=Campo.TIPO_DATA, setor_nome="Implantacao",
            status_condicionante_nome="Agendando Parceiro",
        )
        self.campo_final = Campo.objects.create(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=self.campo_inicio, horas_prazo=72,
        )

    def _content_type_re(self):
        return ContentType.objects.get_for_model(RedeExterna)

    def test_campo_condicionado_nao_aparece_com_status_diferente(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_outro)

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertNotContains(response, "Início Implantação")

    def test_campo_condicionado_aparece_com_status_igual(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertContains(response, "Início Implantação")

    def test_campo_condicionado_nao_aparece_sem_status(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re, setor=self.setor)

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertNotContains(response, "Início Implantação")

    def test_campo_calculado_em_branco_quando_base_sem_valor(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertContains(response, "Data Final Implantação")
        self.assertContains(response, f'name="campo_{self.campo_final.pk}" value=""')

    def test_campo_calculado_soma_72_horas_como_3_dias_corridos(self):
        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )
        CampoValor.objects.create(
            campo=self.campo_inicio, content_type=self._content_type_re(), object_id=re.id, valor="2026-08-10",
        )

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertContains(response, f'name="campo_{self.campo_final.pk}" value="2026-08-13"')

    def test_campo_calculado_arredonda_horas_nao_multiplas_de_24_para_cima(self):
        campo_curto = Campo.objects.create(
            nome="Prazo curto", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=self.campo_inicio, horas_prazo=25,
        )
        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )
        CampoValor.objects.create(
            campo=self.campo_inicio, content_type=self._content_type_re(), object_id=re.id, valor="2026-08-10",
        )

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )

        self.assertContains(response, f'name="campo_{campo_curto.pk}" value="2026-08-12"')

    def test_campo_calculado_e_sempre_somente_leitura_mesmo_no_setor_atual(self):
        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )

        response = self.client.get(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']), {'setor_atual': 'Implantacao'},
        )
        content = response.content.decode()

        self.assertIn(f'name="campo_{self.campo_final.pk}"', content)
        idx = content.index(f'name="campo_{self.campo_final.pk}"')
        trecho_input = content[max(0, idx - 20):idx + 200]
        self.assertIn("disabled", trecho_input)

    def test_campo_calculado_nunca_e_gravado_mesmo_enviado_no_post(self):
        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Implantacao', f'campo_{self.campo_final.pk}': '2099-01-01'},
        )

        self.assertFalse(
            CampoValor.objects.filter(campo=self.campo_final, content_type=self._content_type_re(), object_id=re.id).exists()
        )

    def test_campo_condicionado_ignora_valor_enviado_no_post_quando_status_diferente(self):
        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_outro,
        )

        self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Implantacao', f'campo_{self.campo_inicio.pk}': '2026-08-10'},
        )

        self.assertFalse(
            CampoValor.objects.filter(campo=self.campo_inicio, content_type=self._content_type_re(), object_id=re.id).exists()
        )

    def test_campo_condicionado_salva_valor_quando_status_igual(self):
        re = RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=self.setor, status=self.status_agendando,
        )

        response = self.client.post(
            reverse('escola_rede_campos', args=[self.escola.pk, 're']),
            {'setor_atual': 'Implantacao', f'campo_{self.campo_inicio.pk}': '2026-08-10'},
        )

        self.assertEqual(response.status_code, 200)
        valor = CampoValor.objects.get(campo=self.campo_inicio, content_type=self._content_type_re(), object_id=re.id)
        self.assertEqual(valor.valor, '2026-08-10')


class EscolaCamposTests(TestCase):
    """PO-062/RN-037/ADR-022: modal de Campos com escopo "Escola" na linha
    da Escola (grid de Enderecos Lastmile) — sem trava por setor_atual."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-campos-escola", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-CAMPOS-ESCOLA", nome="Escola Campos Escola")
        self.campo_escola = Campo.objects.create(nome="CNPJ do cliente", tipo=Campo.TIPO_TEXTO, setor_nome="Comercial")
        SetorEscopo.objects.create(setor_nome="Comercial", atividade=SetorEscopo.ATIVIDADE_ESCOLA)

        self.campo_rede = Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Lastmile")

    def _content_type_escola(self):
        return ContentType.objects.get_for_model(Escola)

    def test_usuario_sem_permissao_e_bloqueado(self):
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-campos-escola", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))

        self.assertEqual(response.status_code, 403)

    def test_modal_mostra_somente_campos_com_escopo_escola(self):
        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CNPJ do cliente")
        self.assertNotContains(response, "Data de instalação")

    def test_modal_mostra_dados_tecnicos_eace_somente_leitura(self):
        """RN-057/ADR-029/PO-076: Velocidade Minima, Kit Inicial e TARGET
        EACE aparecem no modal de Campos da Escola, sempre somente leitura
        — nao passam pelo mecanismo de Campo/CampoValor (RN-031/038 nao se
        aplica, pois variam por Escola)."""
        self.escola.velocidade_dl_minima = 100
        self.escola.kit_inicial = 2
        self.escola.uf = "SP"
        self.escola.save()
        TargetRedeExterna.objects.create(uf="SP", velocidade_mbps=100, valor="543.21")

        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))
        content = response.content.decode()

        self.assertContains(response, "Dados Técnicos EACE")
        self.assertContains(response, "Velocidade Mínima")
        self.assertIn("100 Mbps", content)
        self.assertContains(response, "Kit Inicial")
        self.assertContains(response, "TARGET EACE")
        self.assertIn("543.21", content)
        # somente leitura: nao pode haver input/select editavel para estes 3 dados
        self.assertNotIn('name="velocidade_dl_minima"', content)
        self.assertNotIn('name="kit_inicial"', content)
        self.assertNotIn('name="target_eace"', content)

    def test_modal_mostra_dados_tecnicos_eace_em_branco_sem_correspondencia(self):
        """Sem Velocidade Minima/UF cadastrados, ou sem combinacao exata na
        tabela de referencia, os 3 campos ficam em branco (nunca inventados
        ou aproximados)."""
        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))

        self.assertContains(response, "Não informado")

    def test_salva_valor_do_campo_com_escopo_escola(self):
        response = self.client.post(
            reverse('escola_campos', args=[self.escola.pk]),
            {f'campo_{self.campo_escola.pk}': '12.345.678/0001-90'},
        )

        self.assertEqual(response.status_code, 200)
        valor = CampoValor.objects.get(campo=self.campo_escola, content_type=self._content_type_escola(), object_id=self.escola.id)
        self.assertEqual(valor.valor, '12.345.678/0001-90')

    def test_sem_campo_de_escopo_escola_mostra_erro_ao_salvar(self):
        SetorEscopo.objects.filter(setor_nome="Comercial").delete()

        response = self.client.post(
            reverse('escola_campos', args=[self.escola.pk]),
            {f'campo_{self.campo_escola.pk}': 'valor qualquer'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum campo com escopo Escola cadastrado")
        self.assertFalse(CampoValor.objects.filter(campo=self.campo_escola).exists())

    def test_campo_com_status_condicionante_nunca_aparece_no_modal_da_escola(self):
        """PO-063/RN-039: Escola nao tem Status (exclusivo de RE/RI,
        RN-026) — um Campo com Status condicionante nunca aparece aqui,
        mesmo com escopo Escola."""
        campo_condicionado = Campo.objects.create(
            nome="Campo condicionado", tipo=Campo.TIPO_TEXTO, setor_nome="Comercial",
            status_condicionante_nome="Qualquer Status",
        )

        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))

        self.assertNotContains(response, "Campo condicionado")

        self.client.post(reverse('escola_campos', args=[self.escola.pk]), {f'campo_{campo_condicionado.pk}': 'valor'})
        self.assertFalse(CampoValor.objects.filter(campo=campo_condicionado).exists())

    def test_campo_calculado_com_escopo_escola_e_derivado_e_somente_leitura(self):
        """PO-063/RN-039: Campo tipo Calculado tambem funciona no modal da
        Escola (RN-037), com o mesmo mecanismo generico usado no de RE/RI."""
        campo_base_data = Campo.objects.create(nome="Data base", tipo=Campo.TIPO_DATA, setor_nome="Comercial")
        campo_calculado = Campo.objects.create(
            nome="Data final calculada", tipo=Campo.TIPO_CALCULADO, setor_nome="Comercial",
            campo_base=campo_base_data, horas_prazo=48,
        )
        CampoValor.objects.create(
            campo=campo_base_data, content_type=self._content_type_escola(), object_id=self.escola.id, valor="2026-08-10",
        )

        response = self.client.get(reverse('escola_campos', args=[self.escola.pk]))
        content = response.content.decode()

        self.assertIn(f'name="campo_{campo_calculado.pk}" value="2026-08-12"', content)
        idx = content.index(f'name="campo_{campo_calculado.pk}"')
        self.assertIn("disabled", content[idx:idx + 200])

    def test_alterar_campo_da_escola_gera_historico_sistema_estruturado(self):
        """PO-064/RN-040: alteracao de Campo com escopo Escola tambem gera
        RegistroHistorico, mesmo padrao usado no grid de RE/RI."""
        self.client.post(
            reverse('escola_campos', args=[self.escola.pk]),
            {f'campo_{self.campo_escola.pk}': '12.345.678/0001-90'},
        )

        registro = RegistroHistorico.objects.get(content_type=self._content_type_escola(), object_id=self.escola.id)
        self.assertEqual(registro.tipo, 'sistema')
        self.assertEqual(registro.rotulo, 'CNPJ do cliente')
        self.assertEqual(registro.valor_anterior, '(vazio)')
        self.assertEqual(registro.valor_novo, '12.345.678/0001-90')
        self.assertEqual(registro.setor_nome, 'Comercial')

    def test_reenviar_mesmo_valor_na_escola_nao_duplica_historico(self):
        url = reverse('escola_campos', args=[self.escola.pk])
        dados = {f'campo_{self.campo_escola.pk}': '12.345.678/0001-90'}

        self.client.post(url, dados)
        total_apos_primeira = RegistroHistorico.objects.filter(
            content_type=self._content_type_escola(), object_id=self.escola.id,
        ).count()

        self.client.post(url, dados)
        total_apos_segunda = RegistroHistorico.objects.filter(
            content_type=self._content_type_escola(), object_id=self.escola.id,
        ).count()

        self.assertEqual(total_apos_primeira, total_apos_segunda)


class SetoresViewsTests(TestCase):
    """PO-052/ADR-016: visao por Setor (nome), cruzando RE e RI de qualquer
    Processo que compartilhe aquele nome de Setor."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-setores", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.setor_re = Setor.objects.create(processo=self.processo_re, nome="Setor QA Comum")
        self.setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor QA Comum")
        self.status_re = SetorStatus.objects.create(setor=self.setor_re, nome="Em andamento")

    def test_setores_list_mostra_nomes_cadastrados(self):
        response = self.client.get(reverse('setores_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Setor QA Comum")

    def test_setor_detail_agrupa_re_e_ri_de_processos_diferentes_pelo_mesmo_nome(self):
        escola_re = Escola.objects.create(jira_key="EACE-SETOR-RE", nome="Escola RE")
        escola_ri = Escola.objects.create(jira_key="EACE-SETOR-RI", nome="Escola RI")
        RedeExterna.objects.create(escola=escola_re, processo=self.processo_re, setor=self.setor_re, status=self.status_re)
        RedeInterna.objects.create(escola=escola_ri, processo=self.processo_ri, setor=self.setor_ri)

        response = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escola RE")
        self.assertContains(response, "Escola RI")
        self.assertContains(response, "Em andamento")

    def test_setor_detail_nao_mostra_atividade_de_outro_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Diferente")
        escola = Escola.objects.create(jira_key="EACE-OUTRO", nome="Escola Outro Setor")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=outro_setor)

        response = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertNotContains(response, "Escola Outro Setor")

    def test_setor_detail_mostra_so_a_subatividade_que_bate_com_o_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_ri, nome="Setor QA Diferente")
        escola = Escola.objects.create(jira_key="EACE-MISTA", nome="Escola Mista")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=outro_setor)

        response = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertContains(response, "Escola Mista")
        self.assertContains(response, 'id="setor-select-re-')
        self.assertNotContains(response, 'id="setor-select-ri-')

    def test_enderecos_lastmile_view_global_mostra_re_e_ri_mesmo_com_setores_diferentes(self):
        outro_setor = Setor.objects.create(processo=self.processo_ri, nome="Setor QA Diferente")
        escola = Escola.objects.create(jira_key="EACE-MISTA-2", nome="Escola Mista Global")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=outro_setor)

        response = self.client.get(reverse('enderecos_lastmile'))

        # Ja atribuidos a um Setor: aparecem somente-leitura na tela global
        # (RN-029) — o RE/RI so e editavel na tela do proprio Setor.
        self.assertContains(response, f'id="rede-re-{escola.pk}"')
        self.assertContains(response, f'id="rede-ri-{escola.pk}"')
        self.assertContains(response, "Ver Setor", count=2)
        self.assertContains(response, reverse('setor_detail', args=[self.setor_re.nome]))
        self.assertContains(response, reverse('setor_detail', args=[outro_setor.nome]))

    def test_setor_detail_nome_inexistente_404(self):
        response = self.client.get(reverse('setor_detail', args=['Nao Existe']))

        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_permissao_e_bloqueado(self):
        sem_permissao = get_user_model().objects.create_user(username="sem-permissao-setores", password="senha-segura")
        self.client.force_login(sem_permissao)

        response = self.client.get(reverse('setores_list'))

        self.assertEqual(response.status_code, 403)

    def test_grupo_lastmile_nao_da_mais_acesso_ao_modulo_setores(self):
        """RN-054: o modulo Setores deixa de depender do grupo LastMile."""
        usuario_lastmile = get_user_model().objects.create_user(username="lastmile-sem-setor", password="senha-segura")
        usuario_lastmile.groups.add(Group.objects.create(name="LastMile"))
        self.client.force_login(usuario_lastmile)

        response_lista = self.client.get(reverse('setores_list'))
        response_detalhe = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertEqual(response_lista.status_code, 403)
        self.assertEqual(response_detalhe.status_code, 403)

    def test_usuario_grupo_setor_sem_concessao_nao_ve_nenhum_nome(self):
        """RN-055: grupo Setor, sozinho, nao concede nenhum nome."""
        usuario_setor = get_user_model().objects.create_user(username="setor-sem-concessao", password="senha-segura")
        usuario_setor.groups.add(Group.objects.create(name="Setor"))
        self.client.force_login(usuario_setor)

        response = self.client.get(reverse('setores_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Setor QA Comum")

    def test_usuario_grupo_setor_ve_somente_nomes_concedidos(self):
        """RN-055: usuario ve a intersecao entre catalogo e concessao, nao todo o catalogo."""
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor QA Diferente")
        usuario_setor = get_user_model().objects.create_user(username="setor-com-concessao", password="senha-segura")
        usuario_setor.groups.add(Group.objects.create(name="Setor"))
        AcessoSetor.objects.create(usuario=usuario_setor, setor_nome="Setor QA Comum")
        self.client.force_login(usuario_setor)

        response = self.client.get(reverse('setores_list'))

        self.assertContains(response, "Setor QA Comum")
        self.assertNotContains(response, outro_setor.nome)

    def test_setor_detail_403_para_nome_nao_concedido_mesmo_existindo_e_no_grupo_setor(self):
        """RN-055: nome existente no catalogo, usuario no grupo Setor, mas sem concessao -> 403."""
        usuario_setor = get_user_model().objects.create_user(username="setor-nao-concedido", password="senha-segura")
        usuario_setor.groups.add(Group.objects.create(name="Setor"))
        self.client.force_login(usuario_setor)

        response = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertEqual(response.status_code, 403)

    def test_setor_detail_ok_para_nome_concedido_ao_usuario_do_grupo_setor(self):
        usuario_setor = get_user_model().objects.create_user(username="setor-concedido", password="senha-segura")
        usuario_setor.groups.add(Group.objects.create(name="Setor"))
        AcessoSetor.objects.create(usuario=usuario_setor, setor_nome="Setor QA Comum")
        self.client.force_login(usuario_setor)

        response = self.client.get(reverse('setor_detail', args=['Setor QA Comum']))

        self.assertEqual(response.status_code, 200)


class CardReRiPorSetorTests(TestCase):
    """RN-065: card com quantidade de RE e RI vinculadas ao Setor, exibido
    somente na tela de Setor (`setor_detail`), respeitando os filtros de
    busca da propria tela."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-re-ri-setor", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)
        self.setor_re = Setor.objects.create(processo=self.processo_re, nome="Setor RN065")
        self.setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RN065")
        self.setor_mc = Setor.objects.create(processo=self.processo_mc, nome="Setor RN065")
        self.status_concluido = SetorStatus.objects.create(setor=self.setor_re, nome="Concluido")

    def test_card_conta_re_e_ri_de_forma_bruta_sem_filtrar_por_status(self):
        escola_re_1 = Escola.objects.create(jira_key="EACE-RN065-RE1", nome="Escola RE Um")
        escola_re_2 = Escola.objects.create(jira_key="EACE-RN065-RE2", nome="Escola RE Dois")
        escola_ri_1 = Escola.objects.create(jira_key="EACE-RN065-RI1", nome="Escola RI Um")
        RedeExterna.objects.create(
            escola=escola_re_1, processo=self.processo_re, setor=self.setor_re, status=self.status_concluido,
        )
        RedeExterna.objects.create(escola=escola_re_2, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola_ri_1, processo=self.processo_ri, setor=self.setor_ri)

        response = self.client.get(reverse('setor_detail', args=['Setor RN065']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_rede_externa'], 2)
        self.assertEqual(response.context['total_rede_interna'], 1)
        self.assertContains(response, '>RE</p>')
        self.assertContains(response, '>RI</p>')

    def test_card_respeita_filtro_de_busca_da_tela(self):
        escola_re_1 = Escola.objects.create(jira_key="EACE-RN065-BUSCA1", nome="Escola Alpha RN065")
        escola_re_2 = Escola.objects.create(jira_key="EACE-RN065-BUSCA2", nome="Escola Beta RN065")
        RedeExterna.objects.create(escola=escola_re_1, processo=self.processo_re, setor=self.setor_re)
        RedeExterna.objects.create(escola=escola_re_2, processo=self.processo_re, setor=self.setor_re)

        response_sem_filtro = self.client.get(reverse('setor_detail', args=['Setor RN065']))
        response_filtrado = self.client.get(reverse('setor_detail', args=['Setor RN065']), {'q': 'Alpha'})

        self.assertEqual(response_sem_filtro.context['total_rede_externa'], 2)
        self.assertEqual(response_filtrado.context['total_rede_externa'], 1)

    def test_mapa_calor_nunca_entra_na_contagem(self):
        escola = Escola.objects.create(jira_key="EACE-RN065-MC", nome="Escola Mapa Calor RN065")
        MapaCalor.objects.create(escola=escola, processo=self.processo_mc, setor=self.setor_mc)

        response = self.client.get(reverse('setor_detail', args=['Setor RN065']))

        self.assertContains(response, "Escola Mapa Calor RN065")
        self.assertEqual(response.context['total_rede_externa'], 0)
        self.assertEqual(response.context['total_rede_interna'], 0)

    def test_card_nao_aparece_no_grid_global_de_enderecos_lastmile(self):
        escola = Escola.objects.create(jira_key="EACE-RN065-GLOBAL", nome="Escola Global RN065")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '>RE</p>')
        self.assertNotContains(response, '>RI</p>')

    def test_contagem_nao_gera_consulta_extra_por_escola(self):
        """A contagem e agregada numa unica consulta (CLAUDE.md secao 7) —
        aumentar o numero de escolas vinculadas ao Setor nao pode aumentar
        o numero de consultas da tela."""
        for indice in range(3):
            escola = Escola.objects.create(jira_key=f"EACE-RN065-N1-{indice}", nome=f"Escola N1 {indice}")
            RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re)

        with CaptureQueriesContext(connection) as poucas_escolas:
            self.client.get(reverse('setor_detail', args=['Setor RN065']))

        for indice in range(3, 18):
            escola = Escola.objects.create(jira_key=f"EACE-RN065-N1-{indice}", nome=f"Escola N1 {indice}")
            RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re)

        with CaptureQueriesContext(connection) as muitas_escolas:
            self.client.get(reverse('setor_detail', args=['Setor RN065']))

        self.assertEqual(len(poucas_escolas.captured_queries), len(muitas_escolas.captured_queries))


class EscolaSomeDoSetorQuandoConcluidaTests(TestCase):
    """RN-063: nas telas de Setor "Implantacao"/"Qualidade", a Escola some
    da listagem quando RE/RI vinculados aquele Setor especifico estao
    "Concluido" — avaliado por Setor, sem afetar o grid global nem os
    demais Setores."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-rn063", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        # "Implantacao"/"Suprimentos" ja vem semeados (migrations 0006/0014,
        # RN-025) para os Processos padrao de RE/RI/MC — get_or_create evita
        # colidir com a unique constraint (processo, nome) do Setor.
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)

        self.implantacao_re, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Implantacao")
        self.implantacao_ri, _ = Setor.objects.get_or_create(processo=self.processo_ri, nome="Implantacao")
        self.implantacao_mc, _ = Setor.objects.get_or_create(processo=self.processo_mc, nome="Implantacao")
        self.suprimentos_ri, _ = Setor.objects.get_or_create(processo=self.processo_ri, nome="Suprimentos")

        self.concluido_re, _ = SetorStatus.objects.get_or_create(setor=self.implantacao_re, nome="Concluido")
        self.concluido_ri, _ = SetorStatus.objects.get_or_create(setor=self.implantacao_ri, nome="Concluido")
        self.andamento_implantacao_ri, _ = SetorStatus.objects.get_or_create(setor=self.implantacao_ri, nome="Em andamento")
        self.andamento_ri, _ = SetorStatus.objects.get_or_create(setor=self.suprimentos_ri, nome="Em andamento")

    def test_escola_some_do_setor_implantacao_quando_re_e_ri_concluidos(self):
        escola = Escola.objects.create(jira_key="EACE-RN063-1", nome="Escola Concluida")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.implantacao_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.implantacao_ri, status=self.concluido_ri)

        response = self.client.get(reverse('setor_detail', args=['Implantacao']))

        self.assertNotContains(response, "Escola Concluida")

    def test_escola_continua_no_setor_implantacao_com_uma_subatividade_pendente(self):
        escola = Escola.objects.create(jira_key="EACE-RN063-2", nome="Escola Parcial")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.implantacao_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.implantacao_ri, status=self.andamento_implantacao_ri)

        response = self.client.get(reverse('setor_detail', args=['Implantacao']))

        self.assertContains(response, "Escola Parcial")

    def test_escola_some_do_setor_individualmente_mesmo_com_a_outra_subatividade_ativa_em_outro_setor(self):
        escola = Escola.objects.create(jira_key="EACE-RN063-3", nome="Escola Mista Concluida")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.implantacao_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.suprimentos_ri, status=self.andamento_ri)

        response_implantacao = self.client.get(reverse('setor_detail', args=['Implantacao']))
        response_suprimentos = self.client.get(reverse('setor_detail', args=['Suprimentos']))

        # RE concluido dentro de Implantacao: some de la, mesmo com RI ainda
        # ativo em Suprimentos — avaliacao e por Setor, individualmente.
        self.assertNotContains(response_implantacao, "Escola Mista Concluida")
        # Suprimentos nao esta em SETORES_OCULTAM_ESCOLA_CONCLUIDA: continua
        # mostrando a escola normalmente.
        self.assertContains(response_suprimentos, "Escola Mista Concluida")

    def test_escola_so_com_mapa_calor_no_setor_implantacao_nao_e_afetada(self):
        escola = Escola.objects.create(jira_key="EACE-RN063-4", nome="Escola So Mapa Calor")
        MapaCalor.objects.create(escola=escola, processo=self.processo_mc, setor=self.implantacao_mc)

        response = self.client.get(reverse('setor_detail', args=['Implantacao']))

        self.assertContains(response, "Escola So Mapa Calor")

    def test_setor_fora_da_regra_continua_mostrando_escola_concluida(self):
        suprimentos_re, _ = Setor.objects.get_or_create(processo=self.processo_re, nome="Suprimentos")
        concluido_suprimentos, _ = SetorStatus.objects.get_or_create(setor=suprimentos_re, nome="Concluido")
        escola = Escola.objects.create(jira_key="EACE-RN063-5", nome="Escola Concluida Fora Da Regra")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=suprimentos_re, status=concluido_suprimentos)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.suprimentos_ri, status=self.andamento_ri)

        response = self.client.get(reverse('setor_detail', args=['Suprimentos']))

        self.assertContains(response, "Escola Concluida Fora Da Regra")

    def test_escola_concluida_em_implantacao_continua_no_grid_global(self):
        escola = Escola.objects.create(jira_key="EACE-RN063-6", nome="Escola Concluida Grid Global")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.implantacao_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.implantacao_ri, status=self.concluido_ri)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, "Escola Concluida Grid Global")

    def test_regra_roda_por_nome_mesmo_para_setor_qualidade_ainda_nao_seedado(self):
        qualidade_re = Setor.objects.create(processo=self.processo_re, nome="Qualidade")
        concluido_qualidade = SetorStatus.objects.create(setor=qualidade_re, nome="Concluido")
        escola = Escola.objects.create(jira_key="EACE-RN063-7", nome="Escola Concluida Qualidade")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=qualidade_re, status=concluido_qualidade)

        response = self.client.get(reverse('setor_detail', args=['Qualidade']))

        self.assertNotContains(response, "Escola Concluida Qualidade")


class FiltrosTelaSetorTests(TestCase):
    """RN-066: filtros de tipo de subatividade (RE/RI/Mapa Calor),
    Responsavel e Status, exclusivos da Tela de Setor (`setor_detail`) —
    nao aparecem no grid global de Enderecos Lastmile."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-rn066", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)
        self.processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)

        self.setor_re = Setor.objects.create(processo=self.processo_re, nome="Setor RN066")
        self.setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RN066")
        self.setor_mc = Setor.objects.create(processo=self.processo_mc, nome="Setor RN066")

        self.status_a = SetorStatus.objects.create(setor=self.setor_re, nome="Aguardando material")
        self.status_b = SetorStatus.objects.create(setor=self.setor_re, nome="Em campo")

        self.joao = get_user_model().objects.create_user(username="joao-rn066", password="senha-segura")
        self.maria = get_user_model().objects.create_user(username="maria-rn066", password="senha-segura")

    def test_filtro_tipo_restringe_a_escolas_com_aquele_tipo_neste_setor(self):
        escola_re = Escola.objects.create(jira_key="EACE-RN066-1", nome="Escola So RE")
        escola_ri = Escola.objects.create(jira_key="EACE-RN066-2", nome="Escola So RI")
        RedeExterna.objects.create(escola=escola_re, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola_ri, processo=self.processo_ri, setor=self.setor_ri)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'tipo': 're'})

        self.assertContains(response, "Escola So RE")
        self.assertNotContains(response, "Escola So RI")

    def test_filtro_tipo_multiplo_e_or_entre_os_tipos_marcados(self):
        escola_re = Escola.objects.create(jira_key="EACE-RN066-3", nome="Escola RE Multi")
        escola_ri = Escola.objects.create(jira_key="EACE-RN066-4", nome="Escola RI Multi")
        escola_mc = Escola.objects.create(jira_key="EACE-RN066-5", nome="Escola MC Multi")
        RedeExterna.objects.create(escola=escola_re, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola_ri, processo=self.processo_ri, setor=self.setor_ri)
        MapaCalor.objects.create(escola=escola_mc, processo=self.processo_mc, setor=self.setor_mc)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'tipo': ['re', 'ri']})

        self.assertContains(response, "Escola RE Multi")
        self.assertContains(response, "Escola RI Multi")
        self.assertNotContains(response, "Escola MC Multi")

    def test_sem_tipo_marcado_mantem_comportamento_atual(self):
        escola_re = Escola.objects.create(jira_key="EACE-RN066-6", nome="Escola RE Sem Filtro")
        escola_ri = Escola.objects.create(jira_key="EACE-RN066-7", nome="Escola RI Sem Filtro")
        RedeExterna.objects.create(escola=escola_re, processo=self.processo_re, setor=self.setor_re)
        RedeInterna.objects.create(escola=escola_ri, processo=self.processo_ri, setor=self.setor_ri)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']))

        self.assertContains(response, "Escola RE Sem Filtro")
        self.assertContains(response, "Escola RI Sem Filtro")

    def test_filtro_responsavel_restringe_as_escolas_com_aquele_responsavel_neste_setor(self):
        escola_joao = Escola.objects.create(jira_key="EACE-RN066-8", nome="Escola Do Joao")
        escola_maria = Escola.objects.create(jira_key="EACE-RN066-9", nome="Escola Da Maria")
        RedeExterna.objects.create(escola=escola_joao, processo=self.processo_re, setor=self.setor_re, responsavel=self.joao)
        RedeExterna.objects.create(escola=escola_maria, processo=self.processo_re, setor=self.setor_re, responsavel=self.maria)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'responsavel': self.joao.pk})

        self.assertContains(response, "Escola Do Joao")
        self.assertNotContains(response, "Escola Da Maria")

    def test_opcoes_do_filtro_responsavel_reaproveitam_elegibilidade_do_setor_rn060(self):
        AcessoSetor.objects.create(usuario=self.joao, setor_nome="Setor RN066")

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']))

        opcoes = response.context['responsavel_opcoes_filtro']
        self.assertIn(self.joao, opcoes)
        self.assertNotIn(self.maria, opcoes)

    def test_filtro_responsavel_isola_subatividade_de_outro_setor_da_mesma_escola(self):
        """Exemplo do RN-066: Escola X tem RE no Setor da tela (Responsavel
        Joao) e RI em outro Setor (Responsavel Maria) — filtrar por
        Responsavel=Maria na tela deste Setor nao deve trazer a Escola."""
        outro_setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RN066 Outro")
        escola_x = Escola.objects.create(jira_key="EACE-RN066-10", nome="Escola X Mista")
        RedeExterna.objects.create(escola=escola_x, processo=self.processo_re, setor=self.setor_re, responsavel=self.joao)
        RedeInterna.objects.create(escola=escola_x, processo=self.processo_ri, setor=outro_setor_ri, responsavel=self.maria)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'responsavel': self.maria.pk})

        self.assertNotContains(response, "Escola X Mista")

    def test_filtro_status_restringe_as_escolas_com_aquele_status_neste_setor(self):
        escola_a = Escola.objects.create(jira_key="EACE-RN066-12", nome="Escola Status A")
        escola_b = Escola.objects.create(jira_key="EACE-RN066-13", nome="Escola Status B")
        RedeExterna.objects.create(escola=escola_a, processo=self.processo_re, setor=self.setor_re, status=self.status_a)
        RedeExterna.objects.create(escola=escola_b, processo=self.processo_re, setor=self.setor_re, status=self.status_b)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'status': self.status_a.nome})

        self.assertContains(response, "Escola Status A")
        self.assertNotContains(response, "Escola Status B")

    def test_opcoes_do_filtro_status_vem_so_do_catalogo_deste_setor(self):
        outro_setor = Setor.objects.create(processo=self.processo_re, nome="Setor RN066 Catalogo Outro")
        SetorStatus.objects.create(setor=outro_setor, nome="Status De Outro Setor")

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']))

        opcoes = response.context['status_opcoes_filtro']
        self.assertIn(self.status_a.nome, opcoes)
        self.assertNotIn("Status De Outro Setor", opcoes)

    def test_filtro_status_isola_subatividade_de_outro_setor_da_mesma_escola(self):
        outro_setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RN066 Outro Status")
        status_outro = SetorStatus.objects.create(setor=outro_setor_ri, nome="Aguardando material")
        escola_y = Escola.objects.create(jira_key="EACE-RN066-11", nome="Escola Y Mista")
        RedeExterna.objects.create(escola=escola_y, processo=self.processo_re, setor=self.setor_re, status=self.status_b)
        RedeInterna.objects.create(escola=escola_y, processo=self.processo_ri, setor=outro_setor_ri, status=status_outro)

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {'status': "Aguardando material"})

        self.assertNotContains(response, "Escola Y Mista")

    def test_combinacao_dos_tres_filtros_novos_e_por_e(self):
        status_ri_mesmo_nome = SetorStatus.objects.create(setor=self.setor_ri, nome="Aguardando material")
        escola_alvo = Escola.objects.create(jira_key="EACE-RN066-14", nome="Escola Alvo Combinada")
        escola_sem_re = Escola.objects.create(jira_key="EACE-RN066-15", nome="Escola Sem RE Aqui")
        RedeExterna.objects.create(
            escola=escola_alvo, processo=self.processo_re, setor=self.setor_re,
            responsavel=self.joao, status=self.status_a,
        )
        # mesmo Responsavel e mesmo nome de Status, mas so tem RI (nao RE)
        # neste Setor — deve ser excluida pelo filtro de tipo=re, mesmo
        # satisfazendo Responsavel e Status isoladamente.
        RedeInterna.objects.create(
            escola=escola_sem_re, processo=self.processo_ri, setor=self.setor_ri,
            responsavel=self.joao, status=status_ri_mesmo_nome,
        )

        response = self.client.get(reverse('setor_detail', args=['Setor RN066']), {
            'tipo': 're', 'responsavel': self.joao.pk, 'status': self.status_a.nome,
        })

        self.assertContains(response, "Escola Alvo Combinada")
        self.assertNotContains(response, "Escola Sem RE Aqui")

    def test_filtros_novos_nao_aparecem_no_grid_global(self):
        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertNotContains(response, 'name="tipo"')
        self.assertNotContains(response, 'Responsável (todos)')
        self.assertNotContains(response, 'Status (todos)')

    def test_filtros_novos_sao_ignorados_no_grid_global_mesmo_via_querystring(self):
        escola = Escola.objects.create(jira_key="EACE-RN066-16", nome="Escola Setor RN066 Global")
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re, responsavel=self.maria)

        response = self.client.get(
            reverse('enderecos_lastmile'), {'tipo': 'ri', 'responsavel': self.joao.pk, 'status': 'Qualquer'},
        )

        # tipo=ri exigiria RI vinculado a algum Setor, responsavel=joao nao
        # bate com maria — se os filtros novos fossem aplicados ao grid
        # global, a escola sumiria; por serem exclusivos da Tela de Setor,
        # continua aparecendo.
        self.assertContains(response, "Escola Setor RN066 Global")

    def test_filtros_novos_nao_geram_consulta_extra_por_escola(self):
        for indice in range(3):
            escola = Escola.objects.create(jira_key=f"EACE-RN066-N1-{indice}", nome=f"Escola RN066 N1 {indice}")
            RedeExterna.objects.create(
                escola=escola, processo=self.processo_re, setor=self.setor_re,
                responsavel=self.joao, status=self.status_a,
            )

        params = {'tipo': 're', 'responsavel': self.joao.pk, 'status': self.status_a.nome}

        with CaptureQueriesContext(connection) as poucas_escolas:
            self.client.get(reverse('setor_detail', args=['Setor RN066']), params)

        for indice in range(3, 18):
            escola = Escola.objects.create(jira_key=f"EACE-RN066-N1-{indice}", nome=f"Escola RN066 N1 {indice}")
            RedeExterna.objects.create(
                escola=escola, processo=self.processo_re, setor=self.setor_re,
                responsavel=self.joao, status=self.status_a,
            )

        with CaptureQueriesContext(connection) as muitas_escolas:
            self.client.get(reverse('setor_detail', args=['Setor RN066']), params)

        self.assertEqual(len(poucas_escolas.captured_queries), len(muitas_escolas.captured_queries))


class FiltroCorConectividadeTests(TestCase):
    """RN-067: filtro por cor do indicador de conectividade (RN-062),
    exclusivo do grid global de Enderecos Lastmile (`enderecos_lastmile_view`)
    — nao aparece na Tela de Setor (`setor_detail`)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-rn067", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_ri, _ = Processo.objects.get_or_create(nome=RedeInterna.NOME_PROCESSO_PADRAO)

        self.setor_re = Setor.objects.create(processo=self.processo_re, nome="Setor RN067")
        self.setor_ri = Setor.objects.create(processo=self.processo_ri, nome="Setor RN067")

        self.concluido_re = SetorStatus.objects.create(setor=self.setor_re, nome="Concluido")
        self.concluido_ri = SetorStatus.objects.create(setor=self.setor_ri, nome="Concluido")
        self.andamento_re = SetorStatus.objects.create(setor=self.setor_re, nome="Em andamento")
        self.andamento_ri = SetorStatus.objects.create(setor=self.setor_ri, nome="Em andamento")

    def _escola_verde(self, jira_key, nome, **kwargs):
        escola = Escola.objects.create(jira_key=jira_key, nome=nome, **kwargs)
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.setor_ri, status=self.concluido_ri)
        return escola

    def _escola_amarela_re_concluida(self, jira_key, nome):
        escola = Escola.objects.create(jira_key=jira_key, nome=nome)
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re, status=self.concluido_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.setor_ri, status=self.andamento_ri)
        return escola

    def _escola_amarela_ri_concluida(self, jira_key, nome):
        escola = Escola.objects.create(jira_key=jira_key, nome=nome)
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re, status=self.andamento_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.setor_ri, status=self.concluido_ri)
        return escola

    def _escola_vermelha_ambas_pendentes(self, jira_key, nome):
        escola = Escola.objects.create(jira_key=jira_key, nome=nome)
        RedeExterna.objects.create(escola=escola, processo=self.processo_re, setor=self.setor_re, status=self.andamento_re)
        RedeInterna.objects.create(escola=escola, processo=self.processo_ri, setor=self.setor_ri, status=self.andamento_ri)
        return escola

    def _escola_vermelha_sem_re_nem_ri(self, jira_key, nome):
        return Escola.objects.create(jira_key=jira_key, nome=nome)

    def test_filtro_verde_mostra_so_escolas_com_re_e_ri_concluidos(self):
        self._escola_verde("EACE-RN067-1", "Escola Verde")
        self._escola_amarela_re_concluida("EACE-RN067-2", "Escola Amarela RE")
        self._escola_vermelha_ambas_pendentes("EACE-RN067-3", "Escola Vermelha")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde'})

        self.assertContains(response, "Escola Verde")
        self.assertNotContains(response, "Escola Amarela RE")
        self.assertNotContains(response, "Escola Vermelha")

    def test_filtro_amarelo_mostra_re_ou_ri_concluidos_mas_nao_os_dois(self):
        """XOR: amarelo e exatamente uma das duas concluida — nao pode
        confundir com verde (as duas concluidas)."""
        self._escola_amarela_re_concluida("EACE-RN067-4", "Escola Amarela RE Only")
        self._escola_amarela_ri_concluida("EACE-RN067-5", "Escola Amarela RI Only")
        self._escola_verde("EACE-RN067-6", "Escola Verde Nao Deve Aparecer No Amarelo")
        self._escola_vermelha_ambas_pendentes("EACE-RN067-7", "Escola Vermelha Nao Deve Aparecer No Amarelo")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'amarelo'})

        self.assertContains(response, "Escola Amarela RE Only")
        self.assertContains(response, "Escola Amarela RI Only")
        self.assertNotContains(response, "Escola Verde Nao Deve Aparecer No Amarelo")
        self.assertNotContains(response, "Escola Vermelha Nao Deve Aparecer No Amarelo")

    def test_filtro_vermelho_mostra_escolas_sem_nenhuma_concluida(self):
        self._escola_vermelha_ambas_pendentes("EACE-RN067-8", "Escola Vermelha Pendente")
        self._escola_verde("EACE-RN067-9", "Escola Verde Nao Deve Aparecer No Vermelho")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'vermelho'})

        self.assertContains(response, "Escola Vermelha Pendente")
        self.assertNotContains(response, "Escola Verde Nao Deve Aparecer No Vermelho")

    def test_filtro_vermelho_inclui_escola_sem_re_nem_ri_cadastrado(self):
        """RE/RI inexistente para a Escola conta como "nao concluida" —
        cai em vermelho (RN-062/RN-067)."""
        self._escola_vermelha_sem_re_nem_ri("EACE-RN067-10", "Escola Sem RE Nem RI")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'vermelho'})

        self.assertContains(response, "Escola Sem RE Nem RI")

    def test_filtro_vermelho_nao_traz_escola_sem_re_nem_ri_quando_marcado_so_verde_ou_amarelo(self):
        self._escola_vermelha_sem_re_nem_ri("EACE-RN067-11", "Escola Sem Rede Fora Do Verde")

        response_verde = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde'})
        response_amarelo = self.client.get(reverse('enderecos_lastmile'), {'cor': 'amarelo'})

        self.assertNotContains(response_verde, "Escola Sem Rede Fora Do Verde")
        self.assertNotContains(response_amarelo, "Escola Sem Rede Fora Do Verde")

    def test_selecao_multipla_e_or_entre_as_cores_marcadas(self):
        self._escola_verde("EACE-RN067-12", "Escola Verde Multi")
        self._escola_amarela_re_concluida("EACE-RN067-13", "Escola Amarela Multi")
        self._escola_vermelha_ambas_pendentes("EACE-RN067-14", "Escola Vermelha Multi")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': ['verde', 'amarelo']})

        self.assertContains(response, "Escola Verde Multi")
        self.assertContains(response, "Escola Amarela Multi")
        self.assertNotContains(response, "Escola Vermelha Multi")

    def test_nenhuma_cor_marcada_mantem_comportamento_atual(self):
        self._escola_verde("EACE-RN067-15", "Escola Verde Sem Filtro")
        self._escola_vermelha_ambas_pendentes("EACE-RN067-16", "Escola Vermelha Sem Filtro")

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, "Escola Verde Sem Filtro")
        self.assertContains(response, "Escola Vermelha Sem Filtro")

    def test_combinacao_com_busca_q_e_por_e(self):
        self._escola_verde("EACE-RN067-17", "Escola Verde Alvo Busca")
        self._escola_verde("EACE-RN067-18", "Outra Escola Verde Diferente")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde', 'q': 'Alvo Busca'})

        self.assertContains(response, "Escola Verde Alvo Busca")
        self.assertNotContains(response, "Outra Escola Verde Diferente")

    def test_combinacao_com_cidade_e_estado_e_por_e(self):
        self._escola_verde("EACE-RN067-19", "Escola Verde Sao Paulo", municipio="Sao Paulo", uf="SP")
        self._escola_verde("EACE-RN067-20", "Escola Verde Rio", municipio="Rio de Janeiro", uf="RJ")

        response = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde', 'cidade': 'Sao Paulo', 'estado': 'SP'})

        self.assertContains(response, "Escola Verde Sao Paulo")
        self.assertNotContains(response, "Escola Verde Rio")

    def test_filtro_de_cor_nao_aparece_na_tela_de_setor(self):
        response = self.client.get(reverse('setor_detail', args=['Setor RN067']))

        self.assertNotContains(response, 'name="cor"')

    def test_filtro_de_cor_e_ignorado_na_tela_de_setor_mesmo_via_querystring(self):
        escola_vermelha = self._escola_vermelha_ambas_pendentes("EACE-RN067-21", "Escola Vermelha Na Tela De Setor")

        response = self.client.get(reverse('setor_detail', args=['Setor RN067']), {'cor': 'verde'})

        # Se o filtro de cor fosse aplicado na Tela de Setor, a escola
        # vermelha sumiria ao marcar "verde"; por ser exclusivo do grid
        # global, continua aparecendo.
        self.assertContains(response, "Escola Vermelha Na Tela De Setor")

    def test_filtro_de_cor_nao_gera_consulta_extra_por_escola(self):
        for indice in range(3):
            self._escola_verde(f"EACE-RN067-N1-{indice}", f"Escola RN067 N1 {indice}")

        with CaptureQueriesContext(connection) as poucas_escolas:
            self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde'})

        for indice in range(3, 18):
            self._escola_verde(f"EACE-RN067-N1-{indice}", f"Escola RN067 N1 {indice}")

        with CaptureQueriesContext(connection) as muitas_escolas:
            self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde'})

        self.assertEqual(len(poucas_escolas.captured_queries), len(muitas_escolas.captured_queries))

    def test_paginacao_correta_com_filtro_de_cor_aplicado(self):
        for indice in range(15):
            self._escola_verde(f"EACE-RN067-PAG-{indice}", f"Escola Paginada Verde {indice:02d}")
        for indice in range(5):
            self._escola_vermelha_ambas_pendentes(f"EACE-RN067-PAG-VM-{indice}", f"Escola Paginada Vermelha {indice:02d}")

        response_pagina_1 = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde'})
        self.assertEqual(response_pagina_1.context['total_enderecos'], 15)
        self.assertEqual(len(response_pagina_1.context['page_obj']), 10)

        response_pagina_2 = self.client.get(reverse('enderecos_lastmile'), {'cor': 'verde', 'page': 2})
        self.assertEqual(len(response_pagina_2.context['page_obj']), 5)


class NomesSetorVisiveisParaUsuarioTests(TestCase):
    """PO-075/RN-054/RN-055: funcoes de servico que sustentam o menu e as
    views de Setores (grupo dedicado + concessao individual por nome)."""

    def setUp(self):
        # Nomes distintos dos Setores semeados de fabrica (RN-025), para nao
        # colidir com o catalogo ja existente no banco de testes.
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.setor_a = Setor.objects.create(processo=self.processo_re, nome="Setor PO075 A")
        self.setor_b = Setor.objects.create(processo=self.processo_re, nome="Setor PO075 B")

    def test_usuario_comum_sem_concessao_nao_ve_nenhum_nome_novo(self):
        usuario = get_user_model().objects.create_user(username="serv-sem-concessao", password="senha-segura")

        visiveis = services.nomes_setor_visiveis_para_usuario(usuario)

        self.assertNotIn("Setor PO075 A", visiveis)
        self.assertNotIn("Setor PO075 B", visiveis)
        self.assertFalse(services.usuario_pode_acessar_setor(usuario, "Setor PO075 A"))

    def test_usuario_comum_ve_somente_o_concedido(self):
        usuario = get_user_model().objects.create_user(username="serv-com-concessao", password="senha-segura")
        AcessoSetor.objects.create(usuario=usuario, setor_nome="Setor PO075 A")

        visiveis = services.nomes_setor_visiveis_para_usuario(usuario)

        self.assertIn("Setor PO075 A", visiveis)
        self.assertNotIn("Setor PO075 B", visiveis)
        self.assertTrue(services.usuario_pode_acessar_setor(usuario, "Setor PO075 A"))
        self.assertFalse(services.usuario_pode_acessar_setor(usuario, "Setor PO075 B"))

    def test_superuser_ve_todos_sem_precisar_de_concessao(self):
        superuser = get_user_model().objects.create_superuser(username="serv-superuser", password="senha-segura", email="s@s.com")

        visiveis = services.nomes_setor_visiveis_para_usuario(superuser)

        self.assertIn("Setor PO075 A", visiveis)
        self.assertIn("Setor PO075 B", visiveis)
        self.assertTrue(services.usuario_pode_acessar_setor(superuser, "Setor PO075 A"))
        self.assertTrue(services.usuario_pode_acessar_setor(superuser, "Setor PO075 B"))


class SetoresDisponiveisContextProcessorTests(TestCase):
    """PO-075/RN-055: `setores_disponiveis` roda em toda pagina do sistema
    (registrado em TEMPLATES, nao so nas telas de Setores). Regressao de um
    incidente em que a consulta a `AcessoSetor` derrubava com erro 500
    qualquer pagina acessada por um usuario autenticado nao-superusuario."""

    def setUp(self):
        self.factory = RequestFactory()

    def _contexto_para(self, usuario):
        request = self.factory.get("/qualquer-pagina-do-sistema/")
        request.user = usuario
        return context_processors.setores_disponiveis(request)

    def test_usuario_anonimo_nao_recebe_variavel_de_menu(self):
        self.assertEqual(self._contexto_para(AnonymousUser()), {})

    def test_usuario_comum_sem_concessao_nao_gera_erro_e_recebe_lista_vazia(self):
        usuario = get_user_model().objects.create_user(username="ctx-sem-concessao", password="senha-segura")

        self.assertEqual(self._contexto_para(usuario), {"nomes_setor_menu": []})

    def test_usuario_comum_com_concessao_recebe_somente_o_nome_concedido(self):
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        Setor.objects.create(processo=processo, nome="Setor Contexto A")
        Setor.objects.create(processo=processo, nome="Setor Contexto B")
        usuario = get_user_model().objects.create_user(username="ctx-com-concessao", password="senha-segura")
        AcessoSetor.objects.create(usuario=usuario, setor_nome="Setor Contexto A")

        contexto = self._contexto_para(usuario)

        self.assertIn("Setor Contexto A", contexto["nomes_setor_menu"])
        self.assertNotIn("Setor Contexto B", contexto["nomes_setor_menu"])

    def test_superuser_recebe_todos_os_nomes_cadastrados_sem_concessao(self):
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        Setor.objects.create(processo=processo, nome="Setor Contexto C")
        superuser = get_user_model().objects.create_superuser(
            username="ctx-superuser", password="senha-segura", email="ctx-superuser@teste.com",
        )

        contexto = self._contexto_para(superuser)

        self.assertIn("Setor Contexto C", contexto["nomes_setor_menu"])


class EscolaMapaCalorTests(TestCase):
    """RN-043/PO-067: Mapa Calor (MC), terceira subatividade fixa da Escola,
    no mesmo molde de RedeExterna/RedeInterna — grid, cascata Setor/Status,
    Parceiro, historico individual/combinado e Campos por Setor."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-mapa-calor", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(jira_key="EACE-MC", nome="Escola Mapa Calor")
        self.processo_re, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        self.processo_mc, _ = Processo.objects.get_or_create(nome=MapaCalor.NOME_PROCESSO_PADRAO)
        self.setor = Setor.objects.create(processo=self.processo_mc, nome="Setor MC QA")
        self.status = SetorStatus.objects.create(setor=self.setor, nome="Em andamento MC")

    def _content_type_mc(self):
        return ContentType.objects.get_for_model(MapaCalor)

    def test_post_cria_mapa_calor_com_processo_fixo(self):
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'responsavel': self.user.pk},
        )

        self.assertEqual(response.status_code, 200)
        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertEqual(mc.processo, self.processo_mc)
        self.assertEqual(mc.setor, self.setor)
        # RN-035: grid global ignora o Status enviado no POST — fica "Novo".
        self.assertEqual(mc.status.nome, "Novo")
        self.assertContains(response, "Mapa Calor atualizado")

    def test_mapa_calor_independente_de_setor_status_parceiro_de_re_e_ri(self):
        parceiro_re = Partner.objects.create(nome_fantasia="Parceiro RE MC")
        parceiro_mc = Partner.objects.create(nome_fantasia="Parceiro MC")
        setor_re = Setor.objects.create(processo=self.processo_re, nome="Setor RE QA MC")
        status_re = SetorStatus.objects.create(setor=setor_re, nome="Status RE MC")

        RedeExterna.objects.create(
            escola=self.escola, processo=self.processo_re, setor=setor_re, status=status_re, parceiro=parceiro_re,
        )
        MapaCalor.objects.create(
            escola=self.escola, processo=self.processo_mc, setor=self.setor, status=self.status, parceiro=parceiro_mc,
        )

        self.escola.refresh_from_db()
        self.assertNotEqual(self.escola.mapa_calor.setor, self.escola.rede_externa.setor)
        self.assertNotEqual(self.escola.mapa_calor.status, self.escola.rede_externa.status)
        self.assertNotEqual(self.escola.mapa_calor.parceiro, self.escola.rede_externa.parceiro)

    def test_cascata_setor_status_no_mapa_calor_na_tela_do_proprio_setor(self):
        """RN-026: Setor e Status editaveis juntos na tela do proprio Setor."""
        response = self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {'setor': self.setor.pk, 'status': self.status.pk, 'setor_atual': self.setor.nome, 'responsavel': self.user.pk},
        )

        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertEqual(mc.setor, self.setor)
        self.assertEqual(mc.status, self.status)
        self.assertContains(response, "atualizado")

    def test_enviar_mapa_calor_a_outro_setor_aplica_aguardando_automatico(self):
        """RN-033: enviar o MC para um Setor diferente do setor_atual da
        tela aplica o Status "Aguardando" automaticamente no Setor de
        destino, independente do que foi submetido."""
        outro_setor = Setor.objects.create(processo=self.processo_mc, nome="Setor MC Destino")
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc, setor=self.setor, status=self.status)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {'setor': outro_setor.pk, 'status': '', 'setor_atual': self.setor.nome},
        )

        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertEqual(mc.setor, outro_setor)
        self.assertEqual(mc.status.nome, "Aguardando")
        self.assertEqual(mc.status.setor, outro_setor)

    def test_parceiro_do_mapa_calor_editavel_na_tela_do_setor_lastmile(self):
        """RN-030: Parceiro so e editavel pela tela do Setor de negocio
        "Lastmile" — mesma regra ja usada por RE/RI."""
        parceiro = Partner.objects.create(nome_fantasia="Parceiro Lastmile MC")
        setor_lastmile, _ = Setor.objects.get_or_create(processo=self.processo_mc, nome="Lastmile")
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc, setor=setor_lastmile)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {'setor': setor_lastmile.pk, 'status': '', 'setor_atual': setor_lastmile.nome, 'parceiro': parceiro.pk},
        )

        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertEqual(mc.parceiro, parceiro)

    def test_parceiro_do_mapa_calor_nao_editavel_fora_da_tela_lastmile(self):
        parceiro = Partner.objects.create(nome_fantasia="Parceiro Fora MC")
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc, setor=self.setor)

        self.client.post(
            reverse('escola_rede_editar', args=[self.escola.pk, 'mc']),
            {'setor': self.setor.pk, 'status': '', 'setor_atual': self.setor.nome, 'parceiro': parceiro.pk},
        )

        mc = MapaCalor.objects.get(escola=self.escola)
        self.assertIsNone(mc.parceiro_id)

    def test_historico_individual_do_mapa_calor(self):
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)

        response = self.client.post(
            reverse('escola_rede_historico', args=[self.escola.pk, 'mc']),
            {'descricao': 'Comentario exclusivo do Mapa Calor'},
        )

        self.assertEqual(response.status_code, 200)
        mc = MapaCalor.objects.get(escola=self.escola)
        registro = RegistroHistorico.objects.get(content_type=self._content_type_mc(), object_id=mc.id)
        self.assertEqual(registro.acao, 'Comentario exclusivo do Mapa Calor')
        self.assertContains(response, 'Comentario exclusivo do Mapa Calor')

    def test_comentario_do_mapa_calor_nao_aparece_no_historico_do_re(self):
        mc = MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Somente do Mapa Calor', usuario=self.user,
            content_type=self._content_type_mc(), object_id=mc.id,
        )

        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 're']))

        self.assertNotContains(response, 'Somente do Mapa Calor')

    def test_historico_combinado_da_escola_inclui_mapa_calor(self):
        mc = MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)
        RegistroHistorico.objects.create(
            tipo='comentario', acao='Entrada do Mapa Calor', usuario=self.user,
            content_type=self._content_type_mc(), object_id=mc.id,
        )

        entradas = services.historico_combinado_escola(self.escola)
        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0].origem_tipo, 'mc')

        response = self.client.get(reverse('escola_historico', args=[self.escola.pk]))
        self.assertContains(response, 'Entrada do Mapa Calor')
        self.assertContains(response, 'MC')

    def test_grid_exibe_linha_do_mapa_calor(self):
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)

        response = self.client.get(reverse('enderecos_lastmile'))

        self.assertContains(response, f'id="rede-mc-{self.escola.pk}"')

    def test_campo_com_sub_atividades_aplica_mapa_calor_aparece_no_modal_do_mc(self):
        SetorEscopo.objects.create(
            setor_nome="Setor Campo MC", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            aplica_re=False, aplica_ri=False, aplica_mapa_calor=True,
        )
        Campo.objects.create(nome="Campo do Mapa Calor", tipo=Campo.TIPO_TEXTO, setor_nome="Setor Campo MC")
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 'mc']))

        self.assertContains(response, "Campo do Mapa Calor")

    def test_campo_so_re_ri_nao_aparece_no_modal_do_mc(self):
        SetorEscopo.objects.create(
            setor_nome="Setor Campo Sem MC", atividade=SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            aplica_re=True, aplica_ri=True, aplica_mapa_calor=False,
        )
        Campo.objects.create(nome="Campo Sem Mapa Calor", tipo=Campo.TIPO_TEXTO, setor_nome="Setor Campo Sem MC")
        MapaCalor.objects.create(escola=self.escola, processo=self.processo_mc)

        response = self.client.get(reverse('escola_rede_campos', args=[self.escola.pk, 'mc']))

        self.assertNotContains(response, "Campo Sem Mapa Calor")

    def test_tipo_invalido_continua_devolvendo_404(self):
        response = self.client.get(reverse('escola_rede_historico', args=[self.escola.pk, 'xx']))

        self.assertEqual(response.status_code, 404)
