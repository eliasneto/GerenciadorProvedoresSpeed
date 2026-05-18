import pandas as pd
from django.test import SimpleTestCase
from unittest.mock import Mock, patch

from apps.backoffice.views import serializar_linha_para_auditoria
from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    executar_abertura_atendimento,
    normalizar_id_numerico,
)
from scripts.integracoes.backoffice.cadastrar_cliente_ixc import (
    executar_cadastro_cliente_ixc,
    inferir_tipo_pessoa,
    normalizar_confirmacao_cadastro,
    resolver_cidade_ixc,
)
from scripts.integracoes.backoffice.desativar_atendimento_ixc import (
    executar_desativacao_atendimento,
    listar_os_para_desativacao,
    normalizar_confirmacao_desativacao,
)
from scripts.integracoes.ixc_ticket_arquivo_service import _sessao_painel_ixc


class ValidacaoIdsAtendimentoTests(SimpleTestCase):
    def test_normalizar_id_numerico_aceita_inteiro_excel(self):
        valor, erro = normalizar_id_numerico(4047.0, "Login_ID")

        self.assertEqual(valor, "4047")
        self.assertIsNone(erro)

    def test_normalizar_id_numerico_rejeita_texto(self):
        valor, erro = normalizar_id_numerico("Rua A, 123", "Login_ID")

        self.assertIsNone(valor)
        self.assertIn("apenas o ID numerico do IXC", erro)

    def test_executar_abertura_atendimento_barra_login_id_textual(self):
        status, mensagem = executar_abertura_atendimento(
            {
                "Cliente_ID": 575,
                "Login_ID": "Rua das Flores, 100",
                "Contrato_ID": 27,
                "Filial_ID": 1,
                "Assunto_ID": 18,
                "Departamento_ID": 4,
                "Assunto_Descricao": "Teste",
                "Descricao": "Descricao valida",
            }
        )

        self.assertFalse(status)
        self.assertIn("Login_ID", mensagem)
        self.assertIn("apenas o ID numerico do IXC", mensagem)


class AuditoriaImportacaoBackofficeTests(SimpleTestCase):
    def test_serializar_linha_para_auditoria_preserva_id_ixc_e_status(self):
        df = pd.DataFrame(
            [
                {
                    "Cliente_ID": 575,
                    "Login_Login": "CEF_11_DE_TAGUATINGA",
                    "ID_IXC": "998877",
                    "Status_Importacao": "SUCESSO",
                    "Mensagem_Importacao": "Criado com sucesso!",
                }
            ]
        )

        dados = serializar_linha_para_auditoria(df, 0)

        self.assertEqual(dados["Cliente_ID"], 575)
        self.assertEqual(dados["Login_Login"], "CEF_11_DE_TAGUATINGA")
        self.assertEqual(dados["ID_IXC"], "998877")
        self.assertEqual(dados["Status_Importacao"], "SUCESSO")
        self.assertEqual(dados["Mensagem_Importacao"], "Criado com sucesso!")


