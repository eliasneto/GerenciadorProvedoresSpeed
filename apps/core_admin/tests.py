from unittest.mock import Mock, patch

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.core_admin.views import (
    desativar_atendimentos_ixc,
    download_template_desativacao_atendimento,
    import_prospects,
)


class CoreAdminViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.is_superuser = True
        self.user.groups.filter.return_value.exists.return_value = False

    @patch("apps.core_admin.views.render")
    @patch("apps.core_admin.views._buscar_ultima_desativacao")
    @patch("apps.core_admin.views.buscar_ultima_importacao")
    @patch("apps.core_admin.views.buscar_importacao_em_andamento")
    def test_import_prospects_renderiza_central_automacoes(
        self,
        mock_andamento,
        mock_ultima,
        mock_ultima_desativacao,
        mock_render,
    ):
        mock_andamento.return_value = None
        mock_ultima.return_value = None
        mock_ultima_desativacao.return_value = None
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/administracao/importar/")
        request.user = self.user

        response = import_prospects(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_render.call_args.args[1], "core_admin/automacoes.html")

    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    def test_download_template_desativacao_atendimento_retorna_planilha(self, mock_auditoria):
        request = self.factory.get("/administracao/atendimentos/desativacao/modelo/")
        request.user = self.user

        response = download_template_desativacao_atendimento(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Modelo_Desativacao_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_auditoria.assert_called_once()

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    @patch("apps.core_admin.views.executar_desativacao_atendimento")
    def test_desativar_atendimentos_ixc_processa_planilha_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "Atendimento 5313 finalizado com sucesso.",
            "5313",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Atendimento_ID": 5313, "Confirmar_Desativacao": "SIM"}]
        )

        arquivo = SimpleUploadedFile(
            "desativacao.csv",
            b"Atendimento_ID,Confirmar_Desativacao\n5313,SIM\n",
            content_type="text/csv",
        )
        request = self.factory.post(
            "/administracao/atendimentos/desativacao/",
            {"arquivo_desativacao_atendimento": arquivo},
        )
        request.user = self.user

        response = desativar_atendimentos_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Desativacao_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()
        self.assertEqual(mock_auditoria.call_count, 2)
