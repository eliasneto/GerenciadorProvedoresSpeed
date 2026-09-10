import datetime
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core import email_tracking, services, views
from apps.core.admin import IntegrationAuditAdmin
from apps.core.admin_integration_exports import build_integration_audit_export
from apps.core.models import IntegrationAudit, IntegrationAuditItem, RegistroHistorico
from apps.partners.models import Partner


class IntegrationAuditExportTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="senha-forte-123",
        )
        self.audit = IntegrationAudit.objects.create(
            integration="logins_ixc",
            action="importacao_planilha",
            usuario=self.user,
            arquivo_nome="importacao_teste.xlsx",
            total_registros=2,
            total_sucessos=1,
            total_erros=1,
            detalhes_json={"colunas": ["Cliente_ID", "Login_Login", "Plano_ID"]},
        )
        IntegrationAuditItem.objects.create(
            audit=self.audit,
            linha_numero=2,
            status="erro",
            mensagem="IXC Negou: Login ja existe!",
            dados_json={
                "Cliente_ID": 575,
                "Login_Login": "CEF_POLIVALENTE",
                "Plano_ID": 27,
                "End_CEP": "70390-130",
            },
        )

    def test_build_export_abre_colunas_do_json(self):
        resumo, itens = build_integration_audit_export(self.audit)

        self.assertEqual(resumo[0]["Arquivo"], "importacao_teste.xlsx")
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["Cliente_ID"], 575)
        self.assertEqual(itens[0]["Login_Login"], "CEF_POLIVALENTE")
        self.assertEqual(itens[0]["Plano_ID"], 27)
        self.assertEqual(itens[0]["End_CEP"], "70390-130")

    def test_admin_exporta_csv(self):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = IntegrationAuditAdmin(IntegrationAudit, AdminSite())

        response = admin_obj.exportar_itens_integracao(request, str(self.audit.pk), "csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment; filename=\"log_integracao_", response["Content-Disposition"])
        conteudo = response.content.decode("utf-8-sig")
        self.assertIn("Cliente_ID", conteudo)
        self.assertIn("CEF_POLIVALENTE", conteudo)

    def test_admin_exporta_excel(self):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = IntegrationAuditAdmin(IntegrationAudit, AdminSite())

        response = admin_obj.exportar_itens_integracao(request, str(self.audit.pk), "xlsx")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response["Content-Type"],
        )
        self.assertTrue(response.content.startswith(b"PK"))


class DocsPortalTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        diagrams_dir = Path(self.tmp_dir.name)
        (diagrams_dir / "exemplo-diagrama.html").write_text(
            "<html><body>Exemplo</body></html>", encoding="utf-8"
        )
        (diagrams_dir / "nao-e-diagrama.json").write_text("{}", encoding="utf-8")

        patcher = mock.patch("apps.core.services.DOCS_DIAGRAMS_DIR", diagrams_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_docs_index_acessivel_sem_login_e_lista_documento(self):
        response = self.client.get(reverse("docs_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exemplo-diagrama.html")
        self.assertNotContains(response, "nao-e-diagrama.json")

    def test_docs_documento_existente_e_servido_sem_login(self):
        response = self.client.get(
            reverse("docs_documento", kwargs={"nome_arquivo": "exemplo-diagrama.html"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Exemplo", response.content.decode("utf-8"))

    def test_docs_documento_inexistente_retorna_404(self):
        response = self.client.get(
            reverse("docs_documento", kwargs={"nome_arquivo": "nao-existe.html"})
        )

        self.assertEqual(response.status_code, 404)

    def test_docs_documento_bloqueia_extensao_diferente_de_html(self):
        response = self.client.get(
            reverse("docs_documento", kwargs={"nome_arquivo": "nao-e-diagrama.json"})
        )

        self.assertEqual(response.status_code, 404)


class SystemHealthViewTests(TestCase):
    def setUp(self):
        services._HEALTHCHECK_CACHE.update({'checked_at': 0.0, 'db_ok': True, 'error': ''})

    def test_system_health_ok(self):
        response = self.client.get(reverse("system_health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["db"], "online")

    def test_system_health_banco_indisponivel_retorna_503(self):
        with mock.patch("apps.core.services.connection.ensure_connection", side_effect=Exception("sem conexao")):
            response = self.client.get(reverse("system_health"))

        self.assertEqual(response.status_code, 503)
        corpo = response.json()
        self.assertEqual(corpo["db"], "offline")
        self.assertIn("error", corpo)


class GestaoRelatoriosViewTests(TestCase):
    def setUp(self):
        self.gestor = get_user_model().objects.create_user(
            username="gestor", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("gestao_relatorios"))

        self.assertEqual(response.status_code, 403)

    def test_lista_catalogo_de_relatorios(self):
        self.client.force_login(self.gestor)

        response = self.client.get(reverse("gestao_relatorios"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Responsáveis por Endereço")
        self.assertContains(response, "Status por Cotação")

    def test_busca_filtra_catalogo(self):
        self.client.force_login(self.gestor)

        response = self.client.get(reverse("gestao_relatorios"), {"relatorio": "Cotação por Cliente"})

        self.assertContains(response, "Cotação por Cliente")
        self.assertNotContains(response, "Status por Endereço")


class FiltrarLogsIntegracaoServiceTests(TestCase):
    """Cobre a logica de filtro extraida para `services.filtrar_logs_integracao`.

    `gestao_logs_integracoes`/`gestao_log_integracao_detail` nao possuem rota
    registrada em nenhum urls.py do projeto e os templates fazem
    `{% url 'gestao_logs_integracoes' %}` (inexistente) - achado durante a
    PO-011 (fatia core): as views quebram mesmo sendo chamadas diretamente,
    antes desta fatia e sem relacao com ela. Por isso a cobertura de HTTP
    fica limitada ao bloqueio de permissao (que ocorre antes do render); a
    logica de filtro em si e testada aqui, no nivel de servico.
    """

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="gestor", password="senha-forte-123",
        )
        self.audit_ixc = IntegrationAudit.objects.create(
            integration="cadastro_cliente_ixc",
            action="execucao_integracao",
            usuario=self.usuario,
            arquivo_nome="clientes.xlsx",
        )
        self.audit_leads = IntegrationAudit.objects.create(
            integration="importador_leads",
            action="importacao_planilha",
            usuario=self.usuario,
            arquivo_nome="leads.xlsx",
        )

    def test_filtra_por_integracao(self):
        resultado = services.filtrar_logs_integracao(integracao="cadastro_cliente_ixc")

        self.assertEqual(list(resultado), [self.audit_ixc])

    def test_filtra_por_acao(self):
        resultado = services.filtrar_logs_integracao(acao="importacao_planilha")

        self.assertEqual(list(resultado), [self.audit_leads])

    def test_filtra_por_busca_no_nome_do_arquivo(self):
        resultado = services.filtrar_logs_integracao(busca="leads")

        self.assertEqual(list(resultado), [self.audit_leads])

    def test_filtra_por_usuario(self):
        outro_usuario = get_user_model().objects.create_user(
            username="outro", password="senha-forte-123",
        )
        IntegrationAudit.objects.create(
            integration="importador_leads", action="importacao_planilha", usuario=outro_usuario,
        )

        resultado = services.filtrar_logs_integracao(usuario_id=str(self.usuario.pk))

        self.assertEqual(set(resultado), {self.audit_ixc, self.audit_leads})

    def test_sem_filtro_retorna_todos(self):
        resultado = services.filtrar_logs_integracao()

        self.assertEqual(resultado.count(), 2)

    def test_data_invalida_e_ignorada_silenciosamente(self):
        resultado = services.filtrar_logs_integracao(data_inicio="data-invalida")

        self.assertEqual(resultado.count(), 2)


class GestaoLogsIntegracoesPermissaoTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )

    def test_gestao_logs_integracoes_bloqueia_usuario_sem_permissao(self):
        request = self.factory.get("/")
        request.user = self.sem_permissao

        with self.assertRaises(PermissionDenied):
            views.gestao_logs_integracoes(request)

    def test_gestao_log_integracao_detail_bloqueia_usuario_sem_permissao(self):
        audit = IntegrationAudit.objects.create(
            integration="cadastro_cliente_ixc", action="execucao_integracao",
        )
        request = self.factory.get("/")
        request.user = self.sem_permissao

        with self.assertRaises(PermissionDenied):
            views.gestao_log_integracao_detail(request, audit.pk)


class TimelineGlobalViewTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="operacao", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao", password="senha-forte-123",
        )
        self.parceiro = Partner.objects.create(
            nome_fantasia="Parceiro Teste",
            razao_social="Parceiro Teste LTDA",
            cnpj_cpf="33333333000133",
            status="ativo",
        )
        self.content_type = ContentType.objects.get_for_model(Partner)
        self.url = reverse(
            "timeline_global",
            args=["partners", "partner", self.parceiro.id],
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_get_lista_historico_do_periodo_atual(self):
        RegistroHistorico.objects.create(
            tipo="comentario",
            acao="Registro de hoje",
            usuario=self.usuario,
            content_type=self.content_type,
            object_id=self.parceiro.id,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registro de hoje")

    def test_exibe_nome_do_autor_em_vez_do_email(self):
        """PO-080: card do historico mostra o nome da pessoa, sem o dominio
        do e-mail/AD (`item.usuario.email` trocado por
        `get_full_name|default:username`)."""
        autor = get_user_model().objects.create_user(
            username="autor.timeline", email="autor.timeline@howbe.local", password="senha-forte-123",
            first_name="Autor", last_name="Timeline",
        )
        RegistroHistorico.objects.create(
            tipo="comentario", acao="Comentario do autor", usuario=autor,
            content_type=self.content_type, object_id=self.parceiro.id,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(self.url)

        self.assertContains(response, "Autor Timeline")
        self.assertNotContains(response, "autor.timeline@howbe.local")

    def test_post_cria_comentario_e_redireciona(self):
        self.client.force_login(self.usuario)

        response = self.client.post(self.url, {"descricao": "Comentario via teste"})

        self.assertEqual(response.status_code, 302)
        registro = RegistroHistorico.objects.get(
            content_type=self.content_type, object_id=self.parceiro.id,
        )
        self.assertEqual(registro.tipo, "comentario")
        self.assertEqual(registro.acao, "Comentario via teste")
        self.assertEqual(registro.usuario, self.usuario)

    def test_post_com_arquivo_cria_anexo(self):
        self.client.force_login(self.usuario)
        arquivo = SimpleUploadedFile("nota.txt", b"conteudo", content_type="text/plain")

        response = self.client.post(self.url, {"arquivo": arquivo})

        self.assertEqual(response.status_code, 302)
        registro = RegistroHistorico.objects.get(
            content_type=self.content_type, object_id=self.parceiro.id,
        )
        self.assertEqual(registro.tipo, "anexo")

    def test_post_vazio_nao_cria_registro(self):
        self.client.force_login(self.usuario)

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            RegistroHistorico.objects.filter(
                content_type=self.content_type, object_id=self.parceiro.id,
            ).exists()
        )


class EmailTrackingTests(TestCase):
    """PO-066/RN-042/RN-043: numero de rastreio do e-mail de Escola/RE/RI/
    Mapa Calor — data do envio + INEP + sufixo do nivel, embutido no
    assunto do jeito que `apps.integracoes.email` reconhece na resposta."""

    def test_montar_codigo_rastreio_re(self):
        codigo = email_tracking.montar_codigo_rastreio(
            "12345678", email_tracking.NIVEL_RE, data_envio=datetime.date(2026, 8, 11),
        )

        self.assertEqual(codigo, "ESC-20260811-12345678-RE")

    def test_montar_codigo_rastreio_mc(self):
        codigo = email_tracking.montar_codigo_rastreio(
            "12345678", email_tracking.NIVEL_MC, data_envio=datetime.date(2026, 8, 11),
        )

        self.assertEqual(codigo, "ESC-20260811-12345678-MC")

    def test_montar_codigo_rastreio_global(self):
        codigo = email_tracking.montar_codigo_rastreio(
            "12345678", email_tracking.NIVEL_GLOBAL, data_envio=datetime.date(2026, 8, 11),
        )

        self.assertEqual(codigo, "ESC-20260811-12345678-Global")

    def test_montar_codigo_rastreio_sanitiza_inep_com_caracteres_invalidos(self):
        codigo = email_tracking.montar_codigo_rastreio(
            "1234.5678-A", email_tracking.NIVEL_RI, data_envio=datetime.date(2026, 8, 11),
        )

        self.assertEqual(codigo, "ESC-20260811-12345678A-RI")

    def test_montar_codigo_rastreio_nivel_invalido_gera_erro(self):
        with self.assertRaises(ValueError):
            email_tracking.montar_codigo_rastreio("12345678", "outro")

    def test_montar_assunto_com_codigo_prefixa_uma_vez(self):
        codigo = "ESC-20260811-12345678-RE"

        assunto = email_tracking.montar_assunto_com_codigo(codigo, "Documentacao pendente")
        self.assertEqual(assunto, f"#{codigo} - Documentacao pendente")

        # Nao duplica o prefixo se o usuario ja tiver incluido.
        assunto_ja_prefixado = email_tracking.montar_assunto_com_codigo(codigo, assunto)
        self.assertEqual(assunto_ja_prefixado, assunto)

    def test_extrair_codigos_rastreio_reconhece_re_ri_e_global(self):
        assunto = "RE: #ESC-20260811-12345678-RE sobre a instalacao"
        self.assertEqual(
            email_tracking.extrair_codigos_rastreio(assunto), ["ESC-20260811-12345678-RE"],
        )
        self.assertEqual(
            email_tracking.extrair_codigos_rastreio("#ESC-20260811-12345678-ri texto"),
            ["ESC-20260811-12345678-RI"],
        )
        self.assertEqual(
            email_tracking.extrair_codigos_rastreio("#esc-20260811-12345678-global texto"),
            ["ESC-20260811-12345678-Global"],
        )
        self.assertEqual(
            email_tracking.extrair_codigos_rastreio("#ESC-20260811-12345678-mc texto"),
            ["ESC-20260811-12345678-MC"],
        )

    def test_extrair_codigos_rastreio_nao_confunde_com_codigo_de_cotacao(self):
        self.assertEqual(email_tracking.extrair_codigos_rastreio("#123456 - Cotacao"), [])

    def test_extrair_codigos_rastreio_sem_codigo_devolve_lista_vazia(self):
        self.assertEqual(email_tracking.extrair_codigos_rastreio("Assunto qualquer"), [])
        self.assertEqual(email_tracking.extrair_codigos_rastreio(""), [])

    def test_decompor_codigo_rastreio_devolve_inep_e_nivel(self):
        self.assertEqual(
            email_tracking.decompor_codigo_rastreio("ESC-20260811-12345678-RE"),
            ("12345678", email_tracking.NIVEL_RE),
        )

    def test_decompor_codigo_rastreio_invalido_devolve_none(self):
        self.assertIsNone(email_tracking.decompor_codigo_rastreio("#123456"))
        self.assertIsNone(email_tracking.decompor_codigo_rastreio("ESC-2026-12345678-RE"))
