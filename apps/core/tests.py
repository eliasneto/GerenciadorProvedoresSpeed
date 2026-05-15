from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from core.admin import IntegrationAuditAdmin
from core.admin_integration_exports import build_integration_audit_export
from core.models import IntegrationAudit, IntegrationAuditItem


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
