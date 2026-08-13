from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, Endereco
from apps.core.models import CotacaoStatusAuditoria, RegistroHistorico
from apps.partners import services
from apps.partners.models import Partner, PartnerPlan, Proposal
from apps.partners.services import (
    _detalhe_os_ixc_para_auditoria,
    _detalhe_os_ixc_para_historico,
    _mensagem_os_ixc_ja_finalizada,
    _status_os_ixc_para_operador,
)
from apps.partners.models import ProposalMotivoInviavel
from scripts.integracoes.ixc_finalizacao_service import finalizar_os_existente


class OsIxcFeedbackTests(SimpleTestCase):
    def test_status_indica_quando_os_ja_estava_finalizada(self):
        resultado_ixc = {"already_closed": True}

        self.assertEqual(
            _status_os_ixc_para_operador(True, resultado_ixc),
            "Já estava finalizada",
        )
        self.assertIn(
            "O.S. no IXC: Já estava finalizada",
            _detalhe_os_ixc_para_historico(True, "Encerrada pelo fluxo", resultado_ixc),
        )
        self.assertIn(
            "Status da O.S. no IXC: Já estava finalizada.",
            _detalhe_os_ixc_para_auditoria(True, "Encerrada pelo fluxo", resultado_ixc),
        )

    def test_mensagem_resume_multiplas_os_ja_finalizadas(self):
        proposta_1 = type("Proposal", (), {"codigo_exibicao": "COT-001"})()
        proposta_2 = type("Proposal", (), {"codigo_exibicao": "COT-002"})()

        mensagem = _mensagem_os_ixc_ja_finalizada([proposta_1, proposta_2])

        self.assertIn("2 O.S. já estavam finalizadas no IXC", mensagem)
        self.assertIn("sucesso", mensagem.casefold())


class FinalizacaoOsExistenteTests(SimpleTestCase):
    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_registros_fechamento_os", return_value=[{"id": "99"}])
    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_os_por_id", return_value={"id": "5313", "status": "F"})
    def test_retorno_idempotente_marca_os_ja_finalizada(self, _buscar_os, _buscar_registros):
        resultado = finalizar_os_existente(os_id="5313", mensagem="Teste")

        self.assertTrue(resultado["ok"])
        self.assertTrue(resultado["already_closed"])
        self.assertEqual(resultado["registro_fechamento"]["id"], "99")


def _criar_partner(**kwargs):
    dados = {
        "nome_fantasia": "Parceiro Teste",
        "razao_social": "Parceiro Teste LTDA",
        "cnpj_cpf": "11111111000111",
        "status": "ativo",
    }
    dados.update(kwargs)
    return Partner.objects.create(**dados)


def _criar_proposal(partner, **kwargs):
    dados = {"partner": partner, "status": "analise"}
    dados.update(kwargs)
    return Proposal.objects.create(**dados)


class PartnerListViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("partner_list"))

        self.assertEqual(response.status_code, 403)

    def test_lista_apenas_partners_com_proposta_convertida(self):
        partner_convertido = _criar_partner(cnpj_cpf="22222222000122")
        _criar_proposal(partner_convertido, status="contratado", codigo_proposta="COT-1")
        _criar_partner(cnpj_cpf="33333333000133", status="ativo")

        response = self.client.get(reverse("partner_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [partner_convertido])

    def test_deduplica_propostas_do_mesmo_lote_no_parceiro(self):
        partner = _criar_partner()
        _criar_proposal(partner, status="contratado", codigo_proposta="COT-1")
        _criar_proposal(partner, status="contratado", codigo_proposta="COT-1")

        response = self.client.get(reverse("partner_list"))

        partner_na_pagina = response.context["page_obj"].object_list[0]
        self.assertEqual(partner_na_pagina.total_propostas, 1)


class ProvedoresListViewTests(TestCase):
    """RN-045/PO-069: tela em grid de Provedores, independente da lista de
    Parceiros acima (grupo Parceiro) - protegida por grupo_LastMile_required."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="lastmile", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-lastmile", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("provedores_list"))

        self.assertEqual(response.status_code, 403)

    def test_lista_todos_os_partners_cadastrados(self):
        partner_a = _criar_partner(cnpj_cpf="44444444000144", nome_fantasia="Provedor A")
        partner_b = _criar_partner(cnpj_cpf="55555555000155", nome_fantasia="Provedor B", status="inativo")

        response = self.client.get(reverse("provedores_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Provedor A")
        self.assertContains(response, "Provedor B")
        self.assertEqual(set(response.context["page_obj"].object_list), {partner_a, partner_b})

    def test_menu_projeto_nao_exibe_mais_o_item_leads(self):
        """Regressao da RN-046: o item "Leads" e removido do submenu
        Projeto, mas a rota lead_list continua respondendo normalmente
        para quem tem permissao (sem entrada de navegacao, sem quebra)."""
        response = self.client.get(reverse("provedores_list"))

        self.assertNotContains(response, "Leads</a>")

        response_lead_list = self.client.get(reverse("lead_list"))
        self.assertEqual(response_lead_list.status_code, 200)


class ProvedoresCreateViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="lastmile-create", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-lastmile-create", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("provedores_create"), {
            "razao_social": "Novo Provedor LTDA",
            "cnpj_cpf": "66666666000166",
            "status": "ativo",
        })

        self.assertEqual(response.status_code, 403)

    def test_cria_provedor_com_sucesso_e_redireciona(self):
        response = self.client.post(reverse("provedores_create"), {
            "razao_social": "Novo Provedor LTDA",
            "nome_fantasia": "Novo Provedor",
            "cnpj_cpf": "66666666000166",
            "contato_nome": "Fulano",
            "email": "contato@novoprovedor.com.br",
            "telefone": "8599990000",
            "status": "ativo",
        })

        self.assertRedirects(response, reverse("provedores_list"))
        self.assertTrue(Partner.objects.filter(cnpj_cpf="66666666000166").exists())

    def test_cnpj_duplicado_retorna_erro_de_formulario_sem_500(self):
        _criar_partner(cnpj_cpf="77777777000177")

        response = self.client.post(reverse("provedores_create"), {
            "razao_social": "Duplicado LTDA",
            "cnpj_cpf": "77777777000177",
            "status": "ativo",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("cnpj_cpf", response.context["form"].errors)
        self.assertEqual(Partner.objects.filter(cnpj_cpf="77777777000177").count(), 1)


class ProvedoresEditViewTests(TestCase):
    """RN-046/PO-070: edicao de um Partner ja cadastrado a partir da tela
    de Provedores, reaproveitando o PartnerForm - mesma trava de
    grupo_LastMile_required das demais views de Provedores."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="lastmile-edit", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-lastmile-edit", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)
        self.provedor = _criar_partner(
            cnpj_cpf="88888888000188", nome_fantasia="Provedor Original",
            razao_social="Provedor Original LTDA",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("provedores_edit", args=[self.provedor.pk]), {
            "razao_social": "Alterado LTDA",
            "cnpj_cpf": "88888888000188",
            "status": "ativo",
        })

        self.assertEqual(response.status_code, 403)

    def test_get_exibe_formulario_preenchido_com_dados_atuais(self):
        response = self.client.get(reverse("provedores_edit", args=[self.provedor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar")
        self.assertContains(response, "Provedor Original LTDA")

    def test_edita_provedor_existente_com_sucesso_e_persiste_valores(self):
        response = self.client.post(reverse("provedores_edit", args=[self.provedor.pk]), {
            "razao_social": "Provedor Editado LTDA",
            "nome_fantasia": "Provedor Editado",
            "cnpj_cpf": "88888888000188",
            "contato_nome": "Fulano Editado",
            "email": "editado@provedor.com.br",
            "telefone": "8599991111",
            "status": "inativo",
        })

        self.assertRedirects(response, reverse("provedores_list"))
        self.provedor.refresh_from_db()
        self.assertEqual(self.provedor.razao_social, "Provedor Editado LTDA")
        self.assertEqual(self.provedor.nome_fantasia, "Provedor Editado")
        self.assertEqual(self.provedor.contato_nome, "Fulano Editado")
        self.assertEqual(self.provedor.email, "editado@provedor.com.br")
        self.assertEqual(self.provedor.telefone, "8599991111")
        self.assertEqual(self.provedor.status, "inativo")

    def test_cnpj_duplicado_ao_editar_retorna_erro_de_formulario_sem_500(self):
        _criar_partner(cnpj_cpf="99999999000199", nome_fantasia="Outro Provedor")

        response = self.client.post(reverse("provedores_edit", args=[self.provedor.pk]), {
            "razao_social": "Provedor Original LTDA",
            "cnpj_cpf": "99999999000199",
            "status": "ativo",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("cnpj_cpf", response.context["form"].errors)
        self.provedor.refresh_from_db()
        self.assertEqual(self.provedor.cnpj_cpf, "88888888000188")

    def test_link_editar_aparece_no_grid_de_provedores(self):
        response = self.client.get(reverse("provedores_list"))

        self.assertContains(response, reverse("provedores_edit", args=[self.provedor.pk]))


class PartnerInactiveListViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)

    def test_lista_apenas_partners_fora_do_fluxo_ativo(self):
        inativo = _criar_partner(status="inativo", cnpj_cpf="22222222000122")
        _criar_partner(status="ativo", cnpj_cpf="33333333000133")

        response = self.client.get(reverse("partner_inactive_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["page_obj"].object_list), [inativo])


class PartnerDetailViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()
        self.cliente = Cliente.objects.create(
            id_ixc="900", razao_social="Cliente Teste", nome_fantasia="Cliente Teste", cnpj_cpf="00000000000100",
        )

    def test_agrupa_propostas_em_aberto_por_cliente_e_lote(self):
        _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1", cliente=self.cliente)
        _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1", cliente=self.cliente)
        _criar_proposal(self.partner, status="contratado", codigo_proposta="COT-2", cliente=self.cliente)

        response = self.client.get(reverse("partner_detail", args=[self.partner.pk]))

        self.assertEqual(response.status_code, 200)
        grupos = response.context["proposal_groups"]
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["total_logins"], 2)

    def test_historico_mostra_so_ativos_por_padrao_e_todos_com_ver_antigos(self):
        # `partner_detail.html` nao renderiza historico/qtd_antigo/ver_antigos
        # no HTML (achado: contexto calculado na view mas sem uso no template,
        # pre-existente e fora do escopo desta PO) - por isso a verificacao e
        # via response.context, nao via conteudo da pagina.
        partner_type = ContentType.objects.get_for_model(Partner)
        ativo = RegistroHistorico.objects.create(
            tipo="comentario", acao="Ativo", usuario=self.usuario,
            content_type=partner_type, object_id=self.partner.id, arquivado=False,
        )
        arquivado = RegistroHistorico.objects.create(
            tipo="comentario", acao="Arquivado", usuario=self.usuario,
            content_type=partner_type, object_id=self.partner.id, arquivado=True,
        )

        response = self.client.get(reverse("partner_detail", args=[self.partner.pk]))
        self.assertEqual(list(response.context["historico"]), [ativo])
        self.assertEqual(response.context["qtd_antigo"], 1)

        response_antigos = self.client.get(reverse("partner_detail", args=[self.partner.pk]), {"ver_antigos": "true"})
        self.assertEqual(set(response_antigos.context["historico"]), {ativo, arquivado})


class PartnerPlanViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()

    def test_add_cria_plano_do_partner(self):
        response = self.client.post(
            reverse("partner_plan_add", args=[self.partner.pk]),
            {"nome_plano": "Plano 100 Mbps"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PartnerPlan.objects.filter(partner=self.partner).count(), 1)

    def test_delete_remove_plano_do_partner(self):
        plano = PartnerPlan.objects.create(partner=self.partner, nome_plano="Plano 50 Mbps")

        response = self.client.post(
            reverse("partner_plan_delete", args=[self.partner.pk, plano.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(PartnerPlan.objects.filter(pk=plano.pk).exists())

    def test_manage_lista_planos_existentes(self):
        PartnerPlan.objects.create(partner=self.partner, nome_plano="Plano 200 Mbps")

        response = self.client.get(reverse("partner_plan_manage", args=[self.partner.pk]))

        self.assertContains(response, "Plano 200 Mbps")


class PartnerAddHistoricoViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()

    def test_post_com_descricao_cria_comentario(self):
        response = self.client.post(
            reverse("partner_add_historico", args=[self.partner.pk]),
            {"descricao": "Anotacao de teste"},
        )

        self.assertEqual(response.status_code, 302)
        registro = services.listar_historico_partner(self.partner).get()
        self.assertEqual(registro.tipo, "comentario")
        self.assertEqual(registro.acao, "Anotacao de teste")

    def test_post_vazio_nao_cria_registro(self):
        response = self.client.post(reverse("partner_add_historico", args=[self.partner.pk]), {})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(services.listar_historico_partner(self.partner, incluir_arquivados=True).count(), 0)


class UpdatePartnerStatusViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)

    def test_bloqueia_transicao_invalida_a_partir_de_aguardando_contratacao(self):
        partner = _criar_partner(status="aguardando_contratacao")

        response = self.client.post(
            reverse("update_partner_status", args=[partner.pk]), {"status": "inativo"},
        )

        partner.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(partner.status, "aguardando_contratacao")

    def test_transicao_valida_atualiza_status_e_registra_historico(self):
        partner = _criar_partner(status="ativo")

        self.client.post(
            reverse("update_partner_status", args=[partner.pk]),
            {"status": "inativo", "observacao": "Encerrou o contrato"},
        )

        partner.refresh_from_db()
        self.assertEqual(partner.status, "inativo")
        registro = services.listar_historico_partner(partner).get()
        self.assertIn("PARCEIRO INATIVADO", registro.acao)
        self.assertIn("Encerrou o contrato", registro.acao)

    def test_status_desconhecido_e_ignorado_sem_alterar_partner(self):
        partner = _criar_partner(status="ativo")

        self.client.post(
            reverse("update_partner_status", args=[partner.pk]), {"status": "status-invalido"},
        )

        partner.refresh_from_db()
        self.assertEqual(partner.status, "ativo")
        self.assertEqual(services.listar_historico_partner(partner).count(), 0)


class UpdateWinbackStatusViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)

    def test_andamento_reativa_arquiva_historico_e_apaga_propostas(self):
        partner = _criar_partner(status="inativo")
        RegistroHistorico.objects.create(
            tipo="sistema", acao="Historico antigo", usuario=self.usuario,
            content_type=ContentType.objects.get_for_model(Partner),
            object_id=partner.id, arquivado=False,
        )
        _criar_proposal(partner, status="inviavel")

        response = self.client.post(
            reverse("update_winback_status", args=[partner.pk]), {"status": "andamento"},
        )

        partner.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(partner.status, "ativo")
        self.assertEqual(Proposal.objects.filter(partner=partner).count(), 0)
        self.assertEqual(services.listar_historico_partner(partner).count(), 1)
        self.assertEqual(services.listar_historico_partner(partner, incluir_arquivados=True).count(), 2)

    def test_negociacao_atualiza_status_sem_apagar_propostas(self):
        partner = _criar_partner(status="inativo")
        _criar_proposal(partner, status="inviavel")

        self.client.post(
            reverse("update_winback_status", args=[partner.pk]), {"status": "negociacao"},
        )

        partner.refresh_from_db()
        self.assertEqual(partner.status, "negociacao")
        self.assertEqual(Proposal.objects.filter(partner=partner).count(), 1)

    def test_status_desconhecido_nao_altera_partner(self):
        partner = _criar_partner(status="inativo")

        self.client.post(
            reverse("update_winback_status", args=[partner.pk]), {"status": "status-invalido"},
        )

        partner.refresh_from_db()
        self.assertEqual(partner.status, "inativo")


class PartnerClientsListViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.usuario)

    def test_agrupa_enderecos_distintos_por_cliente(self):
        partner = _criar_partner()
        cliente = Cliente.objects.create(
            id_ixc="901", razao_social="Cliente X", nome_fantasia="Cliente X", cnpj_cpf="00000000000200",
        )
        endereco = Endereco.objects.create(
            cliente=cliente, logradouro="Rua A", numero="1", bairro="Centro", cidade="Recife", estado="PE",
        )
        _criar_proposal(partner, status="analise", cliente=cliente, client_address=endereco)

        response = self.client.get(reverse("partner_clients_list", args=[partner.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["clientes_agrupados"], {cliente: [endereco]})


class PartnerServicesUnitTests(TestCase):
    def test_agrupar_propostas_convertidas_ignora_lote_repetido(self):
        partner = _criar_partner()
        _criar_proposal(partner, status="contratado", codigo_proposta="COT-1")
        _criar_proposal(partner, status="contratado", codigo_proposta="COT-1")
        _criar_proposal(partner, status="analise", codigo_proposta="COT-2")

        resultado = services.agrupar_propostas_convertidas_por_parceiro([partner.id])

        self.assertEqual(len(resultado[partner.id]), 1)

    def test_aplicar_transicao_status_partner_bloqueia_a_partir_de_aguardando_contratacao(self):
        partner = _criar_partner(status="aguardando_contratacao")
        usuario = get_user_model().objects.create_user(username="u1", password="senha-forte-123")

        estado, mensagem = services.aplicar_transicao_status_partner(partner, "inativo", usuario)

        self.assertEqual(estado, "bloqueado")
        self.assertIn("Contratado ou Declinado", mensagem)


class GestaoRelatoriosPropostaTestsBase(TestCase):
    """Base comum aos testes dos relatorios de gestao movidos de apps.core
    na PO-032 (donos do dado: Proposal, app partners)."""

    def setUp(self):
        self.gestor = get_user_model().objects.create_user(
            username="gestor", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.client.force_login(self.gestor)
        self.partner = _criar_partner()
        self.cliente = Cliente.objects.create(
            id_ixc="910", razao_social="Cliente Relatorio", nome_fantasia="Cliente Relatorio",
            cnpj_cpf="00000000000300",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Relatorio", numero="10",
            bairro="Centro", cidade="Recife", estado="PE", login_ixc="LOGIN-1",
        )


class GestaoRelatorioLoginStatusViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorio_login_status"))

        self.assertEqual(response.status_code, 403)

    def test_uma_linha_por_login_e_filtro_por_endereco(self):
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="COT-1",
        )
        outro_endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua B", numero="2", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-2",
        )
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=outro_endereco, codigo_proposta="COT-2",
        )

        response = self.client.get(reverse("gestao_relatorio_login_status"), {"endereco": "LOGIN-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["rows"]), 1)
        self.assertEqual(response.context["rows"][0]["login_nome"], "LOGIN-1")

    def test_export_csv(self):
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="COT-1",
        )

        response = self.client.get(reverse("gestao_relatorio_login_status"), {"export": "csv"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])


class GestaoRelatorioPropostaStatusViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorio_proposta_status"))

        self.assertEqual(response.status_code, 403)

    def test_agrupa_por_lote_e_conta_logins(self):
        _criar_proposal(self.partner, status="contratado", cliente=self.cliente, codigo_proposta="COT-1")
        _criar_proposal(self.partner, status="contratado", cliente=self.cliente, codigo_proposta="COT-1")
        _criar_proposal(self.partner, status="analise", cliente=self.cliente, codigo_proposta="COT-2")

        response = self.client.get(reverse("gestao_relatorio_proposta_status"))

        rows_por_codigo = {row["codigo_exibicao"]: row for row in response.context["page_obj"].object_list}
        self.assertEqual(rows_por_codigo["COT-1"]["total_logins"], 2)
        self.assertEqual(rows_por_codigo["COT-2"]["total_logins"], 1)

    def test_filtro_por_status(self):
        _criar_proposal(self.partner, status="contratado", cliente=self.cliente, codigo_proposta="COT-1")
        _criar_proposal(self.partner, status="declinado", cliente=self.cliente, codigo_proposta="COT-2")

        response = self.client.get(reverse("gestao_relatorio_proposta_status"), {"status": "contratado"})

        codigos = [row["codigo_exibicao"] for row in response.context["page_obj"].object_list]
        self.assertEqual(codigos, ["COT-1"])


class GestaoRelatorioStatusClienteViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorio_status_cliente"))

        self.assertEqual(response.status_code, 403)

    def test_agrupa_por_cliente_com_contagem_por_status(self):
        _criar_proposal(self.partner, status="contratado", cliente=self.cliente, codigo_proposta="COT-1")
        _criar_proposal(self.partner, status="analise", cliente=self.cliente, codigo_proposta="COT-2")

        response = self.client.get(reverse("gestao_relatorio_status_cliente"))

        linha = response.context["page_obj"].object_list[0]
        self.assertEqual(linha["cliente_nome"], "Cliente Relatorio")
        self.assertEqual(linha["total_cotacoes"], 2)
        self.assertEqual(linha["contratado"], 1)
        self.assertEqual(linha["em_negociacao"], 1)


class GestaoRelatorioCotacaoEnderecoViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorio_cotacao_endereco"))

        self.assertEqual(response.status_code, 403)

    def test_agrupa_por_endereco_com_contagem_por_status(self):
        _criar_proposal(
            self.partner, status="declinado", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="COT-1",
        )
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="COT-2",
        )

        response = self.client.get(reverse("gestao_relatorio_cotacao_endereco"))

        linha = response.context["page_obj"].object_list[0]
        self.assertEqual(linha["endereco_nome"], "LOGIN-1")
        self.assertEqual(linha["total_cotacoes"], 2)
        self.assertEqual(linha["declinado"], 1)


class GestaoRelatorioLoginUsuarioViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorio_login_usuario"))

        self.assertEqual(response.status_code, 403)

    def test_lista_somente_propostas_em_analise_e_totaliza_responsavel(self):
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, responsavel=self.gestor, codigo_proposta="COT-1",
        )
        _criar_proposal(self.partner, status="analise", cliente=self.cliente, codigo_proposta="COT-2")
        _criar_proposal(self.partner, status="contratado", cliente=self.cliente, codigo_proposta="COT-3")

        response = self.client.get(reverse("gestao_relatorio_login_usuario"))

        self.assertEqual(response.context["total_resultados"], 2)
        self.assertEqual(response.context["total_com_responsavel"], 1)
        self.assertEqual(response.context["total_sem_responsavel"], 1)

    def test_filtro_sem_responsavel(self):
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            responsavel=self.gestor, codigo_proposta="COT-1",
        )
        sem_responsavel = _criar_proposal(
            self.partner, status="analise", cliente=self.cliente, codigo_proposta="COT-2",
        )

        response = self.client.get(reverse("gestao_relatorio_login_usuario"), {"usuario": "__sem__"})

        pks = [row["pk"] for row in response.context["rows"]]
        self.assertEqual(pks, [sem_responsavel.pk])


class GestaoRelatorioLoginUsuarioResponsavelViewTests(GestaoRelatoriosPropostaTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        proposal = _criar_proposal(self.partner, status="analise", cliente=self.cliente)
        self.client.force_login(self.sem_permissao)

        response = self.client.post(
            reverse("gestao_relatorio_login_usuario_responsavel", args=[proposal.pk]),
            {"responsavel_id": str(self.gestor.pk)},
        )

        self.assertEqual(response.status_code, 403)

    def test_bloqueia_troca_fora_de_analise(self):
        proposal = _criar_proposal(self.partner, status="contratado", cliente=self.cliente)

        self.client.post(
            reverse("gestao_relatorio_login_usuario_responsavel", args=[proposal.pk]),
            {"responsavel_id": str(self.gestor.pk)},
        )

        proposal.refresh_from_db()
        self.assertIsNone(proposal.responsavel)

    def test_bloqueia_sem_usuario_selecionado(self):
        proposal = _criar_proposal(self.partner, status="analise", cliente=self.cliente)

        self.client.post(
            reverse("gestao_relatorio_login_usuario_responsavel", args=[proposal.pk]), {},
        )

        proposal.refresh_from_db()
        self.assertIsNone(proposal.responsavel)

    def test_atualiza_responsavel_e_registra_historico(self):
        proposal = _criar_proposal(
            self.partner, status="analise", cliente=self.cliente, codigo_proposta="COT-1",
        )

        response = self.client.post(
            reverse("gestao_relatorio_login_usuario_responsavel", args=[proposal.pk]),
            {"responsavel_id": str(self.gestor.pk)},
        )

        proposal.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.responsavel, self.gestor)
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
        )
        self.assertIn("Responsável do login atualizado", registro.acao)


class ProposalCrudTestsBase(TestCase):
    """Base comum aos testes da sub-fatia "CRUD e navegacao" do grupo
    Proposta (PO-011)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()
        self.cliente = Cliente.objects.create(
            id_ixc="920", razao_social="Cliente Proposta", nome_fantasia="Cliente Proposta",
            cnpj_cpf="00000000000400",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Proposta", numero="1", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-PROPOSTA",
        )


class ProposalCreateViewTests(ProposalCrudTestsBase):
    def test_cria_proposal_e_redireciona_para_edicao(self):
        response = self.client.get(reverse("proposal_create", args=[self.partner.pk]))

        proposal = Proposal.objects.get(partner=self.partner)
        self.assertRedirects(response, reverse("proposal_update", args=[proposal.pk]))
        self.assertTrue(proposal.codigo_proposta)
        self.assertEqual(proposal.grupo_proposta_id, proposal.id)
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
        )
        self.assertIn("Proposta iniciada", registro.acao)

    def test_cria_proposal_vinculada_a_endereco(self):
        self.client.get(
            reverse("proposal_create", args=[self.partner.pk]), {"endereco": self.endereco.pk},
        )

        proposal = Proposal.objects.get(partner=self.partner)
        self.assertEqual(proposal.client_address, self.endereco)
        self.assertEqual(proposal.cliente, self.cliente)


class ProposalDetailViewTests(ProposalCrudTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("proposal_detail", args=[proposal.pk]))

        self.assertEqual(response.status_code, 403)

    def test_lista_historico_do_periodo_atual(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")
        RegistroHistorico.objects.create(
            tipo="comentario", acao="Comentario de hoje", usuario=self.usuario,
            content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
        )

        response = self.client.get(reverse("proposal_detail", args=[proposal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Comentario de hoje")


class ProposalAssumirResponsavelViewTests(ProposalCrudTestsBase):
    def test_bloqueia_fora_de_analise(self):
        proposal = _criar_proposal(self.partner, status="contratado", codigo_proposta="COT-1")

        self.client.post(reverse("proposal_assumir_responsavel", args=[proposal.pk]))

        proposal.refresh_from_db()
        self.assertIsNone(proposal.responsavel)

    def test_ja_responsavel_nao_duplica_historico(self):
        proposal = _criar_proposal(
            self.partner, status="analise", codigo_proposta="COT-1", responsavel=self.usuario,
        )

        self.client.post(reverse("proposal_assumir_responsavel", args=[proposal.pk]))

        self.assertEqual(
            RegistroHistorico.objects.filter(
                content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
            ).count(),
            0,
        )

    def test_atualiza_responsavel_e_registra_historico(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        response = self.client.post(reverse("proposal_assumir_responsavel", args=[proposal.pk]))

        proposal.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.responsavel, self.usuario)
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
        )
        self.assertIn("Responsável do login atualizado", registro.acao)


class ProposalAddHistoricoViewTests(ProposalCrudTestsBase):
    def test_post_com_descricao_cria_comentario(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        self.client.post(
            reverse("proposal_add_historico", args=[proposal.pk]), {"descricao": "Nota da cotacao"},
        )

        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
        )
        self.assertEqual(registro.tipo, "comentario")
        self.assertEqual(registro.acao, "Nota da cotacao")

    def test_post_vazio_nao_cria_registro(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        self.client.post(reverse("proposal_add_historico", args=[proposal.pk]), {})

        self.assertFalse(
            RegistroHistorico.objects.filter(
                content_type=ContentType.objects.get_for_model(Proposal), object_id=proposal.id,
            ).exists()
        )


class ProposalStatusUpdateViewTests(ProposalCrudTestsBase):
    def test_status_invalido(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        response = self.client.post(
            reverse("proposal_status_update", args=[proposal.pk]), {"status": "status-invalido"},
        )

        proposal.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.status, "analise")

    def test_status_ativa_redireciona_para_edicao(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        response = self.client.post(
            reverse("proposal_status_update", args=[proposal.pk]), {"status": "ativa"},
        )

        proposal.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('proposal_update', args=[proposal.pk])}?modo=convertida&status_pendente=ativa",
            fetch_redirect_response=False,
        )
        self.assertEqual(proposal.status, "analise")

    def test_sem_mudanca_nao_gera_auditoria_nem_historico(self):
        proposal = _criar_proposal(self.partner, status="declinado", codigo_proposta="COT-1")

        self.client.post(reverse("proposal_status_update", args=[proposal.pk]), {"status": "declinado"})

        self.assertFalse(CotacaoStatusAuditoria.objects.filter(proposal=proposal).exists())

    def test_atualizado_gera_auditoria_e_historico(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        response = self.client.post(
            reverse("proposal_status_update", args=[proposal.pk]), {"status": "declinado"},
        )

        proposal.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(proposal.status, "declinado")
        auditoria = CotacaoStatusAuditoria.objects.get(proposal=proposal)
        self.assertEqual(auditoria.status_anterior, "analise")
        self.assertEqual(auditoria.status_novo, "declinado")
        self.assertEqual(auditoria.origem, "alteracao_individual")
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Partner), object_id=self.partner.id,
        )
        self.assertIn("Status da proposta atualizado", registro.acao)


class ProposalDeleteViewTests(ProposalCrudTestsBase):
    def test_deleta_e_redireciona_para_o_parceiro(self):
        proposal = _criar_proposal(self.partner, status="analise", codigo_proposta="COT-1")

        response = self.client.post(reverse("proposal_delete", args=[proposal.pk]))

        self.assertRedirects(response, reverse("partner_detail", args=[self.partner.pk]))
        self.assertFalse(Proposal.objects.filter(pk=proposal.pk).exists())


class ProposalGlobalListViewTests(ProposalCrudTestsBase):
    def test_exclui_status_finalizados_e_soma_receita(self):
        _criar_proposal(
            self.partner, status="analise", codigo_proposta="COT-1", valor_mensal=Decimal("100.00"),
        )
        _criar_proposal(
            self.partner, status="contratado", codigo_proposta="COT-2", valor_mensal=Decimal("200.00"),
        )

        response = self.client.get(reverse("proposal_global_list"))

        codigos = [p.codigo_exibicao for p in response.context["proposals"]]
        self.assertEqual(codigos, ["COT-1"])
        self.assertEqual(response.context["total_receita"], 100)


class AddressProposalsListViewTests(ProposalCrudTestsBase):
    def test_lista_apenas_propostas_em_aberto_do_endereco(self):
        _criar_proposal(
            self.partner, status="analise", client_address=self.endereco, codigo_proposta="COT-1",
        )
        outro_endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Y", numero="2", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-Y",
        )
        _criar_proposal(
            self.partner, status="analise", client_address=outro_endereco, codigo_proposta="COT-2",
        )

        response = self.client.get(reverse("address_proposals_list", args=[self.endereco.pk]))

        codigos = [p.codigo_exibicao for p in response.context["proposals"]]
        self.assertEqual(codigos, ["COT-1"])


class ProposalBatchTestsBase(TestCase):
    """Base comum aos testes da sub-fatia "Lote" do grupo Proposta (PO-011)."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()
        self.cliente = Cliente.objects.create(
            id_ixc="930", razao_social="Cliente Lote", nome_fantasia="Cliente Lote",
            cnpj_cpf="00000000000500",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Lote", numero="1", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-LOTE",
        )
        self.proposal = _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="LOTE-1",
        )


class ProposalBatchDetailViewTests(ProposalBatchTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("proposal_batch_detail", args=[self.proposal.pk]))

        self.assertEqual(response.status_code, 403)

    def test_total_logins_lote_conta_todas_as_propostas_do_codigo(self):
        _criar_proposal(self.partner, status="analise", codigo_proposta="LOTE-1")

        response = self.client.get(reverse("proposal_batch_detail", args=[self.proposal.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_logins_lote"], 2)

    def test_deduplica_historico_replicado_no_mesmo_instante(self):
        outro_login = _criar_proposal(self.partner, status="analise", codigo_proposta="LOTE-1")
        momento = timezone.now()
        proposal_content_type = ContentType.objects.get_for_model(Proposal)
        for proposta in (self.proposal, outro_login):
            registro = RegistroHistorico.objects.create(
                tipo="comentario", acao="Nota replicada", usuario=self.usuario,
                content_type=proposal_content_type, object_id=proposta.id,
            )
            RegistroHistorico.objects.filter(pk=registro.pk).update(data=momento)

        response = self.client.get(reverse("proposal_batch_detail", args=[self.proposal.pk]))

        historico_lote = response.context["historico_lote"]
        self.assertEqual(len(historico_lote), 1)
        self.assertTrue(historico_lote[0]["replicado_lote"])
        self.assertEqual(historico_lote[0]["quantidade_afetada"], 2)

    def test_alerta_os_lastmile_quando_endereco_tem_os_aberta(self):
        self.endereco.ticket_os_atual_ixc = "12345"
        self.endereco.os_atual_aberta = True
        self.endereco.em_os_comercial_lastmile = True
        self.endereco.save()

        response = self.client.get(reverse("proposal_batch_detail", args=[self.proposal.pk]))

        self.assertTrue(response.context["possui_os_lastmile"])

    def test_outras_cotacoes_em_negociacao_no_mesmo_endereco(self):
        outro_partner = _criar_partner(cnpj_cpf="22222222000188")
        _criar_proposal(
            outro_partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="OUTRO-LOTE",
        )

        response = self.client.get(reverse("proposal_batch_detail", args=[self.proposal.pk]))

        self.assertEqual(response.context["outras_cotacoes_abertas_qtd"], 1)


class ProposalBatchLoginsViewTests(ProposalBatchTestsBase):
    def test_lista_apenas_propostas_do_mesmo_lote(self):
        outro_login = _criar_proposal(self.partner, status="analise", codigo_proposta="LOTE-1")
        _criar_proposal(self.partner, status="analise", codigo_proposta="OUTRO-LOTE")

        response = self.client.get(reverse("proposal_batch_logins", args=[self.proposal.pk]))

        pks = {p.pk for p in response.context["proposals_lote"]}
        self.assertEqual(pks, {self.proposal.pk, outro_login.pk})


class ProposalBatchAddHistoricoViewTests(ProposalBatchTestsBase):
    def test_post_replica_historico_para_todas_as_propostas_do_lote(self):
        outro_login = _criar_proposal(self.partner, status="analise", codigo_proposta="LOTE-1")

        self.client.post(
            reverse("proposal_batch_add_historico", args=[self.proposal.pk]),
            {"descricao": "Nota do lote"},
        )

        proposal_content_type = ContentType.objects.get_for_model(Proposal)
        for proposta in (self.proposal, outro_login):
            registro = RegistroHistorico.objects.get(
                content_type=proposal_content_type, object_id=proposta.id,
            )
            self.assertEqual(registro.acao, "Nota do lote")
            self.assertEqual(registro.tipo, "comentario")

    def test_post_vazio_nao_cria_registro(self):
        self.client.post(reverse("proposal_batch_add_historico", args=[self.proposal.pk]), {})

        self.assertFalse(
            RegistroHistorico.objects.filter(
                content_type=ContentType.objects.get_for_model(Proposal), object_id=self.proposal.id,
            ).exists()
        )


def _form_data_from_proposal(proposal, **overrides):
    """Monta um POST valido para ProposalForm a partir dos valores atuais
    da instancia (que ja satisfazem os campos obrigatorios, preenchidos
    pelos defaults do model na criacao)."""
    data = {
        'cliente': proposal.cliente_id or '',
        'client_address': proposal.client_address_id or '',
        'status': proposal.status,
        'nome_proposta': proposal.nome_proposta or '',
        'velocidade': proposal.velocidade,
        'tecnologia': proposal.tecnologia,
        'disponibilidade': proposal.disponibilidade,
        'mttr': proposal.mttr,
        'perda_pacote': proposal.perda_pacote,
        'latencia': proposal.latencia,
        'interfaces': proposal.interfaces,
        'tipo_acesso': proposal.tipo_acesso or '',
        'ipv4_bloco': proposal.ipv4_bloco or '',
        'dupla_abordagem': proposal.dupla_abordagem or '',
        'entrega_rb': proposal.entrega_rb or '',
        'designador': proposal.designador or '',
        'trunk': proposal.trunk,
        'dhcp': proposal.dhcp,
        'prazo_ativacao': proposal.prazo_ativacao or '',
        'contato_suporte': proposal.contato_suporte or '',
        'telefone_suporte': proposal.telefone_suporte or '',
        'ticket_cliente': proposal.ticket_cliente or '',
        'valor_mensal': proposal.valor_mensal or '',
        'ticket_empresa': proposal.ticket_empresa or '',
        'taxa_instalacao': proposal.taxa_instalacao or '',
        'valor_parceiro': proposal.valor_parceiro or '',
        'tempo_contrato': proposal.tempo_contrato,
        'email_faturamento': proposal.email_faturamento or '',
        'partner_cnpj_cpf': proposal.partner.cnpj_cpf or '',
    }
    data.update(overrides)
    return data


class ProposalFechamentoTestsBase(TestCase):
    """Base comum aos testes da sub-fatia "Fechamento de O.S. e edicao
    financeira" do grupo Proposta (PO-011) — a de maior risco: RN-017/
    RN-018, integracao com o IXCGateway e calculo financeiro."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="parceiro", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.client.force_login(self.usuario)
        self.partner = _criar_partner()
        self.cliente = Cliente.objects.create(
            id_ixc="940", razao_social="Cliente Fechamento", nome_fantasia="Cliente Fechamento",
            cnpj_cpf="00000000000600",
        )
        self.endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Fechamento", numero="1", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-FECHAMENTO",
        )
        self.proposal = _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="FECH-1",
        )

    def _marcar_endereco_com_os_lastmile(self):
        self.endereco.ticket_os_atual_ixc = "555"
        self.endereco.os_atual_aberta = True
        self.endereco.em_os_comercial_lastmile = True
        self.endereco.save()


class ProposalBatchStatusUpdateViewTests(ProposalFechamentoTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]), {"status": "declinado"},
        )

        self.assertEqual(response.status_code, 403)

    def test_status_invalido(self):
        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]), {"status": "status-invalido"},
        )

        self.proposal.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "analise")

    def test_encerrada_sem_motivo_ativo(self):
        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {"status": "encerrada", "observacao_inviavel": "Sem viabilidade tecnica"},
        )

        self.proposal.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "analise")

    def test_encerrada_sem_observacao(self):
        motivo = ProposalMotivoInviavel.objects.create(nome="Sem infraestrutura", status="ativo")

        self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {"status": "encerrada", "motivo_inviavel": str(motivo.pk)},
        )

        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, "analise")

    def test_encerrada_observacao_muito_longa(self):
        motivo = ProposalMotivoInviavel.objects.create(nome="Sem infraestrutura", status="ativo")

        self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {"status": "encerrada", "motivo_inviavel": str(motivo.pk), "observacao_inviavel": "x" * 151},
        )

        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, "analise")

    def test_encerrada_sucesso_atualiza_lote_e_registra_auditoria(self):
        outro_login = _criar_proposal(self.partner, status="analise", codigo_proposta="FECH-1")
        motivo = ProposalMotivoInviavel.objects.create(nome="Sem infraestrutura", status="ativo")

        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {
                "status": "encerrada",
                "motivo_inviavel": str(motivo.pk),
                "observacao_inviavel": "Regiao sem cobertura",
            },
        )

        self.proposal.refresh_from_db()
        outro_login.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "encerrada")
        self.assertEqual(outro_login.status, "encerrada")
        self.assertEqual(self.proposal.motivo_inviavel, motivo)
        auditoria = CotacaoStatusAuditoria.objects.get(proposal=self.proposal)
        self.assertEqual(auditoria.origem, "alteracao_lote")

    def test_sem_mudanca_nao_gera_auditoria(self):
        self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]), {"status": "analise"},
        )

        self.assertFalse(CotacaoStatusAuditoria.objects.filter(proposal=self.proposal).exists())

    def test_ativa_redireciona_para_edicao_com_querystring(self):
        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]), {"status": "ativa"},
        )

        self.proposal.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('proposal_update', args=[self.proposal.pk])}?modo=convertida&status_pendente=ativa&fechar_outras_cotacoes=nao",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.proposal.status, "analise")

    def test_contratado_redireciona_para_lista_de_parceiros(self):
        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]), {"status": "contratado"},
        )

        self.assertRedirects(response, reverse("partner_list"))

    def test_aguardando_contratacao_sem_alterar_ixc(self):
        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {"status": "aguardando_contratacao"},
        )

        self.proposal.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "aguardando_contratacao")

    def test_aguardando_contratacao_com_ixc_sem_observacao(self):
        self._marcar_endereco_com_os_lastmile()

        self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {"status": "aguardando_contratacao", "alterar_os_ixc": "sim"},
        )

        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, "analise")

    @patch("apps.partners.services.finalizar_os_existente")
    def test_aguardando_contratacao_com_ixc_sucesso(self, mock_finalizar):
        self._marcar_endereco_com_os_lastmile()
        mock_finalizar.return_value = {"ok": True, "already_closed": False}

        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {
                "status": "aguardando_contratacao",
                "alterar_os_ixc": "sim",
                "observacao_contratacao": "Fechando O.S. para contratacao",
            },
        )

        self.proposal.refresh_from_db()
        self.endereco.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "aguardando_contratacao")
        self.assertFalse(self.endereco.os_atual_aberta)
        mock_finalizar.assert_called_once()
        auditoria = CotacaoStatusAuditoria.objects.get(proposal=self.proposal)
        self.assertTrue(auditoria.integrou_ixc)

    @patch("apps.partners.services.finalizar_os_existente")
    def test_aguardando_contratacao_com_ixc_falha(self, mock_finalizar):
        self._marcar_endereco_com_os_lastmile()
        mock_finalizar.return_value = {"ok": False, "message": "Falha simulada no IXC", "body": {}}

        response = self.client.post(
            reverse("proposal_batch_status_update", args=[self.proposal.pk]),
            {
                "status": "aguardando_contratacao",
                "alterar_os_ixc": "sim",
                "observacao_contratacao": "Fechando O.S. para contratacao",
            },
        )

        self.proposal.refresh_from_db()
        self.assertRedirects(response, reverse("proposal_batch_detail", args=[self.proposal.pk]))
        self.assertEqual(self.proposal.status, "analise")


class ProposalUpdateViewTests(ProposalFechamentoTestsBase):
    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("proposal_update", args=[self.proposal.pk]))

        self.assertEqual(response.status_code, 403)

    def test_edicao_normal_registra_historico_com_antes_e_depois(self):
        dados = _form_data_from_proposal(self.proposal, nome_proposta="Nome Editado")

        response = self.client.post(reverse("proposal_update", args=[self.proposal.pk]), dados)

        self.proposal.refresh_from_db()
        self.assertRedirects(response, reverse("partner_detail", args=[self.partner.pk]))
        self.assertEqual(self.proposal.nome_proposta, "Nome Editado")
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=self.proposal.id,
        )
        self.assertIn("Nome Editado", registro.acao)

    def test_adiciona_endereco_extra_cria_link(self):
        outro_endereco = Endereco.objects.create(
            cliente=self.cliente, logradouro="Rua Extra", numero="9", bairro="Centro",
            cidade="Recife", estado="PE", login_ixc="LOGIN-EXTRA",
        )
        dados = _form_data_from_proposal(self.proposal)
        dados["enderecos_selecionados"] = [str(self.endereco.pk), str(outro_endereco.pk)]

        self.client.post(reverse("proposal_update", args=[self.proposal.pk]), dados)

        self.proposal.refresh_from_db()
        clone = Proposal.objects.get(codigo_proposta=self.proposal.codigo_proposta, client_address=outro_endereco)
        self.assertEqual(clone.grupo_proposta_id, self.proposal.grupo_proposta_id)
        registro = RegistroHistorico.objects.get(
            content_type=ContentType.objects.get_for_model(Proposal), object_id=clone.id,
        )
        self.assertIn("Link criado a partir da proposta principal", registro.acao)

    def test_conversao_sem_lastmile_atualiza_status_e_redireciona(self):
        dados = _form_data_from_proposal(self.proposal)

        response = self.client.post(
            f"{reverse('proposal_update', args=[self.proposal.pk])}?modo=convertida", dados,
        )

        self.proposal.refresh_from_db()
        self.partner.refresh_from_db()
        self.assertRedirects(response, reverse("partner_list"))
        self.assertEqual(self.proposal.status, "aguardando_contratacao")
        auditoria = CotacaoStatusAuditoria.objects.get(proposal=self.proposal)
        self.assertEqual(auditoria.origem, "conversao_viavel")

    def test_conversao_bloqueada_por_outras_cotacoes_sem_decisao(self):
        _criar_proposal(
            self.partner, status="analise", cliente=self.cliente,
            client_address=self.endereco, codigo_proposta="OUTRO-FECH",
        )
        self._marcar_endereco_com_os_lastmile()
        dados = _form_data_from_proposal(self.proposal)
        dados["alterar_os_ixc"] = "sim"
        dados["observacao_contratacao"] = "Fechando O.S."

        response = self.client.post(
            f"{reverse('proposal_update', args=[self.proposal.pk])}?modo=convertida", dados,
        )

        self.proposal.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.proposal.status, "analise")

    @patch("apps.partners.services.finalizar_os_existente")
    def test_conversao_com_ixc_sucesso_fecha_fila_lastmile(self, mock_finalizar):
        self._marcar_endereco_com_os_lastmile()
        mock_finalizar.return_value = {"ok": True, "already_closed": False}
        dados = _form_data_from_proposal(self.proposal)
        dados["alterar_os_ixc"] = "sim"
        dados["observacao_contratacao"] = "Fechando O.S. antes da contratacao"

        response = self.client.post(
            f"{reverse('proposal_update', args=[self.proposal.pk])}?modo=convertida", dados,
        )

        self.proposal.refresh_from_db()
        self.endereco.refresh_from_db()
        self.assertRedirects(response, reverse("partner_list"))
        self.assertEqual(self.proposal.status, "aguardando_contratacao")
        self.assertFalse(self.endereco.em_os_comercial_lastmile)
        mock_finalizar.assert_called_once()
