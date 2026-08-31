import csv
import tempfile
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import openpyxl
import pandas as pd
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core_admin.admin import AcessoBancoDadosAdmin
from apps.core.automacoes_registry import (
    automacoes_do_menu,
    usuario_pode_acessar_automacao,
)
from apps.core.models import AutomacaoMenu, IntegrationAudit, RegistroHistorico, RestoreBackupAuditoria
from apps.core_admin.models import AcessoBancoDados
from apps.core_admin import services as core_admin_services
from apps.escolas.models import Campo, CampoValor, Escola, MapaCalor, Processo, RedeExterna, RedeInterna, Setor, SetorEscopo, SetorStatus
from apps.partners.models import Partner
from apps.core_admin.services import _ler_dataframe_upload
from apps.core_admin.views import (
    download_template_edicao_atendimento_ixc,
    download_template_edicao_login_ixc,
    download_template_resolucao_os_atendimento,
    desativar_atendimentos_ixc,
    editar_atendimentos_ixc,
    editar_logins_ixc,
    resolver_os_atendimento_ixc,
    download_template_desativacao_atendimento,
    import_prospects,
)
from apps.backoffice.views import (
    atendimento_import,
    cadastrar_clientes_ixc,
    cotacao_import,
    download_modelo_atendimento,
    download_template_cadastro_cliente_ixc,
)
from django.core.exceptions import PermissionDenied


