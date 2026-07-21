import zipfile
from io import BytesIO
from unittest.mock import Mock, patch

import pandas as pd
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase

from core_admin.admin import AcessoBancoDadosAdmin
from core_admin.automacoes_registry import (
    automacoes_do_menu,
    usuario_pode_acessar_automacao,
)
from core_admin.models import AcessoBancoDados, AutomacaoMenu
from apps.core_admin.views import (
    _ler_dataframe_upload,
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
    cadastrar_clientes_ixc,
    download_template_cadastro_cliente_ixc,
)


class CoreAdminViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = Mock()
        self.user.is_authenticated = True
        self.user.is_superuser = True
        self.user.groups.filter.return_value.exists.return_value = False

    @patch("apps.core_admin.views.render")
    @patch("apps.core_admin.views._buscar_ultima_resolucao_os_atendimento")
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
    @patch("apps.core_admin.views.executar_resolucao_os_atendimento_ixc")
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

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.registrar_auditoria_integracao")
    @patch("apps.core_admin.views.executar_resolucao_os_atendimento_ixc")
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

    @patch("apps.core_admin.views._ler_dataframe_upload")
    @patch("apps.core_admin.views.executar_resolucao_os_atendimento_ixc")
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

    @patch("apps.backoffice.views._ler_dataframe_upload")
    @patch("apps.backoffice.views.registrar_auditoria_integracao")
    @patch("apps.backoffice.views.executar_cadastro_cliente_ixc")
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

    @patch("core_admin.admin.MySQLdb.connect")
    @patch.dict("os.environ", {"MYSQL_ROOT_PASSWORD": "senha_do_ambiente"}, clear=True)
    def test_aplicar_acesso_usa_senha_da_variavel_de_ambiente(self, mock_connect):
        acesso = self._criar_acesso()

        AcessoBancoDadosAdmin(AcessoBancoDados, admin.site)._aplicar_acesso(acesso)

        mock_connect.assert_called_once()
        self.assertEqual(mock_connect.call_args.kwargs["passwd"], "senha_do_ambiente")
