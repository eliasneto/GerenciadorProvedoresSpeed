from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, SimpleTestCase

from apps.auditoria.admin import (
    CadastroClienteIXCAuditoriaAdmin,
    DesativacaoAtendimentoIXCAuditoriaAdmin,
    EdicaoAtendimentoIXCAuditoriaAdmin,
    EdicaoLoginIXCAuditoriaAdmin,
    IntegrationAuditAuditoriaAdmin,
)
from apps.auditoria.models import (
    CadastroClienteIXCAuditoria,
    CotacaoStatusAuditoria,
    DesativacaoAtendimentoIXCAuditoria,
    EdicaoAtendimentoIXCAuditoria,
    EdicaoLoginIXCAuditoria,
    IntegrationAuditAuditoria,
    RestoreBackupAuditoria,
)
from apps.core.models import CotacaoStatusAuditoria as CotacaoStatusAuditoriaCore
from apps.core.models import RestoreBackupAuditoria as RestoreBackupAuditoriaCore


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

    @patch.object(admin.ModelAdmin, "get_queryset")
    def test_admin_dedicado_filtra_apenas_logs_de_edicao_login_ixc(self, mock_get_queryset):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = EdicaoLoginIXCAuditoriaAdmin(EdicaoLoginIXCAuditoria, AdminSite())
        queryset_base = Mock()
        queryset_filtrado = Mock()
        queryset_base.filter.return_value = queryset_filtrado
        mock_get_queryset.return_value = queryset_base

        queryset = admin_obj.get_queryset(request)

        mock_get_queryset.assert_called_once_with(request)
        queryset_base.filter.assert_called_once_with(integration="edicao_login_ixc")
        self.assertIs(queryset, queryset_filtrado)
        self.assertIn("exportacoes_disponiveis", admin_obj.get_list_display(request))
        self.assertFalse(admin_obj.has_add_permission(request))

    def test_admin_de_desativacao_ixc_nao_expoe_mais_disparo_manual_duplicado(self):
        """PO-036: o disparo manual (upload + processamento) foi centralizado em
        core_admin. Este admin (auditoria) so pode manter a listagem/exportacao
        do historico e o download do modelo em branco."""
        admin_obj = DesativacaoAtendimentoIXCAuditoriaAdmin(DesativacaoAtendimentoIXCAuditoria, AdminSite())

        self.assertFalse(hasattr(admin_obj, "processar_planilha_desativacao"))
        self.assertTrue(hasattr(admin_obj, "baixar_modelo_desativacao"))

        nomes_urls = {pattern.name for pattern in admin_obj.get_urls() if getattr(pattern, "name", None)}
        self.assertNotIn(
            "auditoria_desativacaoatendimentoixcauditoria_processar_planilha",
            nomes_urls,
        )
        self.assertIn(
            "auditoria_desativacaoatendimentoixcauditoria_baixar_modelo",
            nomes_urls,
        )

        with patch.object(admin.ModelAdmin, "changelist_view") as mock_super_changelist:
            request = self.factory.get("/")
            request.user = self.user
            admin_obj.changelist_view(request)

        extra_context = mock_super_changelist.call_args.kwargs["extra_context"]
        self.assertNotIn("processar_planilha_url", extra_context)
        self.assertNotIn("pode_processar_desativacao", extra_context)
        self.assertIn("download_modelo_url", extra_context)

    def test_restorebackupauditoria_e_cotacaostatusauditoria_sao_proxy_de_core(self):
        """PO-036: os dados e a regra moraram em apps.core; auditoria mantem
        apenas um proxy com o mesmo nome para preservar a secao do Admin."""
        self.assertTrue(RestoreBackupAuditoria._meta.proxy)
        self.assertIs(RestoreBackupAuditoria._meta.concrete_model, RestoreBackupAuditoriaCore)
        self.assertEqual(RestoreBackupAuditoria._meta.db_table, RestoreBackupAuditoriaCore._meta.db_table)

        self.assertTrue(CotacaoStatusAuditoria._meta.proxy)
        self.assertIs(CotacaoStatusAuditoria._meta.concrete_model, CotacaoStatusAuditoriaCore)
        self.assertEqual(CotacaoStatusAuditoria._meta.db_table, CotacaoStatusAuditoriaCore._meta.db_table)

    @patch.object(admin.ModelAdmin, "get_queryset")
    def test_admin_dedicado_filtra_apenas_logs_de_edicao_atendimento_ixc(self, mock_get_queryset):
        request = self.factory.get("/")
        request.user = self.user
        admin_obj = EdicaoAtendimentoIXCAuditoriaAdmin(EdicaoAtendimentoIXCAuditoria, AdminSite())
        queryset_base = Mock()
        queryset_filtrado = Mock()
        queryset_base.filter.return_value = queryset_filtrado
        mock_get_queryset.return_value = queryset_base

        queryset = admin_obj.get_queryset(request)

        mock_get_queryset.assert_called_once_with(request)
        queryset_base.filter.assert_called_once_with(integration="edicao_atendimento_ixc")
        self.assertIs(queryset, queryset_filtrado)
        self.assertIn("exportacoes_disponiveis", admin_obj.get_list_display(request))
        self.assertFalse(admin_obj.has_add_permission(request))
