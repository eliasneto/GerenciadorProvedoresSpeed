from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
from django.http import HttpResponse
from django.test import SimpleTestCase

from core.admin_integration_exports import build_integration_audit_export, IntegrationAuditExportAdminMixin


class IntegrationAuditExportUnitTests(SimpleTestCase):
    def _build_audit(self):
        item = SimpleNamespace(
            linha_numero=2,
            mensagem="Cliente processado",
            criado_em=None,
            dados_json={
                "Razao_Social": "CLIENTE TESTE",
                "Contato": {"Nome": "Maria", "Email": "maria@teste.com"},
                "Tags": ["VIP", "B2B"],
            },
            get_status_display=lambda: "Sucesso",
        )
        audit = SimpleNamespace(
            pk=13,
            arquivo_nome="clientes.xlsx",
            usuario=SimpleNamespace(username="elias.neto"),
            total_registros=1,
            total_sucessos=1,
            total_erros=0,
            criado_em=None,
            detalhes_json={"colunas": ["Razao_Social", "Contato_Nome"], "origem": "planilha"},
            items=Mock(),
            get_integration_display=lambda: "Cadastro Cliente IXC",
            get_action_display=lambda: "Execucao Integracao",
        )
        audit.items.order_by.return_value = [item]
        return audit

    def test_build_export_expande_itens_e_detalhes_em_colunas(self):
        resumo, itens = build_integration_audit_export(self._build_audit())

        self.assertEqual(itens[0]["Razao_Social"], "CLIENTE TESTE")
        self.assertEqual(itens[0]["Contato_Nome"], "Maria")
        self.assertEqual(itens[0]["Contato_Email"], "maria@teste.com")
        self.assertEqual(itens[0]["Tags_1"], "VIP")
        self.assertEqual(itens[0]["Tags_2"], "B2B")
        self.assertNotIn("Dados_JSON_Bruto", itens[0])
        self.assertEqual(resumo[0]["Detalhe_origem"], "planilha")
        self.assertEqual(resumo[0]["Colunas_Auditadas"], "Razao_Social, Contato_Nome")

    def test_export_excel_coloca_itens_como_primeira_aba(self):
        resumo, itens = build_integration_audit_export(self._build_audit())
        mixin = IntegrationAuditExportAdminMixin()

        response = mixin._exportar_excel("log_integracao_13", resumo, itens)

        self.assertIsInstance(response, HttpResponse)
        planilhas = pd.read_excel(BytesIO(response.content), sheet_name=None)
        self.assertEqual(list(planilhas.keys())[0], "Itens")
        self.assertIn("Contato_Nome", planilhas["Itens"].columns)
        self.assertIn("Detalhe_origem", planilhas["Resumo"].columns)
        self.assertIn("Colunas_Auditadas", planilhas["Resumo"].columns)
        self.assertNotIn("Dados_JSON_Bruto", planilhas["Itens"].columns)