class DesativacaoAtendimentoIXCTests(SimpleTestCase):
    def test_confirmacao_desativacao_aceita_sim(self):
        confirmado, erro = normalizar_confirmacao_desativacao("SIM")

        self.assertTrue(confirmado)
        self.assertIsNone(erro)

    def test_executar_desativacao_bloqueia_sem_confirmacao(self):
        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 6385,
                "Confirmar_Desativacao": "NAO",
            }
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "6385")
        self.assertIn("Confirmar_Desativacao", mensagem)

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_finaliza_os_vinculada_e_atendimento(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "status": "OSAB"},
            {"id": "5313", "status": "F"},
        ]
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {
            "ok": True,
            "os_atualizada": {"id": "6394", "status": "F"},
            "registro_fechamento": {"id": "13067"},
        }

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Desativacao": "SIM",
                "Mensagem": "Encerramento administrativo.",
            },
            usuario_sistema=Mock(is_authenticated=True),
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("13067", mensagem)
        mock_listar_os.assert_called_once_with("5313", os_id="")
        mock_finalizar_os.assert_called_once()

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_fecha_todas_as_os_abertas_sem_os_id(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "status": "OSAB"},
            {"id": "5313", "status": "F"},
        ]
        mock_listar_os.return_value = [
            {"id": "6394", "status": "A"},
            {"id": "6401", "status": "A"},
        ]
        mock_finalizar_os.side_effect = [
            {
                "ok": True,
                "os_atualizada": {"id": "6394", "status": "F"},
                "registro_fechamento": {"id": "13067"},
            },
            {
                "ok": True,
                "os_atualizada": {"id": "6401", "status": "F"},
                "registro_fechamento": {"id": "13068"},
            },
        ]

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("6394, 6401", mensagem)
        self.assertEqual(mock_finalizar_os.call_count, 2)
        self.assertFalse(mock_finalizar_os.call_args_list[0].kwargs["finaliza_atendimento"])
        self.assertTrue(mock_finalizar_os.call_args_list[1].kwargs["finaliza_atendimento"])

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_retorna_sucesso_quando_atendimento_ja_finalizado(
        self,
        mock_buscar_atendimento,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "F"}

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("ja esta finalizado", mensagem)

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_informa_quando_nao_encontra_os(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "OSAB"}
        mock_listar_os.return_value = []

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("nao possui O.S. aberta", mensagem)

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_bloqueia_os_manual_de_outro_atendimento(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "OSAB"}
        mock_listar_os.return_value = [{"id": "6394", "id_ticket": "9999", "status": "A"}]

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "OS_ID": 6394,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("9999", mensagem)
        mock_finalizar_os.assert_not_called()

    @patch("scripts.integracoes.backoffice.desativar_atendimento_ixc.buscar_os_atendimento_ixc")
    def test_listar_os_para_desativacao_retorna_apenas_os_abertas_ordenadas(self, mock_buscar_os):
        mock_buscar_os.return_value = [
            {"id": "6401", "status": "A"},
            {"id": "6394", "status": "F"},
            {"id": "6399", "status": "AG"},
        ]

        registros = listar_os_para_desativacao("5313")

        self.assertEqual([registro["id"] for registro in registros], ["6399", "6401"])