def _construir_upload_excel(dados, nome_arquivo="planilha.xlsx"):
    df = pd.DataFrame(dados)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return SimpleUploadedFile(
        nome_arquivo,
        buffer.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class CoreAdminViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.is_superuser = True
        self.user.groups.filter.return_value.exists.return_value = False

    @patch("apps.core_admin.views.render")
    @patch("apps.core_admin.services._buscar_ultima_resolucao_os_atendimento")
    @patch("apps.core_admin.services._buscar_ultima_edicao_atendimento_ixc")
    @patch("apps.core_admin.services._buscar_ultima_edicao_login_ixc")
    @patch("apps.core_admin.services._buscar_ultima_desativacao")
    @patch("apps.core_admin.services._buscar_ultimo_cadastro_cliente_ixc")
    @patch("apps.core_admin.services.buscar_ultima_importacao")
    @patch("apps.core_admin.services.buscar_importacao_em_andamento")
    def test_import_prospects_renderiza_central_automacoes(
        self,
        mock_andamento,
        mock_ultima,
        mock_ultimo_cadastro_cliente_ixc,
        mock_ultima_desativacao,
        mock_ultima_edicao_login_ixc,
        mock_ultima_edicao_atendimento_ixc,
        mock_ultima_resolucao_os_atendimento,
        mock_render,
    ):
        mock_andamento.return_value = None
        mock_ultima.return_value = None
        mock_ultimo_cadastro_cliente_ixc.return_value = None
        mock_ultima_desativacao.return_value = None
        mock_ultima_edicao_login_ixc.return_value = None
        mock_ultima_edicao_atendimento_ixc.return_value = None
        mock_ultima_resolucao_os_atendimento.return_value = None
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/administracao/importar/")
        request.user = self.user

        response = import_prospects(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_render.call_args.args[1], "core_admin/automacoes.html")

    @patch("apps.core_admin.services.registrar_auditoria_integracao")
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

    @patch("apps.backoffice.views.registrar_auditoria_integracao")
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
        self.assertIn("Tipo_Cliente_Fiscal", "".join(str(v) for v in ajuda["Campo"].tolist() if pd.notna(v)))
        self.assertIn("Razao_Social*", modelo.columns)
        self.assertIn("CNPJ_CPF*", modelo.columns)
        self.assertIn("Confirmar_Cadastro*", modelo.columns)
        self.assertIn("Tipo_Cliente_Fiscal", modelo.columns)
        self.assertNotIn("Classificacao_ISS", modelo.columns)
        linha_tipo_assinante = ajuda.loc[ajuda["Campo"] == "Tipo_Assinante_ID"].iloc[0]
        self.assertIn("Residencial/Pessoa Fisica", linha_tipo_assinante["Regras / Exemplo"])
        mock_auditoria.assert_called_once()

    @patch("apps.core_admin.services.registrar_auditoria_integracao")
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

    @patch("apps.core_admin.services.registrar_auditoria_integracao")
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

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    @patch("apps.core_admin.services.executar_edicao_atendimento_ixc")
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

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    @patch("apps.core_admin.services.executar_edicao_login_ixc")
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

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    @patch("apps.core_admin.services.executar_desativacao_atendimento")
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

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    @patch("apps.core_admin.services.executar_resolucao_os_atendimento_ixc")
    def test_resolver_os_atendimento_ixc_processa_planilha_com_zip_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "Documento anexado e 1 O.S. fechada(s) no atendimento 5313: 6394.",
            "5313",
            "6394",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Atendimento_ID": 5313, "Confirmar_Resolucao": "SIM", "Tem_Anexo": "SIM", "Nome_Anexo": "comunicado.pdf"}]
        )

        planilha = SimpleUploadedFile(
            "resolucao_os.csv",
            b"Atendimento_ID,Confirmar_Resolucao,Tem_Anexo,Nome_Anexo\n5313,SIM,SIM,comunicado.pdf\n",
            content_type="text/csv",
        )
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_arquivo:
            zip_arquivo.writestr("comunicado.pdf", b"conteudo do documento")
        zip_buffer.seek(0)
        zip_anexos = SimpleUploadedFile(
            "anexos.zip",
            zip_buffer.getvalue(),
            content_type="application/zip",
        )
        request = self.factory.post(
            "/administracao/atendimentos/resolucao-os/",
            {
                "arquivo_planilha_resolucao_os": planilha,
                "arquivo_zip_resolucao_os": zip_anexos,
            },
        )
        request.user = self.user

        response = resolver_os_atendimento_ixc(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Resolucao_OS_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()
        zip_recebido = mock_executar.call_args.args[1]
        self.assertIn("comunicado.pdf", zip_recebido.namelist())
        self.assertEqual(mock_auditoria.call_count, 2)

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    @patch("apps.core_admin.services.executar_resolucao_os_atendimento_ixc")
    def test_resolver_os_atendimento_ixc_sem_zip_e_permitido(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (
            True,
            "2 O.S. fechada(s) no atendimento 5313: 6394, 6395.",
            "5313",
            "6394, 6395",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Atendimento_ID": 5313, "Confirmar_Resolucao": "SIM", "Tem_Anexo": "NAO"}]
        )

        planilha = SimpleUploadedFile(
            "resolucao_os.csv",
            b"Atendimento_ID,Confirmar_Resolucao,Tem_Anexo\n5313,SIM,NAO\n",
            content_type="text/csv",
        )
        request = self.factory.post(
            "/administracao/atendimentos/resolucao-os/",
            {"arquivo_planilha_resolucao_os": planilha},
        )
        request.user = self.user

        response = resolver_os_atendimento_ixc(request)

        self.assertEqual(response.status_code, 200)
        mock_executar.assert_called_once()
        self.assertIsNone(mock_executar.call_args.args[1])

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.executar_resolucao_os_atendimento_ixc")
    def test_resolver_os_atendimento_ixc_zip_invalido_nao_processa(
        self,
        mock_executar,
        mock_ler_dataframe,
    ):
        planilha = SimpleUploadedFile(
            "resolucao_os.csv",
            b"Atendimento_ID,Confirmar_Resolucao,Tem_Anexo\n5313,SIM,SIM\n",
            content_type="text/csv",
        )
        zip_invalido = SimpleUploadedFile(
            "anexos.zip",
            b"nao e um zip valido",
            content_type="application/zip",
        )
        request = self.factory.post(
            "/administracao/atendimentos/resolucao-os/",
            {
                "arquivo_planilha_resolucao_os": planilha,
                "arquivo_zip_resolucao_os": zip_invalido,
            },
        )
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = resolver_os_atendimento_ixc(request)

        self.assertEqual(response.status_code, 302)
        mock_executar.assert_not_called()

    @patch("apps.backoffice.services.verificar_duplicidade_ixc")
    @patch("apps.backoffice.services.ler_dataframe_upload")
    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_cadastro_cliente_ixc")
    def test_cadastrar_clientes_ixc_processa_planilha_e_retorna_relatorio(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
        mock_verificar_duplicidade,
    ):
        mock_executar.return_value = (
            True,
            "Cliente cadastrado com sucesso.",
            "9988",
        )
        mock_verificar_duplicidade.return_value = None
        mock_ler_dataframe.return_value = pd.DataFrame(
            [
                {
                    "Razao_Social": "CLIENTE TESTE",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA A",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                }
            ]
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

    @patch("apps.backoffice.services.verificar_duplicidade_ixc")
    @patch("apps.backoffice.services.ler_dataframe_upload")
    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_cadastro_cliente_ixc")
    def test_cadastrar_clientes_ixc_reprova_planilha_com_cnpj_duplicado_interno(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
        mock_verificar_duplicidade,
    ):
        mock_verificar_duplicidade.return_value = None
        mock_ler_dataframe.return_value = pd.DataFrame(
            [
                {
                    "Razao_Social": "ESCOLA A",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA A",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                },
                {
                    "Razao_Social": "ESCOLA B",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA B",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                },
            ]
        )

        arquivo = SimpleUploadedFile(
            "cadastro_clientes.csv",
            b"Razao_Social,CNPJ_CPF,Confirmar_Cadastro\nESCOLA A,11222333000181,SIM\nESCOLA B,11222333000181,SIM\n",
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
            "attachment; filename=Validacao_Cadastro_Clientes_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_not_called()

    @patch("apps.backoffice.services.verificar_duplicidade_ixc")
    @patch("apps.backoffice.services.ler_dataframe_upload")
    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_cadastro_cliente_ixc")
    def test_cadastrar_clientes_ixc_reprova_planilha_com_cnpj_ja_existente_no_ixc(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
        mock_verificar_duplicidade,
    ):
        mock_verificar_duplicidade.return_value = (
            "Cliente ja existente no IXC (ID 4455). Correspondencia encontrada pelo campo "
            "CNPJ/CPF ('11.222.333/0001-81'). Nenhuma alteracao feita para ESCOLA A.",
            "4455",
        )
        mock_ler_dataframe.return_value = pd.DataFrame(
            [
                {
                    "Razao_Social": "ESCOLA A",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA A",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                },
            ]
        )

        arquivo = SimpleUploadedFile(
            "cadastro_clientes.csv",
            b"Razao_Social,CNPJ_CPF,Confirmar_Cadastro\nESCOLA A,11222333000181,SIM\n",
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
            "attachment; filename=Validacao_Cadastro_Clientes_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_not_called()

    @patch("apps.backoffice.services.verificar_duplicidade_ixc")
    @patch("apps.backoffice.services.ler_dataframe_upload")
    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_cadastro_cliente_ixc")
    def test_cadastrar_clientes_ixc_permite_cnpj_duplicado_com_flag(
        self,
        mock_executar,
        mock_auditoria,
        mock_ler_dataframe,
        mock_verificar_duplicidade,
    ):
        mock_executar.return_value = (True, "Cliente cadastrado com sucesso.", "9988")
        mock_verificar_duplicidade.return_value = None
        mock_ler_dataframe.return_value = pd.DataFrame(
            [
                {
                    "Razao_Social": "ESCOLA A",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA A",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                    "Permitir_Duplicidade": "SIM",
                },
                {
                    "Razao_Social": "ESCOLA B",
                    "CNPJ_CPF": "11222333000181",
                    "CEP": "60000-000",
                    "Endereco": "RUA B",
                    "Bairro": "CENTRO",
                    "Cidade_ID_IXC": "887",
                    "Email": "teste@exemplo.com",
                    "Telefone": "(85) 99999-9999",
                    "Tipo_Cliente_ID": "8",
                    "Filial_ID": "1",
                    "Confirmar_Cadastro": "SIM",
                    "Permitir_Duplicidade": "SIM",
                },
            ]
        )

        arquivo = SimpleUploadedFile(
            "cadastro_clientes.csv",
            b"Razao_Social,CNPJ_CPF,Confirmar_Cadastro,Permitir_Duplicidade\n"
            b"ESCOLA A,11222333000181,SIM,SIM\nESCOLA B,11222333000181,SIM,SIM\n",
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
        self.assertEqual(mock_executar.call_count, 2)

    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_cadastro_ixc")
    def test_cotacao_import_processa_planilha_com_sucesso_e_erro(self, mock_executar, mock_auditoria):
        mock_executar.side_effect = [
            (True, "Login criado com sucesso!", "111"),
            (False, "IXC Negou: login duplicado", None),
        ]
        arquivo = _construir_upload_excel([
            {"Login_Login": "cliente1"},
            {"Login_Login": "cliente2"},
        ])
        request = self.factory.post(
            "/backoffice/cotacao/importar/",
            {"arquivo_cotacao": arquivo},
        )
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = cotacao_import(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_Importacao_IXC.xlsx",
            response["Content-Disposition"],
        )
        self.assertEqual(mock_executar.call_count, 2)

    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_abertura_atendimento")
    def test_atendimento_import_processa_planilha_com_sucesso(self, mock_executar, mock_auditoria):
        mock_executar.return_value = (True, "Atendimento aberto com sucesso! ID: 777")
        arquivo = _construir_upload_excel([
            {
                "Cliente_ID": "123",
                "Tipo_Processo": "Avulso",
                "Workflow_ID": "",
            }
        ])
        request = self.factory.post(
            "/backoffice/atendimento/importar/",
            {"arquivo_atendimento": arquivo},
        )
        request.user = self.user

        response = atendimento_import(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_OS_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()

    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_abertura_atendimento")
    def test_atendimento_import_planilha_recusada_na_validacao_previa(self, mock_executar, mock_auditoria):
        arquivo = _construir_upload_excel([
            {
                "Cliente_ID": "123",
                "Tipo_Processo": "Avulso",
                "Workflow_ID": "18",
            }
        ])
        request = self.factory.post(
            "/backoffice/atendimento/importar/",
            {"arquivo_atendimento": arquivo},
        )
        request.user = self.user

        response = atendimento_import(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_OS_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_not_called()

    @patch("apps.backoffice.views.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.registrar_auditoria_integracao")
    @patch("apps.backoffice.services.executar_abertura_atendimento")
    def test_atendimento_import_processa_planilha_gerada_pelo_modelo_oficial(
        self, mock_executar, mock_auditoria, mock_auditoria_view
    ):
        """Regressao: o modelo oficial (download_modelo_atendimento) grava os
        cabecalhos obrigatorios com sufixo "*" (ex.: "Cliente_ID*"). Se a
        planilha reimportada nao normalizar esse sufixo, todo registro e
        silenciosamente ignorado: a planilha "volta" sem erro, mas nenhum
        atendimento e enviado ao IXC."""
        mock_executar.return_value = (True, "Atendimento aberto com sucesso! ID: 999")

        request_modelo = self.factory.post("/backoffice/atendimento/modelo/")
        request_modelo.user = self.user
        modelo_response = download_modelo_atendimento(request_modelo)

        workbook = openpyxl.load_workbook(BytesIO(modelo_response.content))
        planilha = workbook["Modelo_OS"]
        cabecalhos = [celula.value for celula in planilha[1]]
        # Confirma o formato real do modelo antes de validar o fluxo de importacao.
        self.assertIn("Cliente_ID*", cabecalhos)

        valores = {
            "Cliente_ID*": "123",
            "Login_ID*": "456",
            "Contrato_ID*": "789",
            "Filial_ID*": "1",
            "Assunto_ID*": "2",
            "Departamento_ID*": "3",
            "Tipo_Processo*": "Avulso",
            "Workflow_ID": "",
            "Assunto_Descricao*": "Assunto teste",
            "Descricao*": "Descricao teste",
        }
        planilha.append([valores.get(cabecalho, "") for cabecalho in cabecalhos])

        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        arquivo = SimpleUploadedFile(
            "Atendimento.xlsx",
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        request = self.factory.post(
            "/backoffice/atendimento/importar/",
            {"arquivo_atendimento": arquivo},
        )
        request.user = self.user

        response = atendimento_import(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Relatorio_OS_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_executar.assert_called_once()


class ImportProspectsViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Hub de automacoes: cobre os ramos
    de POST que a suite anterior (mock direto na view, so a renderizacao
    GET) nao testava."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-import", password="senha-forte-123", is_superuser=True,
        )

    @patch("apps.core_admin.services.parar_importacao_em_andamento")
    def test_post_stop_sem_importacao_em_andamento_mostra_aviso(self, mock_parar):
        mock_parar.return_value = (False, "Nao existe importacao em andamento para interromper.")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("import_prospects"), {"action": "stop"})

        self.assertRedirects(response, reverse("import_prospects"))
        mock_parar.assert_called_once()

    @patch("apps.core_admin.services.parar_importacao_em_andamento")
    def test_post_stop_com_importacao_em_andamento(self, mock_parar):
        mock_parar.return_value = (True, "Solicitacao de interrupcao enviada.")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("import_prospects"), {"action": "stop"})

        self.assertRedirects(response, reverse("import_prospects"))

    @patch("apps.core_admin.services.verificar_importacao_bloqueada")
    def test_post_bloqueado_por_importacao_em_andamento_nao_chega_a_validar_form(self, mock_bloqueio):
        mock_bloqueio.return_value = "Ja existe uma importacao em andamento para o arquivo x.xlsx."
        self.client.force_login(self.admin)

        response = self.client.post(reverse("import_prospects"), {})

        self.assertRedirects(response, reverse("import_prospects"))

    @patch("apps.core_admin.services.iniciar_importacao_prospects")
    @patch("apps.core_admin.services.verificar_importacao_bloqueada")
    def test_post_arquivo_valido_inicia_importacao_em_segundo_plano(self, mock_bloqueio, mock_iniciar):
        mock_bloqueio.return_value = None
        mock_iniciar.return_value = (True, "Importacao iniciada em segundo plano.")
        self.client.force_login(self.admin)
        arquivo = _construir_upload_excel([{"RAZAO_SOCIAL": "Empresa Exemplo"}])

        response = self.client.post(reverse("import_prospects"), {"file": arquivo})

        self.assertRedirects(response, reverse("import_prospects"))
        mock_iniciar.assert_called_once()

    @patch("apps.core_admin.services.iniciar_importacao_prospects")
    @patch("apps.core_admin.services.verificar_importacao_bloqueada")
    def test_post_falha_ao_iniciar_renderiza_novamente_com_erro(self, mock_bloqueio, mock_iniciar):
        mock_bloqueio.return_value = None
        mock_iniciar.return_value = (False, "Nao foi possivel iniciar a importacao: falha simulada.")
        self.client.force_login(self.admin)
        arquivo = _construir_upload_excel([{"RAZAO_SOCIAL": "Empresa Exemplo"}])

        response = self.client.post(reverse("import_prospects"), {"file": arquivo})

        self.assertEqual(response.status_code, 200)


class AutomacoesAreaViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Hub de automacoes: sem cobertura
    HTTP antes desta entrega."""

    def setUp(self):
        self.usuario_lastmile = get_user_model().objects.create_user(
            username="user-lastmile", password="senha-forte-123",
        )
        self.usuario_lastmile.groups.add(Group.objects.create(name="LastMile"))
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-automacoes", password="senha-forte-123",
        )

    def test_menu_administrador_nao_e_atendido_por_esta_rota(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("automacoes_area", args=[AutomacaoMenu.MENU_ADMINISTRADOR]))

        self.assertEqual(response.status_code, 404)

    def test_usuario_sem_grupo_do_menu_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("automacoes_area", args=[AutomacaoMenu.MENU_LASTMILE]))

        self.assertEqual(response.status_code, 403)

    def test_usuario_do_grupo_do_menu_acessa(self):
        self.client.force_login(self.usuario_lastmile)
        response = self.client.get(reverse("automacoes_area", args=[AutomacaoMenu.MENU_LASTMILE]))

        self.assertEqual(response.status_code, 200)


class AutomacoesIxcPermissaoViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Automacoes IXC: cobre permissao e
    validacao de arquivo, ramos sem cobertura HTTP antes desta entrega
    (a suite anterior so exercitava o caminho de sucesso via mock)."""

    def setUp(self):
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-ixc-automacao", password="senha-forte-123",
        )

    def test_desativar_atendimentos_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.post(reverse("desativar_atendimentos_ixc"), {})

        self.assertEqual(response.status_code, 403)

    def test_desativar_atendimentos_sem_arquivo_redireciona(self):
        self.client.force_login(self.sem_permissao)
        self.sem_permissao.is_superuser = True
        self.sem_permissao.save(update_fields=["is_superuser"])

        response = self.client.post(reverse("desativar_atendimentos_ixc"), {})

        self.assertRedirects(response, reverse("import_prospects"))

    def test_editar_atendimentos_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.post(reverse("editar_atendimentos_ixc"), {})

        self.assertEqual(response.status_code, 403)

    def test_editar_atendimentos_sem_arquivo_redireciona(self):
        self.sem_permissao.is_superuser = True
        self.sem_permissao.save(update_fields=["is_superuser"])
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("editar_atendimentos_ixc"), {})

        self.assertRedirects(response, reverse("import_prospects"))

    def test_editar_logins_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.post(reverse("editar_logins_ixc"), {})

        self.assertEqual(response.status_code, 403)

    def test_editar_logins_sem_arquivo_redireciona(self):
        self.sem_permissao.is_superuser = True
        self.sem_permissao.save(update_fields=["is_superuser"])
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("editar_logins_ixc"), {})

        self.assertRedirects(response, reverse("import_prospects"))

    def test_resolver_os_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.post(reverse("resolver_os_atendimento_ixc"), {})

        self.assertEqual(response.status_code, 403)

    def test_resolver_os_sem_planilha_redireciona(self):
        self.sem_permissao.is_superuser = True
        self.sem_permissao.save(update_fields=["is_superuser"])
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("resolver_os_atendimento_ixc"), {})

        self.assertRedirects(response, reverse("import_prospects"))


class RestoreBackupHelpersTests(SimpleTestCase):
    """Fatia core_admin (PO-011), slice Backup/restore: guardas de
    seguranca contra zip-slip (extracao fora do diretorio de destino)."""

    def test_is_within_directory_aceita_caminho_dentro_do_destino(self):
        with tempfile.TemporaryDirectory() as base_dir:
            self.assertTrue(
                core_admin_services._is_within_directory(base_dir, Path(base_dir) / "arquivo.sql")
            )

    def test_is_within_directory_rejeita_caminho_fora_do_destino(self):
        with tempfile.TemporaryDirectory() as base_dir:
            fora = Path(base_dir).parent / "fora_do_destino.txt"
            self.assertFalse(core_admin_services._is_within_directory(base_dir, fora))

    def test_extract_zip_safely_extrai_arquivo_legitimo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "backup.zip"
            with zipfile.ZipFile(zip_path, "w") as arquivo_zip:
                arquivo_zip.writestr("backup.sql", b"CREATE TABLE x;")

            destino = Path(tmp_dir) / "extract"
            destino.mkdir()
            core_admin_services._extract_zip_safely(zip_path, destino)

            self.assertTrue((destino / "backup.sql").exists())

    def test_extract_zip_safely_rejeita_zip_slip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "malicioso.zip"
            with zipfile.ZipFile(zip_path, "w") as arquivo_zip:
                arquivo_zip.writestr("../../fora_do_destino.txt", b"conteudo malicioso")

            destino = Path(tmp_dir) / "extract"
            destino.mkdir()

            with self.assertRaises(ValueError):
                core_admin_services._extract_zip_safely(zip_path, destino)

            self.assertFalse((Path(tmp_dir) / "fora_do_destino.txt").exists())

    def test_find_first_file_encontra_sql_em_subdiretorio(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            subdir = Path(tmp_dir) / "dump"
            subdir.mkdir()
            (subdir / "backup.sql").write_text("CREATE TABLE x;")

            encontrado = core_admin_services._find_first_file(tmp_dir, ".sql")

            self.assertEqual(encontrado, subdir / "backup.sql")

    def test_find_first_file_retorna_none_quando_nao_encontra(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            self.assertIsNone(core_admin_services._find_first_file(tmp_dir, ".sql"))

    def test_find_media_dir_encontra_pasta_media(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            media_dir = Path(tmp_dir) / "dump" / "media"
            media_dir.mkdir(parents=True)

            self.assertEqual(core_admin_services._find_media_dir(tmp_dir), media_dir)


class RestoreBackupListagemTests(SimpleTestCase):
    """Fatia core_admin (PO-011), slice Backup/restore: listagem e
    resolucao segura de backups ja salvos no servidor."""

    def test_listar_backups_disponiveis_retorna_vazio_sem_diretorio(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.assertEqual(core_admin_services._listar_backups_disponiveis(), [])

    def test_listar_backups_disponiveis_lista_apenas_backups_esperados(self):
        with tempfile.TemporaryDirectory() as media_root:
            backups_dir = Path(media_root) / "backups"
            backups_dir.mkdir()
            (backups_dir / "backup_speed_20260101.zip").write_bytes(b"conteudo")
            (backups_dir / "arquivo_irrelevante.txt").write_bytes(b"x")

            with override_settings(MEDIA_ROOT=media_root):
                backups = core_admin_services._listar_backups_disponiveis()

            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0][0], "backup_speed_20260101.zip")

    def test_resolver_backup_existente_retorna_caminho_valido(self):
        with tempfile.TemporaryDirectory() as media_root:
            backups_dir = Path(media_root) / "backups"
            backups_dir.mkdir()
            arquivo = backups_dir / "backup_speed_20260101.zip"
            arquivo.write_bytes(b"conteudo")

            with override_settings(MEDIA_ROOT=media_root):
                resolvido = core_admin_services._resolver_backup_existente("backup_speed_20260101.zip")

            self.assertEqual(resolvido, arquivo.resolve())

    def test_resolver_backup_existente_rejeita_path_traversal(self):
        with tempfile.TemporaryDirectory() as media_root:
            Path(media_root, "backups").mkdir()

            with override_settings(MEDIA_ROOT=media_root):
                with self.assertRaises(ValueError):
                    core_admin_services._resolver_backup_existente("../../etc/passwd")

    def test_resolver_backup_existente_rejeita_arquivo_inexistente(self):
        with tempfile.TemporaryDirectory() as media_root:
            Path(media_root, "backups").mkdir()

            with override_settings(MEDIA_ROOT=media_root):
                with self.assertRaises(FileNotFoundError):
                    core_admin_services._resolver_backup_existente("nao_existe.zip")

    def test_resolver_backup_existente_rejeita_extensao_diferente_de_zip(self):
        with tempfile.TemporaryDirectory() as media_root:
            backups_dir = Path(media_root) / "backups"
            backups_dir.mkdir()
            (backups_dir / "arquivo.txt").write_bytes(b"conteudo")

            with override_settings(MEDIA_ROOT=media_root):
                with self.assertRaises(ValueError):
                    core_admin_services._resolver_backup_existente("arquivo.txt")


class RestaurarBancoEMidiaTests(SimpleTestCase):
    """Fatia core_admin (PO-011), slice Backup/restore: execucao do
    `mysql` (mockado - nunca roda de fato nos testes) e sincronizacao da
    pasta media."""

    @patch("apps.core_admin.services.subprocess.run")
    def test_restaurar_banco_levanta_erro_quando_mysql_falha(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stderr=b"erro de conexao", stdout=b"")

        with tempfile.TemporaryDirectory() as tmp_dir:
            sql_file = Path(tmp_dir) / "backup.sql"
            sql_file.write_text("CREATE TABLE x;")

            with self.assertRaises(RuntimeError):
                core_admin_services.restaurar_banco_e_midia(sql_file, None)

    @patch("apps.core_admin.services.subprocess.run")
    def test_restaurar_banco_sem_pasta_media_nao_marca_midia_restaurada(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stderr=b"", stdout=b"")

        with tempfile.TemporaryDirectory() as tmp_dir:
            sql_file = Path(tmp_dir) / "backup.sql"
            sql_file.write_text("CREATE TABLE x;")

            media_restaurado = core_admin_services.restaurar_banco_e_midia(sql_file, None)

            self.assertFalse(media_restaurado)

    @patch("apps.core_admin.services.subprocess.run")
    def test_restaurar_banco_sincroniza_pasta_media(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stderr=b"", stdout=b"")

        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as media_root:
            sql_file = Path(tmp_dir) / "backup.sql"
            sql_file.write_text("CREATE TABLE x;")

            media_dir = Path(tmp_dir) / "media"
            media_dir.mkdir()
            (media_dir / "foto.jpg").write_bytes(b"conteudo-da-foto")

            with override_settings(MEDIA_ROOT=media_root):
                media_restaurado = core_admin_services.restaurar_banco_e_midia(sql_file, media_dir)

            self.assertTrue(media_restaurado)
            self.assertTrue((Path(media_root) / "foto.jpg").exists())


def _construir_upload_zip_backup(sql_conteudo=b"CREATE TABLE x;\n", nome_arquivo="backup.zip"):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo_zip:
        arquivo_zip.writestr("backup.sql", sql_conteudo)
    buffer.seek(0)
    return SimpleUploadedFile(nome_arquivo, buffer.read(), content_type="application/zip")


class RestoreBackupViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Backup/restore: sem cobertura
    HTTP antes desta entrega. `services.restaurar_banco_e_midia` e
    mockado em todos os cenarios - nenhum teste executa `mysql` de
    verdade."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-restore", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-restore", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("restore_backup"))

        self.assertEqual(response.status_code, 403)

    def test_get_renderiza_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("restore_backup"))

        self.assertEqual(response.status_code, 200)

    def test_post_sem_confirmar_nao_processa(self):
        self.client.force_login(self.admin)
        arquivo = _construir_upload_zip_backup()

        response = self.client.post(reverse("restore_backup"), {"file": arquivo})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(RestoreBackupAuditoria.objects.count(), 0)

    @patch("apps.core_admin.services.restaurar_banco_e_midia")
    def test_post_zip_sem_sql_mostra_erro_sem_auditar(self, mock_restaurar):
        self.client.force_login(self.admin)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as arquivo_zip:
            arquivo_zip.writestr("nao_e_um_dump.txt", b"conteudo")
        buffer.seek(0)
        arquivo = SimpleUploadedFile("backup.zip", buffer.read(), content_type="application/zip")

        response = self.client.post(
            reverse("restore_backup"), {"file": arquivo, "confirmar": "on"},
        )

        self.assertEqual(response.status_code, 200)
        mock_restaurar.assert_not_called()
        self.assertEqual(RestoreBackupAuditoria.objects.count(), 0)

    @patch("apps.core_admin.services.restaurar_banco_e_midia")
    def test_post_zip_com_sql_vazio_mostra_erro_sem_auditar(self, mock_restaurar):
        self.client.force_login(self.admin)
        arquivo = _construir_upload_zip_backup(sql_conteudo=b"")

        response = self.client.post(
            reverse("restore_backup"), {"file": arquivo, "confirmar": "on"},
        )

        self.assertEqual(response.status_code, 200)
        mock_restaurar.assert_not_called()
        self.assertEqual(RestoreBackupAuditoria.objects.count(), 0)

    def test_post_zip_slip_e_rejeitado_e_auditado_como_falha(self):
        self.client.force_login(self.admin)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as arquivo_zip:
            arquivo_zip.writestr("../../fora_do_destino.txt", b"conteudo malicioso")
        buffer.seek(0)
        arquivo = SimpleUploadedFile("malicioso.zip", buffer.read(), content_type="application/zip")

        response = self.client.post(
            reverse("restore_backup"), {"file": arquivo, "confirmar": "on"},
        )

        self.assertEqual(response.status_code, 200)
        auditoria = RestoreBackupAuditoria.objects.get()
        self.assertFalse(auditoria.sucesso)

    @patch("apps.core_admin.services.restaurar_banco_e_midia")
    def test_post_sucesso_retorna_pagina_de_confirmacao_e_audita(self, mock_restaurar):
        mock_restaurar.return_value = False
        self.client.force_login(self.admin)
        arquivo = _construir_upload_zip_backup()

        response = self.client.post(
            reverse("restore_backup"), {"file": arquivo, "confirmar": "on"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Backup restaurado com sucesso", response.content)
        auditoria = RestoreBackupAuditoria.objects.get()
        self.assertTrue(auditoria.sucesso)
        self.assertEqual(auditoria.origem, "upload")
        self.assertEqual(auditoria.usuario, self.admin)

    @patch("apps.core_admin.services.restaurar_banco_e_midia")
    def test_post_falha_no_restore_e_auditada(self, mock_restaurar):
        mock_restaurar.side_effect = RuntimeError("mysql indisponivel")
        self.client.force_login(self.admin)
        arquivo = _construir_upload_zip_backup()

        response = self.client.post(
            reverse("restore_backup"), {"file": arquivo, "confirmar": "on"},
        )

        self.assertEqual(response.status_code, 200)
        auditoria = RestoreBackupAuditoria.objects.get()
        self.assertFalse(auditoria.sucesso)
        self.assertIn("mysql indisponivel", auditoria.detalhes)


class DownloadTemplateLeadsViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Download de templates: sem
    cobertura HTTP antes desta entrega."""

    def test_download_retorna_planilha(self):
        response = self.client.get(reverse("download_template"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=modelo_importacao_leads.xlsx",
            response["Content-Disposition"],
        )


class DownloadTemplateResolucaoOsViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Download de templates: sem
    cobertura HTTP antes desta entrega."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-resolucao-os", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-resolucao-os", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("download_template_resolucao_os_atendimento"))

        self.assertEqual(response.status_code, 403)

    @patch("apps.core_admin.services.registrar_auditoria_integracao")
    def test_download_retorna_planilha(self, mock_auditoria):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("download_template_resolucao_os_atendimento"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "attachment; filename=Modelo_Resolucao_OS_Atendimentos_IXC.xlsx",
            response["Content-Disposition"],
        )
        mock_auditoria.assert_called_once()


class ProgressoResolucaoOsAtendimentoTests(TestCase):
    """PO-043: visibilidade da linha atual durante a execucao (RN-022)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-progresso-resolucao-os", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-progresso-resolucao-os", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("progresso_resolucao_os_atendimento"), {"execucao_id": "abc"})

        self.assertEqual(response.status_code, 403)

    def test_progresso_de_execucao_inexistente_retorna_nao_encontrado(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("progresso_resolucao_os_atendimento"), {"execucao_id": "nao-existe"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "nao_encontrado"})

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.executar_resolucao_os_atendimento_ixc")
    def test_processar_resolucao_grava_progresso_por_linha(
        self,
        mock_executar,
        mock_ler_dataframe,
    ):
        mock_ler_dataframe.return_value = pd.DataFrame(
            [
                {"Atendimento_ID": 111, "Confirmar_Resolucao": "SIM", "Tem_Anexo": "NAO"},
                {"Atendimento_ID": 222, "Confirmar_Resolucao": "SIM", "Tem_Anexo": "NAO"},
            ]
        )

        execucao_id = "exec-teste-progresso-123"
        progresso_durante_execucao = []

        def _side_effect(linha, zip_arquivos, usuario_sistema=None):
            audit = IntegrationAudit.objects.get(execucao_id=execucao_id, action="importacao_planilha")
            progresso_durante_execucao.append(dict(audit.progresso_atual))
            return True, "ok", str(int(linha.get("Atendimento_ID"))), ""

        mock_executar.side_effect = _side_effect

        planilha = SimpleUploadedFile("teste.csv", b"conteudo", content_type="text/csv")

        core_admin_services.processar_resolucao_os_atendimentos(
            planilha, None, self.admin, execucao_id=execucao_id
        )

        self.assertEqual(len(progresso_durante_execucao), 2)
        self.assertEqual(progresso_durante_execucao[0]["atendimento_id"], "111")
        self.assertEqual(progresso_durante_execucao[0]["linha_atual"], 2)
        self.assertEqual(progresso_durante_execucao[0]["total_linhas"], 2)
        self.assertEqual(progresso_durante_execucao[1]["atendimento_id"], "222")
        self.assertEqual(progresso_durante_execucao[1]["linha_atual"], 3)

        progresso_final = core_admin_services.obter_progresso_resolucao_os_atendimento(execucao_id)
        self.assertEqual(progresso_final["status"], "concluido")
        self.assertEqual(progresso_final["total_registros"], 2)
        self.assertEqual(progresso_final["total_sucessos"], 2)

    @patch("apps.core_admin.services._ler_dataframe_upload")
    @patch("apps.core_admin.services.executar_resolucao_os_atendimento_ixc")
    def test_resolver_os_atendimento_ixc_view_repassa_execucao_id(
        self,
        mock_executar,
        mock_ler_dataframe,
    ):
        mock_executar.return_value = (True, "ok", "5313", "6394")
        mock_ler_dataframe.return_value = pd.DataFrame(
            [{"Atendimento_ID": 5313, "Confirmar_Resolucao": "SIM", "Tem_Anexo": "NAO"}]
        )

        self.client.force_login(self.admin)
        planilha = SimpleUploadedFile(
            "resolucao_os.csv",
            b"Atendimento_ID,Confirmar_Resolucao,Tem_Anexo\n5313,SIM,NAO\n",
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("resolver_os_atendimento_ixc"),
            {"arquivo_planilha_resolucao_os": planilha, "execucao_id": "exec-view-456"},
        )

        self.assertEqual(response.status_code, 200)
        progresso = core_admin_services.obter_progresso_resolucao_os_atendimento("exec-view-456")
        self.assertEqual(progresso["status"], "concluido")


@override_settings(EMAIL_HOST="smtp.exemplo.com")
class SmtpTestViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Diagnosticos: sem cobertura HTTP
    antes desta entrega."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-smtp", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-smtp", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("smtp_test"))

        self.assertEqual(response.status_code, 403)

    def test_get_renderiza_formulario(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("smtp_test"))

        self.assertEqual(response.status_code, 200)

    @patch("apps.core_admin.views.services.enviar_email_teste")
    def test_post_envia_email_com_sucesso(self, mock_enviar):
        mock_enviar.return_value = 1
        self.client.force_login(self.admin)

        response = self.client.post(reverse("smtp_test"), {
            "to_email": "destino@exemplo.com",
            "subject": "Assunto",
            "body": "Corpo",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["resultado_envio"]["ok"])
        mock_enviar.assert_called_once()

    @patch("apps.core_admin.views.services.enviar_email_teste")
    def test_post_email_invalido_nao_envia_e_mostra_erro(self, mock_enviar):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("smtp_test"), {
            "to_email": "nao-e-email",
            "subject": "Assunto",
            "body": "Corpo",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["resultado_envio"]["ok"])
        mock_enviar.assert_not_called()


class TestarApiIxcViewTests(TestCase):
    """Fatia core_admin (PO-011), slice Diagnosticos: sem cobertura HTTP
    antes desta entrega."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-ixc", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-ixc", password="senha-forte-123",
        )

    def test_usuario_nao_autenticado_recebe_401(self):
        response = self.client.post(reverse("testar_api_ixc"))

        self.assertEqual(response.status_code, 401)

    def test_usuario_sem_permissao_recebe_403(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.post(reverse("testar_api_ixc"))

        self.assertEqual(response.status_code, 403)

    def test_metodo_get_nao_permitido(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("testar_api_ixc"))

        self.assertEqual(response.status_code, 405)

    @patch("apps.core_admin.views.services.consultar_status_ixc")
    def test_post_sucesso_retorna_ok(self, mock_consultar):
        mock_consultar.return_value = {"ok": True, "status_code": 200, "url": "https://ixc.exemplo.com"}
        self.client.force_login(self.admin)

        response = self.client.post(reverse("testar_api_ixc"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    @patch("apps.core_admin.views.services.consultar_status_ixc")
    def test_post_excecao_retorna_ok_false(self, mock_consultar):
        mock_consultar.side_effect = RuntimeError("Falha de conexao")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("testar_api_ixc"))

        self.assertEqual(response.status_code, 200)
        corpo = response.json()
        self.assertFalse(corpo["ok"])
        self.assertIn("Falha de conexao", corpo["erro"])


class BackofficeImportPermissaoTests(TestCase):
    """Precisa de acesso real ao banco (AutomacaoMenu), por isso e TestCase
    e nao SimpleTestCase como o restante das views de Backoffice."""

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.usuario_sem_permissao = User.objects.create_user(
            username="sem_permissao", password="senha-teste"
        )

    def test_cotacao_import_bloqueia_usuario_sem_permissao(self):
        arquivo = _construir_upload_excel([{"Login_Login": "cliente1"}])
        request = self.factory.post(
            "/backoffice/cotacao/importar/",
            {"arquivo_cotacao": arquivo},
        )
        request.user = self.usuario_sem_permissao

        with self.assertRaises(PermissionDenied):
            cotacao_import(request)


class AutomacaoMenuTests(TestCase):
    def test_automacao_sem_menu_explicito_usa_administrador_como_padrao(self):
        automacao = AutomacaoMenu.objects.create(
            slug="automacao_nova",
            nome_exibicao="Automacao Nova",
            url_name="automacao_nova",
        )

        self.assertEqual(automacao.menu, AutomacaoMenu.MENU_ADMINISTRADOR)

    def test_migracao_de_dados_preservou_automacoes_existentes_em_administrador(self):
        slugs_existentes = [
            "import_prospects",
            "resolver_os_atendimento_ixc",
            "cotacao_import",
            "cadastrar_clientes_ixc",
        ]

        for slug in slugs_existentes:
            automacao = AutomacaoMenu.objects.get(slug=slug)
            self.assertEqual(automacao.menu, AutomacaoMenu.MENU_ADMINISTRADOR)
            self.assertTrue(automacao.ativo)

    def test_automacoes_do_menu_retorna_apenas_ativas_do_menu_informado(self):
        AutomacaoMenu.objects.create(
            slug="teste_backoffice_ativa",
            nome_exibicao="Backoffice Ativa",
            url_name="x",
            menu=AutomacaoMenu.MENU_BACKOFFICE,
        )
        AutomacaoMenu.objects.create(
            slug="teste_backoffice_inativa",
            nome_exibicao="Backoffice Inativa",
            url_name="x",
            menu=AutomacaoMenu.MENU_BACKOFFICE,
            ativo=False,
        )

        slugs = list(
            automacoes_do_menu(AutomacaoMenu.MENU_BACKOFFICE).values_list("slug", flat=True)
        )

        self.assertIn("teste_backoffice_ativa", slugs)
        self.assertNotIn("teste_backoffice_inativa", slugs)

    def test_realocar_automacao_reflete_sem_deploy(self):
        automacao = AutomacaoMenu.objects.create(
            slug="teste_realocacao",
            nome_exibicao="Automacao Realocavel",
            url_name="x",
            menu=AutomacaoMenu.MENU_ADMINISTRADOR,
        )

        self.assertIn(
            "teste_realocacao",
            automacoes_do_menu(AutomacaoMenu.MENU_ADMINISTRADOR).values_list("slug", flat=True),
        )

        automacao.menu = AutomacaoMenu.MENU_BACKOFFICE
        automacao.save(update_fields=["menu"])

        self.assertNotIn(
            "teste_realocacao",
            automacoes_do_menu(AutomacaoMenu.MENU_ADMINISTRADOR).values_list("slug", flat=True),
        )
        self.assertIn(
            "teste_realocacao",
            automacoes_do_menu(AutomacaoMenu.MENU_BACKOFFICE).values_list("slug", flat=True),
        )

    def test_usuario_pode_acessar_automacao_conforme_grupo_do_menu(self):
        AutomacaoMenu.objects.create(
            slug="teste_permissao_backoffice",
            nome_exibicao="Permissao Backoffice",
            url_name="x",
            menu=AutomacaoMenu.MENU_BACKOFFICE,
        )
        grupo_backoffice = Group.objects.create(name="Backoffice")
        grupo_parceiro = Group.objects.create(name="Parceiro")

        UserModel = get_user_model()
        usuario_autorizado = UserModel.objects.create_user(username="user_backoffice", email="b@x.com")
        usuario_autorizado.groups.add(grupo_backoffice)

        usuario_sem_permissao = UserModel.objects.create_user(username="user_parceiro", email="p@x.com")
        usuario_sem_permissao.groups.add(grupo_parceiro)

        superuser = UserModel.objects.create_superuser(username="admin_teste", email="a@x.com")

        self.assertTrue(usuario_pode_acessar_automacao(usuario_autorizado, "teste_permissao_backoffice"))
        self.assertFalse(usuario_pode_acessar_automacao(usuario_sem_permissao, "teste_permissao_backoffice"))
        self.assertTrue(usuario_pode_acessar_automacao(superuser, "teste_permissao_backoffice"))

    def test_usuario_pode_acessar_automacao_inexistente_retorna_falso(self):
        UserModel = get_user_model()
        usuario = UserModel.objects.create_user(username="user_qualquer", email="q@x.com")

        self.assertFalse(usuario_pode_acessar_automacao(usuario, "slug_que_nao_existe"))


class AcessoBancoDadosAdminTests(TestCase):
    def _criar_acesso(self):
        return AcessoBancoDados.objects.create(
            nome="Acesso teste",
            usuario_banco="usuario_teste",
            senha_banco="senha_teste",
            host_acesso="%",
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_aplicar_acesso_sem_variavel_de_ambiente_falha_sem_senha_padrao(self):
        acesso = self._criar_acesso()

        with self.assertRaises(RuntimeError):
            AcessoBancoDadosAdmin(AcessoBancoDados, admin.site)._aplicar_acesso(acesso)

    @patch("apps.core_admin.admin.MySQLdb.connect")
    @patch.dict("os.environ", {"MYSQL_ROOT_PASSWORD": "senha_do_ambiente"}, clear=True)
    def test_aplicar_acesso_usa_senha_da_variavel_de_ambiente(self, mock_connect):
        acesso = self._criar_acesso()

        AcessoBancoDadosAdmin(AcessoBancoDados, admin.site)._aplicar_acesso(acesso)

        mock_connect.assert_called_once()
        self.assertEqual(mock_connect.call_args.kwargs["passwd"], "senha_do_ambiente")


class ProcessosViewTests(TestCase):
    """PO-050/ADR-014: tela de Processos (Setor/Status), so listar e criar."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-processos", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-processos", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado_na_lista(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("processos_list"))

        self.assertEqual(response.status_code, 403)

    def test_lista_processos_status_200(self):
        Processo.objects.create(nome="Processo QA A")
        self.client.force_login(self.admin)

        response = self.client.get(reverse("processos_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Processo QA A")

    def test_post_cria_processo_e_redireciona_para_detalhe(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("processos_list"), {"nome": "Processo Teste"})

        processo = Processo.objects.get(nome="Processo Teste")
        self.assertRedirects(response, reverse("processo_detail", args=[processo.pk]))

    def test_post_sem_nome_nao_cria_processo(self):
        self.client.force_login(self.admin)
        total_antes = Processo.objects.count()

        response = self.client.post(reverse("processos_list"), {"nome": ""})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Processo.objects.count(), total_antes)

    def test_usuario_sem_permissao_e_bloqueado_no_detalhe(self):
        processo = Processo.objects.create(nome="Processo QA A")
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("processo_detail", args=[processo.pk]))

        self.assertEqual(response.status_code, 403)

    def test_detalhe_mostra_setores_e_status(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        SetorStatus.objects.create(setor=setor, nome="A fazer")
        self.client.force_login(self.admin)

        response = self.client.get(reverse("processo_detail", args=[processo.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lastmile")
        self.assertContains(response, "A fazer")

    def test_post_no_detalhe_adiciona_setor(self):
        processo = Processo.objects.create(nome="Processo QA A")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("processo_detail", args=[processo.pk]), {"nome": "Suporte"})

        self.assertRedirects(response, reverse("processo_detail", args=[processo.pk]))
        self.assertTrue(processo.setores.filter(nome="Suporte").exists())

    def test_post_no_detalhe_com_setor_duplicado_nao_cria_outro(self):
        processo = Processo.objects.create(nome="Processo QA A")
        Setor.objects.create(processo=processo, nome="Suporte")
        self.client.force_login(self.admin)

        self.client.post(reverse("processo_detail", args=[processo.pk]), {"nome": "Suporte"})

        self.assertEqual(processo.setores.filter(nome="Suporte").count(), 1)

    def test_post_adiciona_status_ao_setor(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("processo_setor_status_criar", args=[processo.pk, setor.pk]),
            {"nome": "Em andamento"},
        )

        self.assertRedirects(response, reverse("processo_detail", args=[processo.pk]))
        self.assertTrue(setor.status_opcoes.filter(nome="Em andamento").exists())

    def test_post_status_duplicado_nao_cria_outro(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        SetorStatus.objects.create(setor=setor, nome="Em andamento")
        self.client.force_login(self.admin)

        self.client.post(
            reverse("processo_setor_status_criar", args=[processo.pk, setor.pk]),
            {"nome": "Em andamento"},
        )

        self.assertEqual(setor.status_opcoes.filter(nome="Em andamento").count(), 1)

    def test_usuario_sem_permissao_e_bloqueado_na_exclusao_de_status(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor, nome="A fazer")
        self.client.force_login(self.sem_permissao)

        response = self.client.post(
            reverse("processo_setor_status_excluir", args=[processo.pk, setor.pk, status.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(SetorStatus.objects.filter(pk=status.pk).exists())

    def test_post_exclui_status_do_setor(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor, nome="A fazer")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("processo_setor_status_excluir", args=[processo.pk, setor.pk, status.pk])
        )

        self.assertRedirects(response, reverse("processo_detail", args=[processo.pk]))
        self.assertFalse(SetorStatus.objects.filter(pk=status.pk).exists())

    def test_get_na_exclusao_nao_apaga_status(self):
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor, nome="A fazer")
        self.client.force_login(self.admin)

        self.client.get(
            reverse("processo_setor_status_excluir", args=[processo.pk, setor.pk, status.pk])
        )

        self.assertTrue(SetorStatus.objects.filter(pk=status.pk).exists())

    def test_excluir_status_com_setor_de_outro_processo_retorna_404(self):
        processo = Processo.objects.create(nome="Processo QA A")
        outro_processo = Processo.objects.create(nome="Processo QA B")
        setor_outro_processo = Setor.objects.create(processo=outro_processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor_outro_processo, nome="A fazer")
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("processo_setor_status_excluir", args=[processo.pk, setor_outro_processo.pk, status.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(SetorStatus.objects.filter(pk=status.pk).exists())

    def test_excluir_status_em_uso_deixa_rede_externa_sem_status(self):
        """RN-034: Status em uso pode ser excluido; RedeExterna/RedeInterna
        que apontavam para ele ficam com o campo `status` em branco
        (on_delete=SET_NULL, RN-026), sem apagar o RE."""
        processo = Processo.objects.create(nome="Processo QA A")
        setor = Setor.objects.create(processo=processo, nome="Lastmile")
        status = SetorStatus.objects.create(setor=setor, nome="Em andamento")
        escola = Escola.objects.create(jira_key="ESC-QA-034")
        rede_externa = RedeExterna.objects.create(escola=escola, setor=setor, status=status)
        self.client.force_login(self.admin)

        self.client.post(
            reverse("processo_setor_status_excluir", args=[processo.pk, setor.pk, status.pk])
        )

        rede_externa.refresh_from_db()
        self.assertIsNone(rede_externa.status)
        self.assertEqual(rede_externa.setor, setor)


class CamposViewTests(TestCase):
    """PO-057/ADR-019: tela de Campos personalizados por Setor (RN-031),
    nesta versao so listar e criar."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-campos", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-campos", password="senha-forte-123",
        )
        processo = Processo.objects.create(nome="Processo QA A")
        self.setor = Setor.objects.create(processo=processo, nome="Lastmile")

    def test_usuario_sem_permissao_e_bloqueado(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("campos_list"))

        self.assertEqual(response.status_code, 403)

    def test_lista_campos_status_200(self):
        Campo.objects.create(nome="Data de instalação", tipo=Campo.TIPO_DATA, setor_nome="Lastmile")
        self.client.force_login(self.admin)

        response = self.client.get(reverse("campos_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data de instalação")

    def test_post_cria_campo_texto(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campos_list"), {
            "nome": "Observação",
            "tipo": Campo.TIPO_TEXTO,
            "setor_nome": self.setor.nome,
            "opcoes_texto": "",
        })

        self.assertRedirects(response, reverse("campos_list"))
        campo = Campo.objects.get(nome="Observação")
        self.assertEqual(campo.tipo, Campo.TIPO_TEXTO)
        self.assertEqual(campo.setor_nome, "Lastmile")
        self.assertEqual(campo.opcoes, [])

    def test_post_lista_sem_opcoes_nao_cria_campo(self):
        total_antes = Campo.objects.count()
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campos_list"), {
            "nome": "Categoria",
            "tipo": Campo.TIPO_LISTA,
            "setor_nome": self.setor.nome,
            "opcoes_texto": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Campo.objects.count(), total_antes)
        self.assertContains(response, "Informe pelo menos uma opção para o tipo Lista.")

    def test_post_lista_com_opcoes_cria_campo(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campos_list"), {
            "nome": "Categoria",
            "tipo": Campo.TIPO_LISTA,
            "setor_nome": self.setor.nome,
            "opcoes_texto": "Opção A\nOpção B",
        })

        self.assertRedirects(response, reverse("campos_list"))
        campo = Campo.objects.get(nome="Categoria")
        self.assertEqual(campo.opcoes, ["Opção A", "Opção B"])


class CampoEditarExcluirViewTests(TestCase):
    """PO-061/ADR-021: edicao e exclusao de Campos personalizados (RN-036)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-campos-editar", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-campos-editar", password="senha-forte-123",
        )
        processo = Processo.objects.create(nome="Processo QA A")
        self.setor = Setor.objects.create(processo=processo, nome="Lastmile")
        self.campo = Campo.objects.create(nome="Observação", tipo=Campo.TIPO_TEXTO, setor_nome=self.setor.nome)

    def test_usuario_sem_permissao_e_bloqueado_ao_editar(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("campo_editar", args=[self.campo.pk]))

        self.assertEqual(response.status_code, 403)

    def test_usuario_sem_permissao_e_bloqueado_ao_excluir(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.post(reverse("campo_excluir", args=[self.campo.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Campo.objects.filter(pk=self.campo.pk).exists())

    def test_get_editar_preenche_opcoes_do_campo_lista(self):
        campo_lista = Campo.objects.create(
            nome="Categoria", tipo=Campo.TIPO_LISTA, setor_nome=self.setor.nome, opcoes=["Opção A", "Opção B"],
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("campo_editar", args=[campo_lista.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opção A\nOpção B")

    def test_post_editar_atualiza_nome_tipo_e_setor(self):
        outro_setor = Setor.objects.create(processo=self.setor.processo, nome="Suprimentos")
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campo_editar", args=[self.campo.pk]), {
            "nome": "Observação geral",
            "tipo": Campo.TIPO_TEXTO,
            "setor_nome": outro_setor.nome,
            "opcoes_texto": "",
        })

        self.assertRedirects(response, reverse("campos_list"))
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.nome, "Observação geral")
        self.assertEqual(self.campo.setor_nome, "Suprimentos")

    def test_post_editar_troca_tipo_com_valor_gravado_nao_bloqueia_nem_limpa(self):
        """RN-036: trocar o tipo de um Campo com CampoValor ja gravados e
        permitido, sem bloqueio nem limpeza automatica do valor existente."""
        escola = Escola.objects.create(jira_key="ESC-QA-036")
        rede_externa = RedeExterna.objects.create(escola=escola, setor=self.setor)
        valor = CampoValor.objects.create(
            campo=self.campo,
            content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=rede_externa.pk,
            valor="texto gravado antes da troca",
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campo_editar", args=[self.campo.pk]), {
            "nome": self.campo.nome,
            "tipo": Campo.TIPO_LISTA,
            "setor_nome": self.setor.nome,
            "opcoes_texto": "Opção A\nOpção B",
        })

        self.assertRedirects(response, reverse("campos_list"))
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.tipo, Campo.TIPO_LISTA)
        valor.refresh_from_db()
        self.assertEqual(valor.valor, "texto gravado antes da troca")

    def test_get_excluir_nao_apaga_campo(self):
        self.client.force_login(self.admin)

        self.client.get(reverse("campo_excluir", args=[self.campo.pk]))

        self.assertTrue(Campo.objects.filter(pk=self.campo.pk).exists())

    def test_post_excluir_apaga_campo_e_campovalor_em_cascata(self):
        escola = Escola.objects.create(jira_key="ESC-QA-036B")
        rede_externa = RedeExterna.objects.create(escola=escola, setor=self.setor)
        valor = CampoValor.objects.create(
            campo=self.campo,
            content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=rede_externa.pk,
            valor="sera perdido",
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse("campo_excluir", args=[self.campo.pk]))

        self.assertRedirects(response, reverse("campos_list"))
        self.assertFalse(Campo.objects.filter(pk=self.campo.pk).exists())
        self.assertFalse(CampoValor.objects.filter(pk=valor.pk).exists())


class CampoCalculadoEStatusCondicionanteViewTests(TestCase):
    """PO-063/RN-039/ADR-024: cadastro do tipo Calculado e do Status
    condicionante pela tela "Campos" (Administracao), e protecao contra
    exclusao do Campo base de um Campo Calculado."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-campos-calculado", password="senha-forte-123", is_superuser=True,
        )
        self.client.force_login(self.admin)
        processo = Processo.objects.create(nome="Processo QA Calculado")
        self.setor = Setor.objects.create(processo=processo, nome="Implantacao")
        self.campo_data = Campo.objects.create(
            nome="Início Implantação", tipo=Campo.TIPO_DATA, setor_nome="Implantacao",
        )

    def test_post_cria_campo_calculado_valido(self):
        response = self.client.post(reverse("campos_list"), {
            "nome": "Data Final Implantação",
            "tipo": Campo.TIPO_CALCULADO,
            "setor_nome": "Implantacao",
            "opcoes_texto": "",
            "campo_base": self.campo_data.pk,
            "horas_prazo": "72",
        })

        self.assertRedirects(response, reverse("campos_list"))
        campo = Campo.objects.get(nome="Data Final Implantação")
        self.assertEqual(campo.campo_base_id, self.campo_data.pk)
        self.assertEqual(campo.horas_prazo, 72)

    def test_post_calculado_sem_campo_base_nao_cria(self):
        total_antes = Campo.objects.count()

        response = self.client.post(reverse("campos_list"), {
            "nome": "Data Final Implantação",
            "tipo": Campo.TIPO_CALCULADO,
            "setor_nome": "Implantacao",
            "opcoes_texto": "",
            "horas_prazo": "72",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Campo.objects.count(), total_antes)
        self.assertContains(response, "Selecione o Campo base para o tipo Calculado.")

    def test_post_calculado_com_campo_base_de_outro_setor_nao_cria(self):
        campo_data_outro_setor = Campo.objects.create(
            nome="Data outro setor", tipo=Campo.TIPO_DATA, setor_nome="Suprimentos",
        )
        total_antes = Campo.objects.count()

        response = self.client.post(reverse("campos_list"), {
            "nome": "Data Final Implantação",
            "tipo": Campo.TIPO_CALCULADO,
            "setor_nome": "Implantacao",
            "opcoes_texto": "",
            "campo_base": campo_data_outro_setor.pk,
            "horas_prazo": "72",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Campo.objects.count(), total_antes)
        self.assertContains(response, "O Campo base precisa pertencer ao mesmo Setor do campo calculado.")

    def test_post_calculado_sem_horas_prazo_nao_cria(self):
        total_antes = Campo.objects.count()

        response = self.client.post(reverse("campos_list"), {
            "nome": "Data Final Implantação",
            "tipo": Campo.TIPO_CALCULADO,
            "setor_nome": "Implantacao",
            "opcoes_texto": "",
            "campo_base": self.campo_data.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Campo.objects.count(), total_antes)
        self.assertContains(response, "Informe um número positivo de horas de prazo.")

    def test_post_cria_campo_com_status_condicionante(self):
        response = self.client.post(reverse("campos_list"), {
            "nome": "Início Implantação B",
            "tipo": Campo.TIPO_DATA,
            "setor_nome": "Implantacao",
            "opcoes_texto": "",
            "status_condicionante_nome": "Agendando Parceiro",
        })

        self.assertRedirects(response, reverse("campos_list"))
        campo = Campo.objects.get(nome="Início Implantação B")
        self.assertEqual(campo.status_condicionante_nome, "Agendando Parceiro")

    def test_post_excluir_campo_base_de_calculado_e_bloqueado(self):
        Campo.objects.create(
            nome="Data Final Implantação", tipo=Campo.TIPO_CALCULADO, setor_nome="Implantacao",
            campo_base=self.campo_data, horas_prazo=72,
        )

        response = self.client.post(reverse("campo_excluir", args=[self.campo_data.pk]))

        self.assertRedirects(response, reverse("campos_list"))
        self.assertTrue(Campo.objects.filter(pk=self.campo_data.pk).exists())


class SetorEscopoViewTests(TestCase):
    """PO-062/ADR-022: tela "Setor" (Administracao) — escopo de exibicao do
    Setor (RN-025) entre Escola e RE/RI/Mapa Calor (RN-037/RN-043)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-setor-escopo", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-setor-escopo", password="senha-forte-123",
        )
        processo = Processo.objects.create(nome="Processo QA A")
        self.setor = Setor.objects.create(processo=processo, nome="Lastmile")

    def test_usuario_sem_permissao_e_bloqueado_na_lista(self):
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("setor_escopo_list"))

        self.assertEqual(response.status_code, 403)

    def test_lista_mostra_setor_nao_configurado(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("setor_escopo_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lastmile")
        self.assertContains(response, "Não configurado")

    def test_post_cria_escopo_escola(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("setor_escopo_list"), {
            "setor_nome": self.setor.nome,
            "atividade": SetorEscopo.ATIVIDADE_ESCOLA,
        })

        self.assertRedirects(response, reverse("setor_escopo_list"))
        escopo = SetorEscopo.objects.get(setor_nome="Lastmile")
        self.assertEqual(escopo.atividade, SetorEscopo.ATIVIDADE_ESCOLA)

    def test_post_cria_escopo_sub_atividades_somente_re(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("setor_escopo_list"), {
            "setor_nome": self.setor.nome,
            "atividade": SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            "aplica_re": "on",
        })

        self.assertRedirects(response, reverse("setor_escopo_list"))
        escopo = SetorEscopo.objects.get(setor_nome="Lastmile")
        self.assertTrue(escopo.aplica_re)
        self.assertFalse(escopo.aplica_ri)

    def test_post_sub_atividades_sem_re_ri_nem_mapa_calor_nao_salva(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("setor_escopo_list"), {
            "setor_nome": self.setor.nome,
            "atividade": SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SetorEscopo.objects.filter(setor_nome="Lastmile").exists())
        self.assertContains(response, "Selecione ao menos RE, RI ou Mapa Calor")

    def test_post_cria_escopo_sub_atividades_somente_mapa_calor(self):
        """RN-043: Mapa Calor pode ser marcado isoladamente, assim como ja
        acontecia com RE ou RI isoladamente."""
        self.client.force_login(self.admin)

        response = self.client.post(reverse("setor_escopo_list"), {
            "setor_nome": self.setor.nome,
            "atividade": SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            "aplica_mapa_calor": "on",
        })

        self.assertRedirects(response, reverse("setor_escopo_list"))
        escopo = SetorEscopo.objects.get(setor_nome="Lastmile")
        self.assertFalse(escopo.aplica_re)
        self.assertFalse(escopo.aplica_ri)
        self.assertTrue(escopo.aplica_mapa_calor)

    def test_setor_ja_configurado_nao_aparece_nas_opcoes_de_criar(self):
        SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("setor_escopo_list"))

        form = response.context["form"]
        self.assertNotIn("Lastmile", dict(form.fields["setor_nome"].choices))

    def test_usuario_sem_permissao_e_bloqueado_ao_editar(self):
        escopo = SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        self.client.force_login(self.sem_permissao)

        response = self.client.get(reverse("setor_escopo_editar", args=[escopo.pk]))

        self.assertEqual(response.status_code, 403)

    def test_post_editar_troca_para_sub_atividades(self):
        escopo = SetorEscopo.objects.create(setor_nome="Lastmile", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        self.client.force_login(self.admin)

        response = self.client.post(reverse("setor_escopo_editar", args=[escopo.pk]), {
            "setor_nome": "Lastmile",
            "atividade": SetorEscopo.ATIVIDADE_SUB_ATIVIDADES,
            "aplica_re": "on",
            "aplica_ri": "on",
        })

        self.assertRedirects(response, reverse("setor_escopo_list"))
        escopo.refresh_from_db()
        self.assertEqual(escopo.atividade, SetorEscopo.ATIVIDADE_SUB_ATIVIDADES)
        self.assertTrue(escopo.aplica_re)
        self.assertTrue(escopo.aplica_ri)


@override_settings(
    EMAIL_HOST="smtp.teste.local",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EscolaEnviarEmailTests(TestCase):
    """PO-066/RN-042: e-mail enviado a partir da Escola (nivel "Global") ou
    de um RE/RI, com o log caindo no historico do nivel correto — mesma
    regra de visibilidade individual/combinada da RN-029."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dev-tester-email-escola", password="senha-segura", is_superuser=True,
        )
        self.client.force_login(self.user)

        self.escola = Escola.objects.create(
            jira_key="EACE-EMAIL", nome="Escola E-mail", inep="12345678",
        )
        self.processo_re, _ = self._get_or_create_processo(RedeExterna)
        self.processo_ri, _ = self._get_or_create_processo(RedeInterna)

    @staticmethod
    def _get_or_create_processo(modelo):
        return Processo.objects.get_or_create(nome=modelo.NOME_PROCESSO_PADRAO)

    def _content_type(self, modelo):
        return ContentType.objects.get_for_model(modelo)

    def test_envio_pelo_re_gera_historico_somente_no_re(self):
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        ri = RedeInterna.objects.create(escola=self.escola, processo=self.processo_ri)

        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "re"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Documentacao pendente",
            "body": "Favor enviar os documentos.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail enviado.")
        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertIn("ESC-", enviado.subject)
        self.assertIn("-12345678-RE", enviado.subject)

        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=self._content_type(RedeExterna), object_id=re.id).exists()
        )
        self.assertFalse(
            RegistroHistorico.objects.filter(content_type=self._content_type(RedeInterna), object_id=ri.id).exists()
        )

    def test_envio_pelo_ri_nao_aparece_no_modal_do_re(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        RedeInterna.objects.create(escola=self.escola, processo=self.processo_ri)

        self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "ri"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Assunto do RI",
            "body": "Mensagem do RI.",
        })

        response_re = self.client.get(reverse("escola_rede_historico", args=[self.escola.pk, "re"]))
        self.assertNotContains(response_re, "Assunto do RI")

        response_ri = self.client.get(reverse("escola_rede_historico", args=[self.escola.pk, "ri"]))
        self.assertContains(response_ri, "E-mail enviado pela tela de Rede Interna (RI)")

    def test_envio_pela_escola_aparece_na_visao_combinada(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        RedeInterna.objects.create(escola=self.escola, processo=self.processo_ri)

        response = self.client.post(reverse("escola_enviar_email", args=[self.escola.pk]), {
            "to": "destinatario@exemplo.com",
            "subject": "Aviso geral",
            "body": "Mensagem para a escola.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail enviado.")
        self.assertContains(response, "ESCOLA")

        escola_content_type = self._content_type(Escola)
        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=escola_content_type, object_id=self.escola.id).exists()
        )

        enviado = mail.outbox[0]
        self.assertIn("-Global", enviado.subject)

    def test_envio_sem_destinatario_mostra_erro_e_nao_envia(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "re"]), {
            "to": "",
            "subject": "Assunto",
            "body": "Mensagem",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe ao menos um destinatario")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_HOST="")
    def test_smtp_nao_configurado_mostra_erro(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "re"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Assunto",
            "body": "Mensagem",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O SMTP ainda nao foi configurado")

    def test_usuario_sem_permissao_e_bloqueado(self):
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)
        sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-email-escola", password="senha-segura",
        )
        self.client.force_login(sem_permissao)

        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "re"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Assunto",
            "body": "Mensagem",
        })

        self.assertEqual(response.status_code, 403)

    def test_tipo_de_rede_invalido_devolve_404(self):
        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "xx"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Assunto",
            "body": "Mensagem",
        })

        self.assertEqual(response.status_code, 404)

    def test_envio_pelo_mapa_calor_gera_historico_somente_no_mapa_calor(self):
        """RN-043: Mapa Calor e um terceiro "sub-ticket" — mesma regra de
        isolamento ja usada por RE/RI (RN-042)."""
        processo_mc, _ = self._get_or_create_processo(MapaCalor)
        mc = MapaCalor.objects.create(escola=self.escola, processo=processo_mc)
        re = RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        response = self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "mc"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Documentacao do Mapa Calor",
            "body": "Favor enviar os documentos do Mapa Calor.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "E-mail enviado.")
        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertIn("ESC-", enviado.subject)
        self.assertIn("-12345678-MC", enviado.subject)

        self.assertTrue(
            RegistroHistorico.objects.filter(content_type=self._content_type(MapaCalor), object_id=mc.id).exists()
        )
        self.assertFalse(
            RegistroHistorico.objects.filter(content_type=self._content_type(RedeExterna), object_id=re.id).exists()
        )

    def test_envio_pelo_mapa_calor_nao_aparece_no_modal_do_re(self):
        processo_mc, _ = self._get_or_create_processo(MapaCalor)
        MapaCalor.objects.create(escola=self.escola, processo=processo_mc)
        RedeExterna.objects.create(escola=self.escola, processo=self.processo_re)

        self.client.post(reverse("escola_rede_enviar_email", args=[self.escola.pk, "mc"]), {
            "to": "destinatario@exemplo.com",
            "subject": "Assunto do Mapa Calor",
            "body": "Mensagem do Mapa Calor.",
        })

        response_re = self.client.get(reverse("escola_rede_historico", args=[self.escola.pk, "re"]))
        self.assertNotContains(response_re, "Assunto do Mapa Calor")

        response_mc = self.client.get(reverse("escola_rede_historico", args=[self.escola.pk, "mc"]))
        self.assertContains(response_mc, "E-mail enviado pela tela de Mapa Calor (MC)")


class ImportacaoExportacaoViewTests(TestCase):
    """PO-071/RN-048: tela "Importação e Exportação" (Administração) e o
    card de exportacao de Setores e Escolas em CSV — uma linha por Escola,
    no mesmo formato de colunas ja exibido na tela de Setor."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin-import-export", password="senha-forte-123", is_superuser=True,
        )
        self.sem_permissao = get_user_model().objects.create_user(
            username="sem-permissao-import-export", password="senha-forte-123",
        )

    def test_usuario_sem_permissao_e_bloqueado_na_tela(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("importacao_exportacao"))

        self.assertEqual(response.status_code, 403)

    def test_usuario_sem_permissao_e_bloqueado_na_exportacao(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("exportar_setores_escolas"))

        self.assertEqual(response.status_code, 403)

    def test_tela_renderiza_o_card_de_exportacao(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("importacao_exportacao"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exportação de Setores e Escolas")

    def test_usuario_sem_permissao_e_bloqueado_no_modelo(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse("exportar_setores_escolas_modelo"))

        self.assertEqual(response.status_code, 403)

    def test_modelo_tem_as_colunas_mas_nenhuma_linha_de_escola(self):
        self.client.force_login(self.admin)
        Escola.objects.create(jira_key="EACE-MODELO", nome="Escola Que Nao Deve Aparecer no Modelo")

        response = self.client.get(reverse("exportar_setores_escolas_modelo"))
        conteudo = response.content.decode("utf-8-sig")
        linhas = conteudo.strip().splitlines()

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertIn("modelo_setores_escolas", response["Content-Disposition"])
        self.assertEqual(
            linhas[0],
            "INEP,Nome da Escola,Estado,Municipio,Logradouro,Numero,Bairro,CEP,Status,"
            "Setor RE,Parceiro RE,Status RE,Setor RI,Parceiro RI,Status RI,"
            "Setor MC,Parceiro MC,Status MC",
        )
        self.assertEqual(len(linhas), 1)

    def test_modelo_reflete_campo_personalizado_atual_sem_valores(self):
        self.client.force_login(self.admin)
        Campo.objects.create(nome="Circuito ID", tipo=Campo.TIPO_TEXTO, setor_nome="Comercial")

        response = self.client.get(reverse("exportar_setores_escolas_modelo"))
        conteudo = response.content.decode("utf-8-sig")
        linhas = conteudo.strip().splitlines()

        self.assertIn("Campo Personalizado - Circuito ID (RE)", linhas[0])
        self.assertEqual(len(linhas), 1)

    def test_exportacao_gera_csv_uma_linha_por_escola(self):
        self.client.force_login(self.admin)
        escola = Escola.objects.create(
            jira_key="EACE-EXPORT", nome="Escola Exportacao", uf="CE",
            municipio="Fortaleza", inep="12345678",
            logradouro="Rua Teste", numero="1", bairro="Centro", cep="60000-000",
            status_escola="Ativa",
        )
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        setor = Setor.objects.create(processo=processo, nome="Comercial")
        status = SetorStatus.objects.create(setor=setor, nome="Aguardando")
        parceiro = Partner.objects.create(razao_social="Parceiro Fibra Norte")
        RedeExterna.objects.create(escola=escola, processo=processo, setor=setor, status=status, parceiro=parceiro)

        response = self.client.get(reverse("exportar_setores_escolas"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", response["Content-Disposition"])

        conteudo = response.content.decode("utf-8-sig")
        cabecalho = conteudo.strip().splitlines()[0]
        self.assertEqual(
            cabecalho,
            "INEP,Nome da Escola,Estado,Municipio,Logradouro,Numero,Bairro,CEP,Status,"
            "Setor RE,Parceiro RE,Status RE,Setor RI,Parceiro RI,Status RI,"
            "Setor MC,Parceiro MC,Status MC",
        )
        self.assertIn("Escola Exportacao", conteudo)
        self.assertIn("Rua Teste", conteudo)
        self.assertIn("Centro", conteudo)
        self.assertIn("60000-000", conteudo)
        self.assertIn("Comercial", conteudo)
        self.assertIn("Aguardando", conteudo)
        self.assertIn("Parceiro Fibra Norte", conteudo)

    def test_exportacao_deixa_colunas_vazias_quando_escola_nao_tem_subatividade(self):
        self.client.force_login(self.admin)
        Escola.objects.create(jira_key="EACE-SEM-REDE", nome="Escola Sem Rede")

        response = self.client.get(reverse("exportar_setores_escolas"))
        conteudo = response.content.decode("utf-8-sig")
        linha = next(linha for linha in conteudo.splitlines() if "Escola Sem Rede" in linha)

        self.assertEqual(linha.split(",")[9:], ["", "", "", "", "", "", "", "", ""])

    def test_exportacao_nao_faz_uma_consulta_por_escola(self):
        self.client.force_login(self.admin)
        Escola.objects.create(jira_key="EACE-N1", nome="Escola Unica")

        with CaptureQueriesContext(connection) as consultas_com_uma_escola:
            self.client.get(reverse("exportar_setores_escolas"))

        for indice in range(2, 6):
            Escola.objects.create(jira_key=f"EACE-N{indice}", nome=f"Escola {indice}")

        with CaptureQueriesContext(connection) as consultas_com_cinco_escolas:
            self.client.get(reverse("exportar_setores_escolas"))

        self.assertEqual(len(consultas_com_uma_escola), len(consultas_com_cinco_escolas))

    @staticmethod
    def _linhas_csv(response):
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))

    def test_exportacao_inclui_campo_personalizado_por_subatividade_sem_setorescopo(self):
        """RN-049: Campo sem `SetorEscopo` cadastrado segue o comportamento
        legado — aplica a RE, RI e Mapa Calor, uma coluna por subatividade."""
        self.client.force_login(self.admin)
        escola = Escola.objects.create(jira_key="EACE-CAMPO", nome="Escola Campo Personalizado")
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        setor = Setor.objects.create(processo=processo, nome="Comercial")
        rede_externa = RedeExterna.objects.create(escola=escola, processo=processo, setor=setor)

        campo = Campo.objects.create(nome="Circuito ID", tipo=Campo.TIPO_TEXTO, setor_nome="Comercial")
        CampoValor.objects.create(
            campo=campo, content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=rede_externa.pk, valor="ABC-123",
        )

        response = self.client.get(reverse("exportar_setores_escolas"))
        cabecalho, *linhas = self._linhas_csv(response)
        linha = next(linha for linha in linhas if "Escola Campo Personalizado" in linha)

        for sufixo in ("RE", "RI", "MC"):
            self.assertIn(f"Campo Personalizado - Circuito ID ({sufixo})", cabecalho)

        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Circuito ID (RE)")], "ABC-123")
        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Circuito ID (RI)")], "")
        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Circuito ID (MC)")], "")

    def test_exportacao_gera_uma_coluna_para_campo_personalizado_com_escopo_escola(self):
        self.client.force_login(self.admin)
        escola = Escola.objects.create(jira_key="EACE-ESCOLA-CAMPO", nome="Escola Nivel Escola")
        SetorEscopo.objects.create(setor_nome="Financeiro", atividade=SetorEscopo.ATIVIDADE_ESCOLA)
        campo = Campo.objects.create(nome="Contrato Assinado", tipo=Campo.TIPO_SIM_NAO, setor_nome="Financeiro")
        CampoValor.objects.create(
            campo=campo, content_type=ContentType.objects.get_for_model(Escola),
            object_id=escola.pk, valor=True,
        )

        response = self.client.get(reverse("exportar_setores_escolas"))
        cabecalho, *linhas = self._linhas_csv(response)
        linha = next(linha for linha in linhas if "Escola Nivel Escola" in linha)

        self.assertIn("Campo Personalizado - Contrato Assinado", cabecalho)
        self.assertNotIn("Campo Personalizado - Contrato Assinado (RE)", cabecalho)
        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Contrato Assinado")], "Sim")

    def test_exportacao_calcula_campo_personalizado_tipo_calculado(self):
        self.client.force_login(self.admin)
        escola = Escola.objects.create(jira_key="EACE-CALC", nome="Escola Calculado")
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        setor = Setor.objects.create(processo=processo, nome="Tecnico")
        rede = RedeExterna.objects.create(escola=escola, processo=processo, setor=setor)

        campo_base = Campo.objects.create(nome="Data Base", tipo=Campo.TIPO_DATA, setor_nome="Tecnico")
        Campo.objects.create(
            nome="Prazo Final", tipo=Campo.TIPO_CALCULADO, setor_nome="Tecnico",
            campo_base=campo_base, horas_prazo=48,
        )
        CampoValor.objects.create(
            campo=campo_base, content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=rede.pk, valor="2026-08-01",
        )

        response = self.client.get(reverse("exportar_setores_escolas"))
        cabecalho, *linhas = self._linhas_csv(response)
        linha = next(linha for linha in linhas if "Escola Calculado" in linha)

        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Prazo Final (RE)")], "03/08/2026")

    def test_exportacao_deixa_campo_personalizado_em_branco_quando_status_nao_bate(self):
        self.client.force_login(self.admin)
        escola = Escola.objects.create(jira_key="EACE-COND", nome="Escola Condicionante")
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        setor = Setor.objects.create(processo=processo, nome="Suporte Tecnico")
        status_diferente = SetorStatus.objects.create(setor=setor, nome="Em atendimento")
        rede = RedeExterna.objects.create(escola=escola, processo=processo, setor=setor, status=status_diferente)

        campo = Campo.objects.create(
            nome="Motivo Bloqueio", tipo=Campo.TIPO_TEXTO, setor_nome="Suporte Tecnico",
            status_condicionante_nome="Bloqueado",
        )
        CampoValor.objects.create(
            campo=campo, content_type=ContentType.objects.get_for_model(RedeExterna),
            object_id=rede.pk, valor="Falta de fibra",
        )

        response = self.client.get(reverse("exportar_setores_escolas"))
        cabecalho, *linhas = self._linhas_csv(response)
        linha = next(linha for linha in linhas if "Escola Condicionante" in linha)

        self.assertEqual(linha[cabecalho.index("Campo Personalizado - Motivo Bloqueio (RE)")], "")

    def test_exportacao_com_campos_personalizados_nao_faz_uma_consulta_por_escola(self):
        self.client.force_login(self.admin)
        processo, _ = Processo.objects.get_or_create(nome=RedeExterna.NOME_PROCESSO_PADRAO)
        setor = Setor.objects.create(processo=processo, nome="Operacoes")
        campo = Campo.objects.create(nome="Observacao", tipo=Campo.TIPO_TEXTO, setor_nome="Operacoes")

        def criar_escola_com_campo(sufixo):
            escola = Escola.objects.create(jira_key=f"EACE-OPS-{sufixo}", nome=f"Escola Ops {sufixo}")
            rede = RedeExterna.objects.create(escola=escola, processo=processo, setor=setor)
            CampoValor.objects.create(
                campo=campo, content_type=ContentType.objects.get_for_model(RedeExterna),
                object_id=rede.pk, valor=f"nota {sufixo}",
            )

        criar_escola_com_campo(1)
        with CaptureQueriesContext(connection) as consultas_com_uma_escola:
            self.client.get(reverse("exportar_setores_escolas"))

        for indice in range(2, 6):
            criar_escola_com_campo(indice)
        with CaptureQueriesContext(connection) as consultas_com_cinco_escolas:
            self.client.get(reverse("exportar_setores_escolas"))

        self.assertEqual(len(consultas_com_uma_escola), len(consultas_com_cinco_escolas))
