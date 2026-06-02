import pandas as pd
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from unittest.mock import Mock, patch

from apps.backoffice.views import (
    buscar_execucao_em_andamento,
    construir_abas_relatorio_atendimento,
    contar_registros_atendimento_importaveis,
    obter_limite_registros_atendimento_ixc,
    render_backoffice_automacoes,
    serializar_relatorio_disponivel,
    serializar_execucao_em_andamento,
    serializar_linha_para_auditoria,
)
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
        status, mensagem, id_ixc = executar_abertura_atendimento(
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
        self.assertEqual(id_ixc, "")
        self.assertIn("Login_ID", mensagem)
        self.assertIn("apenas o ID numerico do IXC", mensagem)

    @patch("scripts.integracoes.backoffice.cria_atendimento_ixc.requests.post")
    def test_executar_abertura_atendimento_retorna_id_ticket_criado(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"type":"success","id":"778899"}'
        mock_response.json.return_value = {"type": "success", "id": "778899"}
        mock_post.return_value = mock_response

        status, mensagem, id_ixc = executar_abertura_atendimento(
            {
                "Cliente_ID": 575,
                "Login_ID": 4047,
                "Contrato_ID": 27,
                "Filial_ID": 1,
                "Assunto_ID": 18,
                "Departamento_ID": 4,
                "Assunto_Descricao": "Teste",
                "Descricao": "Descricao valida",
            }
        )

        self.assertTrue(status)
        self.assertEqual(id_ixc, "778899")
        self.assertIn("778899", mensagem)


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

    def test_contar_registros_atendimento_importaveis_ignora_linhas_sem_cliente(self):
        df = pd.DataFrame(
            [
                {"Cliente_ID": 575, "Login_ID": 1},
                {"Cliente_ID": None, "Login_ID": 2},
                {"Cliente_ID": 576, "Login_ID": 3},
            ]
        )

        total = contar_registros_atendimento_importaveis(df)

        self.assertEqual(total, 2)

    def test_obter_limite_registros_atendimento_ixc_ler_env_valido(self):
        with patch.dict("os.environ", {"ATENDIMENTO_IXC_MAX_REGISTROS_POR_PROCESSAMENTO": "250"}):
            self.assertEqual(obter_limite_registros_atendimento_ixc(), 250)

    def test_obter_limite_registros_atendimento_ixc_faz_fallback_para_padrao(self):
        with patch.dict("os.environ", {"ATENDIMENTO_IXC_MAX_REGISTROS_POR_PROCESSAMENTO": "abc"}):
            self.assertEqual(obter_limite_registros_atendimento_ixc(), 1000)

    def test_construir_abas_relatorio_atendimento_separa_criados_erros_e_pendentes(self):
        df = pd.DataFrame(
            [
                {
                    "Cliente_ID": 575,
                    "Login_ID": 1,
                    "Status_Importacao": "SUCESSO",
                    "Mensagem_Importacao": "OK",
                    "ID_IXC": "8001",
                },
                {
                    "Cliente_ID": 576,
                    "Login_ID": 2,
                    "Status_Importacao": "ERRO",
                    "Mensagem_Importacao": "Falha",
                    "ID_IXC": "",
                },
                {
                    "Cliente_ID": 577,
                    "Login_ID": 3,
                    "Status_Importacao": "",
                    "Mensagem_Importacao": "",
                    "ID_IXC": "",
                },
            ]
        )

        abas = construir_abas_relatorio_atendimento(
            df,
            arquivo_nome="lote.xlsx",
            total_registros=3,
            sucessos=1,
            falhas=1,
            limite_registros=1000,
            ultimo_id_ixc="8001",
            ultima_linha_processada=3,
        )

        nomes_abas = [nome for nome, _ in abas]
        self.assertEqual(nomes_abas, ["Resumo", "Criados", "Erros", "Pendentes", "Completo"])
        self.assertEqual(len(dict(abas)["Criados"]), 1)
        self.assertEqual(len(dict(abas)["Erros"]), 1)
        self.assertEqual(len(dict(abas)["Pendentes"]), 1)
        self.assertEqual(dict(abas)["Resumo"].iloc[0]["Valor"], "lote.xlsx")


class BackofficeAutomacoesRenderTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_serializar_execucao_em_andamento_retorna_campos_de_progresso(self):
        audit = Mock()
        audit.id = 99
        audit.arquivo_nome = "lote.xlsx"
        audit.total_registros = 15
        audit.total_sucessos = 12
        audit.total_erros = 3
        audit.criado_em = "2026-05-29T10:00:00"
        audit.detalhes_json = {
            "mensagem": "Criando atendimentos no IXC.",
            "total_previsto": 40,
            "ultima_linha_processada": 20,
            "ultimo_id_ixc_criado": "8123",
        }

        payload = serializar_execucao_em_andamento(audit)

        self.assertEqual(payload["arquivo_nome"], "lote.xlsx")
        self.assertEqual(payload["processadas"], 15)
        self.assertEqual(payload["total_previsto"], 40)
        self.assertEqual(payload["ultimo_id_ixc_criado"], "8123")

    def test_serializar_relatorio_disponivel_retorna_link_e_nome(self):
        audit = Mock()
        audit.id = 55
        audit.arquivo_nome = "lote.xlsx"
        audit.detalhes_json = {
            "relatorio_nome_arquivo": "Relatorio_Importacao_IXC.xlsx",
            "relatorio_gerado_em": "2026-05-29T10:10:00",
        }

        with patch("apps.backoffice.views.reverse", return_value="/backoffice/relatorios/55/download/"):
            payload = serializar_relatorio_disponivel(audit)

        self.assertEqual(payload["relatorio_nome_arquivo"], "Relatorio_Importacao_IXC.xlsx")
        self.assertEqual(payload["url_download"], "/backoffice/relatorios/55/download/")

    @patch("apps.backoffice.views.render")
    @patch("apps.backoffice.views.buscar_relatorio_disponivel")
    @patch("apps.backoffice.views.buscar_execucao_em_andamento")
    def test_render_backoffice_automacoes_envia_status_persistente_para_template(
        self,
        mock_buscar_execucao,
        mock_buscar_relatorio,
        mock_render,
    ):
        audit_logins = Mock()
        audit_logins.id = 1
        audit_logins.arquivo_nome = "logins.xlsx"
        audit_logins.total_registros = 5
        audit_logins.total_sucessos = 4
        audit_logins.total_erros = 1
        audit_logins.criado_em = "2026-05-29T10:00:00"
        audit_logins.detalhes_json = {"mensagem": "Criando logins no IXC.", "total_previsto": 10}

        audit_atendimento = Mock()
        audit_atendimento.id = 2
        audit_atendimento.arquivo_nome = "atendimentos.xlsx"
        audit_atendimento.total_registros = 7
        audit_atendimento.total_sucessos = 7
        audit_atendimento.total_erros = 0
        audit_atendimento.criado_em = "2026-05-29T10:00:00"
        audit_atendimento.detalhes_json = {"mensagem": "Criando atendimentos no IXC.", "total_previsto": 20}

        mock_buscar_execucao.side_effect = [audit_logins, audit_atendimento]
        mock_buscar_relatorio.side_effect = [None, None]
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/backoffice/cotacao/importar/")
        request.user = Mock(is_authenticated=True)

        response = render_backoffice_automacoes(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_render.call_args.args[1], "backoffice/cotacao_import.html")
        contexto = mock_render.call_args.args[2]
        self.assertEqual(contexto["logins_ixc_em_andamento"]["arquivo_nome"], "logins.xlsx")
        self.assertEqual(contexto["atendimento_ixc_em_andamento"]["arquivo_nome"], "atendimentos.xlsx")


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