class CadastroClienteIXCTests(SimpleTestCase):
    def test_confirmacao_cadastro_aceita_sim(self):
        confirmado, erro = normalizar_confirmacao_cadastro("SIM")

        self.assertTrue(confirmado)
        self.assertIsNone(erro)

    def test_inferir_tipo_pessoa_por_documento(self):
        self.assertEqual(inferir_tipo_pessoa("123.456.789-01"), "F")
        self.assertEqual(inferir_tipo_pessoa("12.345.678/0001-99"), "J")

    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc._listar_registros")
    def test_resolver_cidade_ixc_valida_id_existente(self, mock_listar):
        mock_listar.side_effect = [
            [{"id": "887", "cidade": "FORTALEZA", "uf": "CE"}],
        ]

        cidade_id, erro = resolver_cidade_ixc("887")

        self.assertEqual(cidade_id, "887")
        self.assertIsNone(erro)

    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.resolver_cidade_ixc")
    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    def test_executar_cadastro_retorna_sucesso_quando_cliente_ja_existe(
        self,
        mock_buscar_cliente,
        mock_resolver_cidade,
    ):
        mock_resolver_cidade.return_value = ("887", None)
        mock_buscar_cliente.return_value = {"id": "4455", "razao": "CLIENTE TESTE"}

        status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(
            {
                "Razao_Social": "CLIENTE TESTE",
                "CNPJ_CPF": "12.345.678/0001-99",
                "Cidade_ID_IXC": 887,
                "Confirmar_Cadastro": "SIM",
            }
        )

        self.assertTrue(status)
        self.assertEqual(cliente_ixc_id, "4455")
        self.assertIn("ja existente", mensagem)

    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.buscar_cliente_por_razao_social")
    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.IXCClient")
    @patch("scripts.integracoes.backoffice.cadastrar_cliente_ixc.resolver_cidade_ixc")
    def test_executar_cadastro_cria_cliente_com_payload_esperado(
        self,
        mock_resolver_cidade,
        mock_ixc_client_cls,
        mock_buscar_cliente,
        mock_buscar_razao,
    ):
        mock_resolver_cidade.return_value = ("887", None)
        mock_buscar_cliente.side_effect = [{}, {}]
        mock_buscar_razao.return_value = {}
        client = Mock()
        client.escrever.return_value = (200, {"type": "success", "id": "9988"})
        mock_ixc_client_cls.return_value = client

        status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(
            {
                "Razao_Social": "CLIENTE TESTE LTDA",
                "CNPJ_CPF": "12.345.678/0001-99",
                "Nome_Fantasia": "CLIENTE TESTE",
                "CEP": "60000-000",
                "Endereco": "RUA A",
                "Numero": "100",
                "Bairro": "CENTRO",
                "Cidade_ID_IXC": "887",
                "Telefone": "(85) 99999-9999",
                "Email": "teste@exemplo.com",
                "Confirmar_Cadastro": "SIM",
            }
        )

        self.assertTrue(status)
        self.assertEqual(cliente_ixc_id, "9988")
        self.assertIn("cadastrado com sucesso", mensagem)
        payload = client.escrever.call_args.args[1]
        self.assertEqual(client.escrever.call_args.args[0], "cliente")
        self.assertEqual(payload["tipo_pessoa"], "J")
        self.assertEqual(payload["cidade"], "887")
        self.assertEqual(payload["cnpj_cpf"], "12.345.678/0001-99")

    def test_executar_cadastro_bloqueia_sem_confirmacao(self):
        status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(
            {
                "Razao_Social": "CLIENTE TESTE",
                "CNPJ_CPF": "12.345.678/0001-99",
                "Cidade_ID_IXC": 887,
                "Confirmar_Cadastro": "NAO",
            }
        )

        self.assertFalse(status)
        self.assertEqual(cliente_ixc_id, "")
        self.assertIn("Confirmar_Cadastro", mensagem)


