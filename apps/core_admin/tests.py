from io import BytesIO
from unittest.mock import Mock, patch

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.core_admin.views import (
    _ler_dataframe_upload,
    cadastrar_clientes_ixc,
    download_template_edicao_atendimento_ixc,
    download_template_edicao_login_ixc,
    download_template_cadastro_cliente_ixc,
    desativar_atendimentos_ixc,
    editar_atendimentos_ixc,
    editar_logins_ixc,
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
    @patch("apps.core_admin.views._buscar_ultima_edicao_atendimento_ixc")
    @patch("apps.core_admin.views._buscar_ultima_edicao_login_ixc")
    @patch("apps.core_admin.views._buscar_ultima_desativacao")
    @patch("apps.core_admin.views._buscar_ultimo_cadastro_cliente_ixc")
    @patch("apps.core_admin.views.buscar_ultima_importacao")
    @patch("apps.core_admin.views.buscar_importacao_em_andamento")
    def test_import_prospects_renderiza_central_automacoes(
        self,
        mock_andamento,
        mock_ultima,
        mock_ultimo_cadastro_cliente_ixc,
        mock_ultima_desativacao,
        mock_ultima_edicao_login_ixc,
        mock_ultima_edicao_atendimento_ixc,
        mock_render,
    ):
        mock_andamento.return_value = None
        mock_ultima.return_value = None
        mock_ultimo_cadastro_cliente_ixc.return_value = None
        mock_ultima_desativacao.return_value = None
        mock_ultima_edicao_login_ixc.return_value = None
        mock_ultima_edicao_atendimento_ixc.return_value = None
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

    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    def test_download_template_cadastro_cliente_ixc_retorna_planilha(self, mock_auditoria):
        request = self.factory.get("/administracao/clientes/cadastro-ixc/modelo/")
        request.user = self.user

        response = download_template_cadastro_cliente_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Modelo_Cadastro_Clientes_IXC.xlsx",
            response["Content-Disposition"],
        )
        planilhas = pd.read_excel(BytesIO(response.content), sheet_name=None)
        modelo = planilhas["Modelo_Cadastro_Cliente_IXC"]
        ajuda = planilhas["Instrucoes_Ajuda"]
        self.assertIn("Tipo_Cliente_Fiscal", ajuda["Campo"].tolist())
        self.assertIn("Tipo_Assinante_ID", ajuda["Campo"].tolist())
        self.assertIn("Tipo_Cliente_Fiscal", "".join(ajuda["Campo"].tolist()))
        self.assertIn("Razao_Social*", modelo.columns)
        self.assertIn("CNPJ_CPF*", modelo.columns)
        self.assertIn("Confirmar_Cadastro*", modelo.columns)
        self.assertIn("Tipo_Cliente_Fiscal", modelo.columns)
        self.assertNotIn("Classificacao_ISS", modelo.columns)
        linha_tipo_assinante = ajuda.loc[ajuda["Campo"] == "Tipo_Assinante_ID"].iloc[0]
        self.assertIn("Residencial/Pessoa Fisica", linha_tipo_assinante["Regras / Exemplo"])
        mock_auditoria.assert_called_once()

    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    def test_download_template_edicao_login_ixc_retorna_planilha(self, mock_auditoria):
        request = self.factory.get("/administracao/logins/edicao-ixc/modelo/")
        request.user = self.user

        response = download_template_edicao_login_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Modelo_Edicao_Logins_IXC.xlsx",
            response["Content-Disposition"],
        )
        planilhas = pd.read_excel(BytesIO(response.content), sheet_name=None)
        modelo = planilhas["Modelo_Edicao_Login_IXC"]
        ajuda = planilhas["Instrucoes_Ajuda"]
        self.assertIn("Login_ID*", modelo.columns)
        self.assertIn("Confirmar_Alteracao*", modelo.columns)
        self.assertIn("Plano_ID", ajuda["Campo"].tolist())
        self.assertIn("Login_Login", ajuda["Campo"].tolist())
        mock_auditoria.assert_called_once()

    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    def test_download_template_edicao_atendimento_ixc_retorna_planilha(self, mock_auditoria):
        request = self.factory.get("/administracao/atendimentos/edicao-ixc/modelo/")
        request.user = self.user

        response = download_template_edicao_atendimento_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Modelo_Edicao_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        planilhas = pd.read_excel(BytesIO(response.content), sheet_name=None)
        modelo = planilhas["Modelo_Edicao_Atendimento_IXC"]
        ajuda = planilhas["Instrucoes_Ajuda"]
        self.assertIn("Atendimento_ID*", modelo.columns)
        self.assertIn("Confirmar_Alteracao*", modelo.columns)
        self.assertIn("Assunto_ID", ajuda["Campo"].tolist())
        self.assertIn("Descricao", ajuda["Campo"].tolist())
        mock_auditoria.assert_called_once()

    def test_ler_dataframe_upload_remove_asterisco_dos_campos_obrigatorios(self):
        conteudo = BytesIO()
        pd.DataFrame(
            [{"Razao_Social*": "CLIENTE TESTE", "CNPJ_CPF*": "12345678000199", "Confirmar_Cadastro*": "SIM"}]
        ).to_excel(conteudo, index=False)
        arquivo = SimpleUploadedFile(
            "cadastro_clientes.xlsx",
            conteudo.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        df = _ler_dataframe_upload(arquivo)

        self.assertListEqual(
            list(df.columns),
            ["Razao_Social", "CNPJ_CPF", "Confirmar_Cadastro"],
        )

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    @patch("apps.core_admin.views.executar_edicao_atendimento_ixc")
    def test_editar_atendimentos_ixc_processa_planilha_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "Atendimento atualizado com sucesso.",
            "6502",
            "Assunto_ID, Descricao",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Atendimento_ID": 6502, "Assunto_ID": 133, "Confirmar_Alteracao": "SIM"}]
        )

        arquivo = SimpleUploadedFile(
            "edicao_atendimentos.csv",
            b"Atendimento_ID,Assunto_ID,Confirmar_Alteracao\n6502,133,SIM\n",
            content_type="text/csv",
        )
        request = self.factory.post(
            "/administracao/atendimentos/edicao-ixc/",
            {"arquivo_edicao_atendimento_ixc": arquivo},
        )
        request.user = self.user

        response = editar_atendimentos_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Edicao_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()
        self.assertEqual(mock_auditoria.call_count, 2)

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    @patch("apps.core_admin.views.executar_edicao_login_ixc")
    def test_editar_logins_ixc_processa_planilha_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "Login atualizado com sucesso.",
            "4441",
            "Plano_ID, End_CEP",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Login_ID": 4441, "Plano_ID": 13, "Confirmar_Alteracao": "SIM"}]
        )

        arquivo = SimpleUploadedFile(
            "edicao_logins.csv",
            b"Login_ID,Plano_ID,Confirmar_Alteracao\n4441,13,SIM\n",
            content_type="text/csv",
        )
        request = self.factory.post(
            "/administracao/logins/edicao-ixc/",
            {"arquivo_edicao_login_ixc": arquivo},
        )
        request.user = self.user

        response = editar_logins_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Edicao_Logins_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()
        self.assertEqual(mock_auditoria.call_count, 2)

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

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    @patch("apps.core_admin.views.executar_cadastro_cliente_ixc")
    def test_cadastrar_clientes_ixc_processa_planilha_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "Cliente cadastrado com sucesso.",
            "9988",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Razao_Social": "CLIENTE TESTE", "CNPJ_CPF": "12345678000199", "Confirmar_Cadastro": "SIM"}]
        )

        arquivo = SimpleUploadedFile(
            "cadastro_clientes.csv",
            b"Razao_Social,CNPJ_CPF,Confirmar_Cadastro\nCLIENTE TESTE,12345678000199,SIM\n",
            content_type="text/csv",
        )
        request = self.factory.post(
            "/administracao/clientes/cadastro-ixc/",
            {"arquivo_cadastro_cliente_ixc": arquivo},
        )
        request.user = self.user

        response = cadastrar_clientes_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Cadastro_Clientes_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()
        self.assertEqual(mock_auditoria.call_count, 2)
