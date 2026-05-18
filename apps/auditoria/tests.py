from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from auditoria.admin import CadastroClienteIXCAuditoriaAdmin, IntegrationAuditAuditoriaAdmin
from auditoria.models import CadastroClienteIXCAuditoria, IntegrationAuditAuditoria


class AuditoriaAdminTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.is_staff = True
        self.user.is_superuser = True

    def test_admin_generico_de_logs_exibe_coluna_de_exportacao(self):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = IntegrationAuditAuditoriaAdmin(IntegrationAuditAuditoria, AdminSite())

        self.assertIn("exportacoes_disponiveis", admin_obj.get_list_display(request))
        self.assertEqual(
            admin_obj.change_list_template,
            "admin/integration_audit_change_list.html",
        )
        self.assertFalse(admin_obj.has_add_permission(request))

    @patch.object(admin.ModelAdmin, "get_queryset")
    def test_admin_dedicado_filtra_apenas_logs_de_cadastro_cliente_ixc(self, mock_get_queryset):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = CadastroClienteIXCAuditoriaAdmin(CadastroClienteIXCAuditoria, AdminSite())
        queryset_base = Mock()
        queryset_filtrado = Mock()
        queryset_base.filter.return_value = queryset_filtrado
        mock_get_queryset.return_value = queryset_base

        queryset = admin_obj.get_queryset(request)

        mock_get_queryset.assert_called_once_with(request)
        queryset_base.filter.assert_called_once_with(integration="cadastro_cliente_ixc")
        self.assertIs(queryset, queryset_filtrado)
        self.assertIn("exportacoes_disponiveis", admin_obj.get_list_display(request))
        self.assertFalse(admin_obj.has_add_permission(request))