class SessaoPainelIXCTests(SimpleTestCase):
    @patch("scripts.integracoes.ixc_ticket_arquivo_service.requests.Session")
    @patch("scripts.integracoes.ixc_ticket_arquivo_service.IXCClient")
    def test_sessao_painel_ixc_executa_login_em_duas_etapas_antes_do_adm(
        self,
        mock_ixc_client,
        mock_session_cls,
    ):
        client = Mock()
        client.base_url = "https://megainfraestrutura.com.br/webservice/v1"
        client.verify_ssl = True
        client.timeout = 30
        mock_ixc_client.return_value = client

        response_login = Mock(
            status_code=200,
            url="https://megainfraestrutura.com.br/app/login",
            headers={"Set-Cookie": "IXC_Session=abc", "Content-Type": "text/html"},
            text="<title>Login</title>",
            history=[],
        )
        response_email = Mock(
            status_code=200,
            headers={"Content-Type": "application/json"},
            text='{"protocol":"0.0.1","status":"1","data":{"type":"password"}}',
        )
        response_email.json.return_value = {
            "protocol": "0.0.1",
            "status": "1",
            "data": {"type": "password", "email": "elias.neto@speedcsc.com.br"},
        }
        response_password = Mock(
            status_code=200,
            headers={"Content-Type": "application/json"},
            text='{"protocol":"0.0.1","status":"1","goto":{"local":"/adm.php"},"data":{"type":"redirect"}}',
        )
        response_password.json.return_value = {
            "protocol": "0.0.1",
            "status": "1",
            "goto": {"local": "/adm.php"},
            "data": {"type": "redirect"},
        }
        response_adm = Mock(
            status_code=200,
            url="https://megainfraestrutura.com.br/adm.php",
            headers={"Content-Type": "text/html"},
            text="<!DOCTYPE HTML><html><title>Painel</title></html>",
            history=[],
        )

        session = Mock()
        session.cookies.get_dict.return_value = {
            "IXC_Session": "abc",
            "IXC_VERSAO": "80.93.2",
        }
        session.get.side_effect = [response_login, response_adm]
        session.post.side_effect = [response_email, response_password]
        mock_session_cls.return_value = session

        sessao, auth = _sessao_painel_ixc("elias.neto@speedcsc.com.br", "El1as@2025NETO")

        self.assertIs(sessao, session)
        self.assertTrue(auth["ok"])
        self.assertEqual(auth["pagina_final"], "https://megainfraestrutura.com.br/adm.php")
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(
            session.post.call_args_list[0].kwargs["files"],
            {"email": (None, "elias.neto@speedcsc.com.br")},
        )
        self.assertEqual(
            session.post.call_args_list[1].kwargs["files"],
            {"password": (None, "El1as@2025NETO")},
        )

    @patch("scripts.integracoes.ixc_ticket_arquivo_service.requests.Session")
    @patch("scripts.integracoes.ixc_ticket_arquivo_service.IXCClient")
    def test_sessao_painel_ixc_repete_senha_quando_ixc_indica_sessao_ativa(
        self,
        mock_ixc_client,
        mock_session_cls,
    ):
        client = Mock()
        client.base_url = "https://megainfraestrutura.com.br/webservice/v1"
        client.verify_ssl = True
        client.timeout = 30
        mock_ixc_client.return_value = client

        response_login = Mock(
            status_code=200,
            url="https://megainfraestrutura.com.br/app/login",
            headers={"Set-Cookie": "IXC_Session=abc", "Content-Type": "text/html"},
            text="<title>Login</title>",
            history=[],
        )
        response_email = Mock(status_code=200, headers={"Content-Type": "application/json"})
        response_email.json.return_value = {
            "protocol": "0.0.1",
            "status": "1",
            "data": {"type": "password", "email": "elias.neto@speedcsc.com.br"},
        }
        response_password_1 = Mock(status_code=200, headers={"Content-Type": "application/json"})
        response_password_1.json.return_value = {
            "protocol": "0.0.1",
            "status": "0",
            "messages": [
                {"type": "error", "body": "Ja existe uma sessao ativa, tente novamente para acessar!"}
            ],
        }
        response_password_2 = Mock(status_code=200, headers={"Content-Type": "application/json"})
        response_password_2.json.return_value = {
            "protocol": "0.0.1",
            "status": "1",
            "goto": {"local": "/adm.php"},
            "data": {"type": "redirect"},
        }
        response_adm = Mock(
            status_code=200,
            url="https://megainfraestrutura.com.br/adm.php",
            headers={"Content-Type": "text/html"},
            text="<!DOCTYPE HTML><html><title>Painel</title></html>",
            history=[],
        )

        session = Mock()
        session.cookies.get_dict.return_value = {
            "IXC_Session": "abc",
            "IXC_VERSAO": "80.93.2",
        }
        session.get.side_effect = [response_login, response_adm]
        session.post.side_effect = [response_email, response_password_1, response_password_2]
        mock_session_cls.return_value = session

        sessao, auth = _sessao_painel_ixc("elias.neto@speedcsc.com.br", "El1as@2025NETO")

        self.assertIs(sessao, session)
        self.assertTrue(auth["ok"])
        self.assertEqual(session.post.call_count, 3)
        self.assertEqual(
            session.post.call_args_list[1].kwargs["files"],
            {"password": (None, "El1as@2025NETO")},
        )
        self.assertEqual(
            session.post.call_args_list[2].kwargs["files"],
            {"password": (None, "El1as@2025NETO")},
        )
