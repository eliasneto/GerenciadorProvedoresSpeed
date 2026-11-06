import zipfile
from io import BytesIO

import pandas as pd
from django.test import SimpleTestCase, TestCase
from unittest.mock import Mock, patch

from apps.backoffice.services import serializar_linha_para_auditoria
from apps.integracoes.ixc.services.cria_atendimento_ixc import (
    executar_abertura_atendimento,
    normalizar_id_numerico,
)
from apps.integracoes.ixc.services.cria_login_atendimento import executar_cadastro_ixc
from apps.integracoes.ixc.services.cadastrar_cliente_ixc import (
    detectar_cnpj_duplicado_na_planilha,
    executar_cadastro_cliente_ixc,
    inferir_tipo_pessoa,
    normalizar_confirmacao_cadastro,
    resolver_cidade_ixc,
    verificar_duplicidade_ixc,
)
from apps.integracoes.ixc.services.desativar_atendimento_ixc import (
    buscar_os_atendimento_ixc,
    executar_desativacao_atendimento,
    listar_os_para_desativacao,
    normalizar_confirmacao_desativacao,
)
from apps.integracoes.ixc.services.resolver_os_atendimento_ixc import (
    executar_resolucao_os_atendimento_ixc,
    localizar_anexo_no_zip,
    normalizar_confirmacao_resolucao,
    normalizar_fechar_todas_os,
    normalizar_informar_colaborador,
    normalizar_mais_de_um_anexo,
    normalizar_proxima_tarefa_id,
    normalizar_tem_anexo,
)
from scripts.integracoes.ixc_finalizacao_service import IXCConsultaIndisponivelError
from scripts.integracoes.ixc_ticket_arquivo_service import _sessao_painel_ixc


def _zip_com_pdf(nome_arquivo="comunicado.pdf", conteudo=b"conteudo do pdf"):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo_zip:
        arquivo_zip.writestr(nome_arquivo, conteudo)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_falha_de_comunicacao_nao_diz_nao_encontrado(
        self,
        mock_buscar_atendimento,
    ):
        # Bug corrigido: uma falha ao consultar o IXC (timeout, HTTP != 200) nao
        # pode ser relatada como "atendimento nao encontrado" — sao causas
        # diferentes e a segunda esconde a real (ex.: instabilidade do IXC).
        mock_buscar_atendimento.side_effect = IXCConsultaIndisponivelError(
            "falha ao consultar 'su_ticket' no IXC (HTTP 500)"
        )

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("Nao foi possivel confirmar", mensagem)
        self.assertNotIn("nao encontrado", mensagem)

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_desativacao_atendimento_nao_confirmado_mas_com_os_vinculada(
        self, mock_buscar_atendimento, mock_listar_os
    ):
        # Confirmado em producao (2026-08-28): a API do IXC pode nao retornar um
        # atendimento que existe e esta ativo no painel. A mensagem nao pode afirmar
        # que o atendimento "nao existe mais" — so que nao foi possivel confirmar via
        # API, mantendo o usuario ciente da O.S. ainda vinculada.
        mock_buscar_atendimento.return_value = {}
        mock_listar_os.return_value = [{"id": "6408", "status": "A"}]

        status, mensagem, atendimento_id = executar_desativacao_atendimento(
            {
                "Atendimento_ID": 5327,
                "Confirmar_Desativacao": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5327")
        self.assertIn("Nao foi possivel confirmar", mensagem)
        self.assertIn("6408", mensagem)
        self.assertNotIn("nao existe mais", mensagem)
        self.assertNotIn("removido", mensagem)

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_atendimento_ixc_por_id")
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

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc.buscar_os_atendimento_ixc")
    def test_listar_os_para_desativacao_retorna_apenas_os_abertas_ordenadas(self, mock_buscar_os):
        mock_buscar_os.return_value = [
            {"id": "6401", "status": "A"},
            {"id": "6394", "status": "F"},
            {"id": "6399", "status": "AG"},
        ]

        registros = listar_os_para_desativacao("5313")

        self.assertEqual([registro["id"] for registro in registros], ["6399", "6401"])

    def test_qtypes_os_atendimento_mantem_apenas_o_valor_valido(self):
        # Bug corrigido (producao, execucoes de 28/08 e 10/09 com 203/203 erros):
        # "id_atendimento", "id_su_ticket" e "id_chamado" nao sao qtypes validos
        # para su_oss_chamado no IXC (confirmado ao vivo) e nao devem voltar aqui.
        from apps.integracoes.ixc.services.desativar_atendimento_ixc import (
            QTYPES_OS_ATENDIMENTO,
        )

        self.assertEqual(QTYPES_OS_ATENDIMENTO, ("id_ticket",))

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc._listar_registros")
    def test_buscar_os_atendimento_ignora_qtype_invalido_sem_abortar_busca(
        self, mock_listar_registros
    ):
        # Reproduz o bug real: um qtype invalido no meio do laco (IXC responde
        # HTML em vez de JSON) nao pode abortar a busca inteira quando outro
        # qtype ja encontrou a O.S. certa.
        def _listar_registros_fake(endpoint, qtype, query, limite="10"):
            if qtype == "id_ticket":
                return [{"id": "6401", "status": "A"}]
            raise IXCConsultaIndisponivelError(
                f"falha ao consultar '{endpoint}' no IXC (HTTP 200)"
            )

        mock_listar_registros.side_effect = _listar_registros_fake

        with patch(
            "apps.integracoes.ixc.services.desativar_atendimento_ixc.QTYPES_OS_ATENDIMENTO",
            ("id_ticket", "id_qtype_invalido"),
        ):
            registros = buscar_os_atendimento_ixc("5313")

        self.assertEqual([registro["id"] for registro in registros], ["6401"])

    @patch("apps.integracoes.ixc.services.desativar_atendimento_ixc._listar_registros")
    def test_buscar_os_atendimento_propaga_falha_quando_nenhum_qtype_confirma(
        self, mock_listar_registros
    ):
        # RN-072 continua valida: se nenhum qtype conseguir confirmar (todos
        # falham), a falha de comunicacao deve ser propagada, nunca tratada
        # silenciosamente como "nenhuma O.S. encontrada".
        mock_listar_registros.side_effect = IXCConsultaIndisponivelError(
            "falha ao consultar 'su_oss_chamado' no IXC (HTTP 500)"
        )

        with self.assertRaises(IXCConsultaIndisponivelError):
            buscar_os_atendimento_ixc("5313")


class ResolucaoOsAtendimentoIXCTests(SimpleTestCase):
    def test_confirmacao_resolucao_aceita_sim(self):
        confirmado, erro = normalizar_confirmacao_resolucao("SIM")

        self.assertTrue(confirmado)
        self.assertIsNone(erro)

    def test_executar_resolucao_bloqueia_sem_confirmacao(self):
        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {"Atendimento_ID": 6385, "Confirmar_Resolucao": "NAO"},
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "6385")
        self.assertEqual(os_fechadas, "")
        self.assertIn("Confirmar_Resolucao", mensagem)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_bloqueia_atendimento_nao_encontrado(
        self, mock_buscar_atendimento, mock_listar_os
    ):
        mock_buscar_atendimento.return_value = {}
        mock_listar_os.return_value = []

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "")
        self.assertIn("nao encontrado", mensagem)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_atendimento_nao_confirmado_mas_com_os_vinculada(
        self, mock_buscar_atendimento, mock_listar_os
    ):
        # Confirmado em producao (2026-08-28): a API do IXC pode nao retornar um
        # atendimento que existe e esta ativo no painel. Nesse caso a mensagem nao
        # pode afirmar que o atendimento "nao existe mais" — so que nao foi possivel
        # confirmar via API, mantendo o usuario ciente da O.S. ainda vinculada.
        mock_buscar_atendimento.return_value = {}
        mock_listar_os.return_value = [{"id": "6408", "status": "A"}]

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5327,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5327")
        self.assertEqual(os_fechadas, "")
        self.assertIn("Nao foi possivel confirmar", mensagem)
        self.assertIn("6408", mensagem)
        self.assertNotIn("nao existe mais", mensagem)
        self.assertNotIn("removido", mensagem)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.localizar_anexo_no_zip")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_nao_fecha_os_quando_anexo_falha(
        self,
        mock_buscar_atendimento,
        mock_localizar_anexo,
        mock_anexar,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_localizar_anexo.return_value = (b"conteudo", "contrato.pdf", None)
        mock_anexar.return_value = {"ok": False, "message": "Falha ao enviar o anexo."}

        with patch(
            "apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente"
        ) as mock_finalizar_os:
            status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
                {
                    "Atendimento_ID": 5313,
                    "Confirmar_Resolucao": "SIM",
                    "Tem_Anexo": "SIM",
                    "Nome_Anexo": "contrato.pdf",
                    "Fechar_Todas_OS": "SIM",
                },
                zip_arquivos=Mock(),
            )

            mock_finalizar_os.assert_not_called()

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "")
        self.assertIn("Nao foi possivel anexar", mensagem)
        self.assertIn("Nenhuma O.S. foi fechada", mensagem)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_fecha_todas_as_os_sem_finalizar_atendimento(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.side_effect = [
            [
                {"id": "6394", "status": "A"},
                {"id": "6401", "status": "A"},
            ],
            [],
        ]
        mock_finalizar_os.side_effect = [
            {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}},
            {"ok": True, "os_atualizada": {"id": "6401", "status": "F"}},
        ]

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "6394, 6401")
        self.assertEqual(mock_finalizar_os.call_count, 2)
        self.assertFalse(mock_finalizar_os.call_args_list[0].kwargs["finaliza_atendimento"])
        self.assertFalse(mock_finalizar_os.call_args_list[1].kwargs["finaliza_atendimento"])
        self.assertNotIn("Atencao", mensagem)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_mantem_os_ja_fechadas_quando_uma_falha(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = [
            {"id": "6394", "status": "A"},
            {"id": "6401", "status": "A"},
        ]
        mock_finalizar_os.side_effect = [
            {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}},
            {"ok": False, "message": "IXC recusou o fechamento.", "body": {}},
        ]

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "6394")
        self.assertIn("6394", mensagem)
        self.assertIn("6401", mensagem)
        mock_buscar_atendimento.assert_called_once()

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_informa_quando_nao_ha_os_aberta(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = []

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "")
        self.assertIn("nao possui O.S. aberta", mensagem)

    def test_normalizar_proxima_tarefa_id_aceita_vazio(self):
        valor, erro = normalizar_proxima_tarefa_id("")

        self.assertEqual(valor, "")
        self.assertIsNone(erro)

    def test_normalizar_proxima_tarefa_id_rejeita_texto(self):
        valor, erro = normalizar_proxima_tarefa_id("Realizar Implantacao")

        self.assertIsNone(valor)
        self.assertIn("Proxima_Tarefa_ID", erro)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_informa_proxima_tarefa_quando_preenchida(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Proxima_Tarefa_ID": 147,
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394")
        self.assertEqual(mock_finalizar_os.call_args.kwargs["id_proxima_tarefa"], "147")

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_sem_proxima_tarefa_mantem_padrao(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}

        executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
            },
            zip_arquivos=None,
        )

        self.assertIsNone(mock_finalizar_os.call_args.kwargs["id_proxima_tarefa"])

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_com_fechar_todas_os_aplica_proxima_tarefa_so_na_primeira_os(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
    ):
        """RN-070: a automacao nao pode se impor sobre O.S. que o workflow do IXC
        abrir depois (ex.: bifurcacao em O.S. de mais de um setor) reaproveitando o
        Proxima_Tarefa_ID informado para a O.S. atual."""
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.side_effect = [
            [
                {"id": "6394", "status": "A"},
                {"id": "6401", "status": "A"},
            ],
            [],
        ]
        mock_finalizar_os.side_effect = [
            {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}},
            {"ok": True, "os_atualizada": {"id": "6401", "status": "F"}},
        ]

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
                "Proxima_Tarefa_ID": 147,
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394, 6401")
        self.assertEqual(mock_finalizar_os.call_args_list[0].kwargs["id_proxima_tarefa"], "147")
        self.assertIsNone(mock_finalizar_os.call_args_list[1].kwargs["id_proxima_tarefa"])

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.resolver_proxima_tarefa_automatica")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_resolve_proxima_tarefa_automaticamente_por_os(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
        mock_resolver_automatico,
    ):
        """RN-071: sem Proxima_Tarefa_ID na planilha, cada O.S. tem sua propria
        tarefa resolvida sozinha a partir do workflow do IXC — o usuario nao
        precisa descobrir nenhum ID manualmente."""
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.side_effect = [
            [
                {"id": "6394", "status": "A", "id_wfl_tarefa": "150"},
                {"id": "6401", "status": "A", "id_wfl_tarefa": "148"},
            ],
            [],
        ]
        mock_resolver_automatico.side_effect = [("148", None), (None, None)]
        mock_finalizar_os.side_effect = [
            {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}},
            {"ok": True, "os_atualizada": {"id": "6401", "status": "F"}},
        ]

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394, 6401")
        self.assertEqual(mock_finalizar_os.call_args_list[0].kwargs["id_proxima_tarefa"], "148")
        self.assertIsNone(mock_finalizar_os.call_args_list[1].kwargs["id_proxima_tarefa"])
        mock_resolver_automatico.assert_any_call("150")
        mock_resolver_automatico.assert_any_call("148")

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.resolver_proxima_tarefa_automatica")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_bloqueia_quando_proxima_tarefa_e_ambigua(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
        mock_resolver_automatico,
    ):
        """RN-071: se o sistema nao consegue resolver sozinho a proxima tarefa
        (decisao real de negocio, ainda sem mapeamento confirmado), a O.S. nao e
        tocada e o erro explica as opcoes em vez de adivinhar."""
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = [{"id": "6394", "status": "A", "id_wfl_tarefa": "146"}]
        mock_resolver_automatico.return_value = (
            None,
            "a tarefa atual 'Realizar Contratacao' (ID 146) exige escolher a proxima tarefa "
            "entre mais de uma opcao. Opcoes encontradas no IXC: 147 (Realizar Implantacao), "
            "150 (Realizar Implantacao EACE). Informe Proxima_Tarefa_ID na planilha.",
        )

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(os_fechadas, "")
        self.assertIn("6394", mensagem)
        self.assertIn("Opcoes encontradas no IXC", mensagem)
        mock_finalizar_os.assert_not_called()

    def test_executar_resolucao_bloqueia_proxima_tarefa_invalida(self):
        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Proxima_Tarefa_ID": "Realizar Implantacao",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(os_fechadas, "")
        self.assertIn("Proxima_Tarefa_ID", mensagem)

    def test_normalizar_mais_de_um_anexo_aceita_vazio_como_nao(self):
        valor, erro = normalizar_mais_de_um_anexo("")

        self.assertFalse(valor)
        self.assertIsNone(erro)

    def test_normalizar_mais_de_um_anexo_aceita_sim(self):
        valor, erro = normalizar_mais_de_um_anexo("SIM")

        self.assertTrue(valor)
        self.assertIsNone(erro)

    def test_normalizar_mais_de_um_anexo_rejeita_valor_invalido(self):
        valor, erro = normalizar_mais_de_um_anexo("TALVEZ")

        self.assertIsNone(valor)
        self.assertIn("Mais_de_um_anexo", erro)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.localizar_anexo_no_zip")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_anexa_multiplos_arquivos_quando_mais_de_um_anexo_sim(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
        mock_localizar_anexo,
        mock_anexar,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}
        mock_localizar_anexo.return_value = (b"conteudo", "arquivo.pdf", None)
        mock_anexar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "SIM",
                "Nome_Anexo": "contrato.pdf",
                "Mais_de_um_anexo": "SIM",
                "Nome_Anexo_2": "aditivo1.pdf",
                "Nome_Anexo_3": "aditivo2.pdf",
                "Fechar_Todas_OS": "NAO",
            },
            zip_arquivos=Mock(),
        )

        self.assertTrue(status)
        self.assertEqual(mock_localizar_anexo.call_count, 3)
        self.assertEqual(mock_anexar.call_count, 3)
        nomes_chamados = [chamada.args[1] for chamada in mock_localizar_anexo.call_args_list]
        self.assertEqual(nomes_chamados, ["contrato.pdf", "aditivo1.pdf", "aditivo2.pdf"])

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.localizar_anexo_no_zip")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_ignora_nome_anexo_extra_quando_mais_de_um_anexo_nao(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
        mock_finalizar_os,
        mock_localizar_anexo,
        mock_anexar,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}
        mock_localizar_anexo.return_value = (b"conteudo", "contrato.pdf", None)
        mock_anexar.return_value = {"ok": True}

        executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "SIM",
                "Nome_Anexo": "contrato.pdf",
                "Mais_de_um_anexo": "NAO",
                "Nome_Anexo_2": "aditivo1.pdf",
                "Fechar_Todas_OS": "NAO",
            },
            zip_arquivos=Mock(),
        )

        self.assertEqual(mock_localizar_anexo.call_count, 1)
        self.assertEqual(mock_localizar_anexo.call_args.args[1], "contrato.pdf")

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.localizar_anexo_no_zip")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_para_no_primeiro_anexo_que_falhar_entre_multiplos(
        self,
        mock_buscar_atendimento,
        mock_localizar_anexo,
        mock_anexar,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_localizar_anexo.side_effect = [
            (b"conteudo", "contrato.pdf", None),
            (None, None, "Nenhum arquivo chamado 'aditivo1.pdf' foi encontrado no ZIP de anexos."),
        ]
        mock_anexar.return_value = {"ok": True}

        with patch(
            "apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente"
        ) as mock_finalizar_os:
            status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
                {
                    "Atendimento_ID": 5313,
                    "Confirmar_Resolucao": "SIM",
                    "Tem_Anexo": "SIM",
                    "Nome_Anexo": "contrato.pdf",
                    "Mais_de_um_anexo": "SIM",
                    "Nome_Anexo_2": "aditivo1.pdf",
                    "Fechar_Todas_OS": "SIM",
                },
                zip_arquivos=Mock(),
            )

            mock_finalizar_os.assert_not_called()

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "")
        self.assertIn("aditivo1.pdf", mensagem)
        self.assertEqual(mock_anexar.call_count, 1)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_nao_valida_mais_de_um_anexo_quando_tem_anexo_nao(
        self,
        mock_buscar_atendimento,
        mock_listar_os,
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "su_status": "EP"}
        mock_listar_os.return_value = []

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Mais_de_um_anexo": "TALVEZ",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)

    def test_normalizar_informar_colaborador_aceita_vazio_como_nao(self):
        valor, erro = normalizar_informar_colaborador("")

        self.assertFalse(valor)
        self.assertIsNone(erro)

    def test_normalizar_informar_colaborador_aceita_sim(self):
        valor, erro = normalizar_informar_colaborador("SIM")

        self.assertTrue(valor)
        self.assertIsNone(erro)

    def test_normalizar_informar_colaborador_rejeita_valor_invalido(self):
        valor, erro = normalizar_informar_colaborador("TALVEZ")

        self.assertIsNone(valor)
        self.assertIn("Informar_Colaborador", erro)

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_bloqueia_quando_informar_colaborador_sem_email(
        self,
        mock_buscar_atendimento,
    ):
        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Informar_Colaborador": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertIn("Email_Colaborador", mensagem)
        mock_buscar_atendimento.assert_not_called()

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.resolver_usuario_ixc_por_email")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_bloqueia_email_colaborador_nao_encontrado_no_ixc(
        self,
        mock_buscar_atendimento,
        mock_resolver_email,
    ):
        mock_resolver_email.return_value = {"fallback": True, "usuario_ixc_id": "76", "tecnico_ixc_id": "84"}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Informar_Colaborador": "SIM",
                "Email_Colaborador": "fulano@exemplo.com",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertIn("fulano@exemplo.com", mensagem)
        mock_buscar_atendimento.assert_not_called()

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.resolver_usuario_ixc_por_email")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_usa_email_colaborador_informado(
        self,
        mock_buscar_atendimento,
        mock_resolver_email,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_resolver_email.return_value = {"fallback": False, "usuario_ixc_id": "99", "tecnico_ixc_id": "88"}
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Informar_Colaborador": "SIM",
                "Email_Colaborador": "fulano@exemplo.com",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(mock_finalizar_os.call_args.kwargs["email_ixc"], "fulano@exemplo.com")

    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.resolver_usuario_ixc_por_email")
    @patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
    def test_executar_resolucao_ignora_email_colaborador_quando_informar_colaborador_nao(
        self,
        mock_buscar_atendimento,
        mock_resolver_email,
        mock_listar_os,
        mock_finalizar_os,
    ):
        mock_buscar_atendimento.side_effect = [
            {"id": "5313", "su_status": "EP"},
            {"id": "5313", "status": "A"},
        ]
        mock_listar_os.return_value = [{"id": "6394", "status": "A"}]
        mock_finalizar_os.return_value = {"ok": True, "os_atualizada": {"id": "6394", "status": "F"}}

        executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
                "Informar_Colaborador": "NAO",
                "Email_Colaborador": "fulano@exemplo.com",
            },
            zip_arquivos=None,
        )

        mock_resolver_email.assert_not_called()
        self.assertIsNone(mock_finalizar_os.call_args.kwargs["email_ixc"])


class CadastroClienteIXCTests(SimpleTestCase):
    def test_confirmacao_cadastro_aceita_sim(self):
        confirmado, erro = normalizar_confirmacao_cadastro("SIM")

        self.assertTrue(confirmado)
        self.assertIsNone(erro)

    def test_inferir_tipo_pessoa_por_documento(self):
        self.assertEqual(inferir_tipo_pessoa("123.456.789-01"), "F")
        self.assertEqual(inferir_tipo_pessoa("12.345.678/0001-99"), "J")

    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc._listar_registros")
    def test_resolver_cidade_ixc_valida_id_existente(self, mock_listar):
        mock_listar.side_effect = [
            [{"id": "887", "cidade": "FORTALEZA", "uf": "CE"}],
        ]

        cidade_id, uf_id, erro = resolver_cidade_ixc("887")

        self.assertEqual(cidade_id, "887")
        self.assertEqual(uf_id, "CE")
        self.assertIsNone(erro)

    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.resolver_cidade_ixc")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    def test_executar_cadastro_bloqueia_quando_cliente_ja_existe(
        self,
        mock_buscar_cliente,
        mock_resolver_cidade,
    ):
        mock_resolver_cidade.return_value = ("887", "CE", None)
        mock_buscar_cliente.return_value = {"id": "4455", "razao": "CLIENTE TESTE"}

        status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(
            {
                "Razao_Social": "CLIENTE TESTE",
                "CNPJ_CPF": "12.345.678/0001-99",
                "Cidade_ID_IXC": 887,
                "Confirmar_Cadastro": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(cliente_ixc_id, "4455")
        self.assertIn("ja existente", mensagem)
        self.assertIn("CNPJ/CPF", mensagem)
        self.assertIn("12.345.678/0001-99", mensagem)

    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.resolver_cidade_ixc")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_razao_social")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    def test_executar_cadastro_bloqueia_por_razao_social_quando_cnpj_nao_bate(
        self,
        mock_buscar_cnpj,
        mock_buscar_razao,
        mock_resolver_cidade,
    ):
        mock_resolver_cidade.return_value = ("887", "CE", None)
        mock_buscar_cnpj.return_value = {}
        mock_buscar_razao.return_value = {"id": "7788", "razao": "CLIENTE TESTE"}

        status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(
            {
                "Razao_Social": "CLIENTE TESTE",
                "CNPJ_CPF": "12.345.678/0001-99",
                "Cidade_ID_IXC": 887,
                "Confirmar_Cadastro": "SIM",
            }
        )

        self.assertFalse(status)
        self.assertEqual(cliente_ixc_id, "7788")
        self.assertIn("razao social", mensagem)
        self.assertIn("CLIENTE TESTE", mensagem)

    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_razao_social")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.IXCClient")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.resolver_cidade_ixc")
    def test_executar_cadastro_cria_cliente_com_payload_esperado(
        self,
        mock_resolver_cidade,
        mock_ixc_client_cls,
        mock_buscar_cliente,
        mock_buscar_razao,
    ):
        mock_resolver_cidade.return_value = ("887", "CE", None)
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
                "Tipo_Cliente_ID": "8",
                "Tipo_Assinante_ID": "3",
                "Filial_ID": "1",
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

    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_razao_social")
    @patch("apps.integracoes.ixc.services.cadastrar_cliente_ixc.buscar_cliente_por_cnpj_cpf")
    def test_verificar_duplicidade_ixc_retorna_none_quando_nao_encontra(
        self, mock_buscar_cnpj, mock_buscar_razao
    ):
        mock_buscar_cnpj.return_value = {}
        mock_buscar_razao.return_value = {}

        resultado = verificar_duplicidade_ixc("CLIENTE TESTE", "12345678000199")

        self.assertIsNone(resultado)

    def test_detectar_cnpj_duplicado_na_planilha_sinaliza_linhas_repetidas(self):
        linhas = [
            {"Razao_Social": "ESCOLA A", "CNPJ_CPF": "11.222.333/0001-81"},
            {"Razao_Social": "ESCOLA B", "CNPJ_CPF": "11.222.333/0001-81"},
            {"Razao_Social": "ESCOLA C", "CNPJ_CPF": "99.888.777/0001-11"},
        ]

        erros = detectar_cnpj_duplicado_na_planilha(linhas)

        self.assertEqual(set(erros.keys()), {0, 1})
        self.assertIn("linha(s) 3", erros[0])
        self.assertIn("linha(s) 2", erros[1])

    def test_detectar_cnpj_duplicado_na_planilha_respeita_permitir_duplicidade(self):
        linhas = [
            {"Razao_Social": "ESCOLA A", "CNPJ_CPF": "11.222.333/0001-81", "Permitir_Duplicidade": "SIM"},
            {"Razao_Social": "ESCOLA B", "CNPJ_CPF": "11.222.333/0001-81"},
        ]

        erros = detectar_cnpj_duplicado_na_planilha(linhas)

        self.assertEqual(set(erros.keys()), {1})


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


class NormalizarTemAnexoTests(SimpleTestCase):
    def test_aceita_variacoes_de_sim(self):
        for valor in ("SIM", "sim", "S", "1", "true"):
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_tem_anexo(valor), (True, None))

    def test_aceita_variacoes_de_nao(self):
        for valor in ("NAO", "não", "N", "0", "false"):
            with self.subTest(valor=valor):
                self.assertEqual(normalizar_tem_anexo(valor), (False, None))

    def test_rejeita_valor_vazio_ou_invalido(self):
        tem_anexo, erro = normalizar_tem_anexo("talvez")
        self.assertIsNone(tem_anexo)
        self.assertIn("SIM ou NAO", erro)


class NormalizarFecharTodasOsTests(SimpleTestCase):
    def test_aceita_variacoes_de_sim_e_nao(self):
        self.assertEqual(normalizar_fechar_todas_os("SIM"), (True, None))
        self.assertEqual(normalizar_fechar_todas_os("NAO"), (False, None))

    def test_rejeita_valor_vazio_ou_invalido(self):
        fechar_todas_os, erro = normalizar_fechar_todas_os("")
        self.assertIsNone(fechar_todas_os)
        self.assertIn("Fechar_Todas_OS", erro)


class LocalizarAnexoNoZipTests(SimpleTestCase):
    def test_localiza_arquivo_por_nome_ignorando_caixa(self):
        zip_arquivos = _zip_com_pdf("Comunicado_Cliente.PDF")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "comunicado_cliente.pdf")
        self.assertIsNone(erro)
        self.assertEqual(nome_real, "Comunicado_Cliente.PDF")
        self.assertEqual(conteudo, b"conteudo do pdf")

    def test_erro_quando_nome_nao_existe_no_zip(self):
        zip_arquivos = _zip_com_pdf("comunicado.pdf")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "outro.pdf")
        self.assertIsNone(conteudo)
        self.assertIn("Nenhum arquivo chamado", erro)

    def test_erro_quando_arquivo_nao_e_formato_aceito(self):
        zip_arquivos = _zip_com_pdf("comunicado.zip")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "comunicado.zip")
        self.assertIsNone(conteudo)
        self.assertIn("nao e um formato aceito", erro)

    def test_aceita_planilha_excel_xlsx(self):
        zip_arquivos = _zip_com_pdf("proposta.xlsx", conteudo=b"conteudo do excel")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "proposta.xlsx")
        self.assertIsNone(erro)
        self.assertEqual(nome_real, "proposta.xlsx")
        self.assertEqual(conteudo, b"conteudo do excel")

    def test_aceita_documento_word_docx(self):
        zip_arquivos = _zip_com_pdf("PROPOSTA COMERCIAL ELO - HOW BE - BOMBEIROS.docx", conteudo=b"conteudo do word")
        conteudo, nome_real, erro = localizar_anexo_no_zip(
            zip_arquivos, "PROPOSTA COMERCIAL ELO - HOW BE - BOMBEIROS"
        )
        self.assertIsNone(erro)
        self.assertEqual(nome_real, "PROPOSTA COMERCIAL ELO - HOW BE - BOMBEIROS.docx")
        self.assertEqual(conteudo, b"conteudo do word")

    def test_aceita_planilha_csv(self):
        zip_arquivos = _zip_com_pdf("dados.csv", conteudo=b"col1,col2\n1,2")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "dados.csv")
        self.assertIsNone(erro)
        self.assertEqual(nome_real, "dados.csv")
        self.assertEqual(conteudo, b"col1,col2\n1,2")

    def test_localiza_arquivo_quando_nome_anexo_vem_sem_extensao(self):
        zip_arquivos = _zip_com_pdf("PROPOSTA COMERCIAL GIGA+ - HOWBE - BOMBEIROS.pdf")
        conteudo, nome_real, erro = localizar_anexo_no_zip(
            zip_arquivos, "PROPOSTA COMERCIAL GIGA+ - HOWBE - BOMBEIROS"
        )
        self.assertIsNone(erro)
        self.assertEqual(nome_real, "PROPOSTA COMERCIAL GIGA+ - HOWBE - BOMBEIROS.pdf")
        self.assertEqual(conteudo, b"conteudo do pdf")

    def test_erro_quando_nome_sem_extensao_e_ambiguo(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr("proposta.pdf", b"pdf")
            zf.writestr("proposta.xlsx", b"xlsx")
        buffer.seek(0)
        conteudo, nome_real, erro = localizar_anexo_no_zip(zipfile.ZipFile(buffer), "proposta")
        self.assertIsNone(conteudo)
        self.assertIn("Mais de um arquivo", erro)

    def test_erro_quando_nenhum_zip_foi_informado(self):
        conteudo, nome_real, erro = localizar_anexo_no_zip(None, "comunicado.pdf")
        self.assertIsNone(conteudo)
        self.assertIn("Nenhum arquivo ZIP", erro)


@patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.finalizar_os_existente")
@patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.listar_os_para_desativacao")
@patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
@patch("apps.integracoes.ixc.services.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
class ExecutarResolucaoOsAtendimentoIxcTests(SimpleTestCase):
    def test_tem_anexo_nao_fecha_os_sem_anexar(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.side_effect = [[{"id": "6394"}], []]
        mock_finalizar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertEqual(os_fechadas, "6394")
        mock_anexar.assert_not_called()
        mock_finalizar.assert_called_once()

    def test_tem_anexo_sim_localiza_no_zip_e_anexa_antes_de_fechar(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.side_effect = [[{"id": "6394"}], []]
        mock_anexar.return_value = {"ok": True}
        mock_finalizar.return_value = {"ok": True}
        zip_arquivos = _zip_com_pdf("comunicado.pdf")

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "SIM",
                "Fechar_Todas_OS": "SIM",
                "Nome_Anexo": "comunicado.pdf",
            },
            zip_arquivos=zip_arquivos,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394")
        mock_anexar.assert_called_once()
        self.assertEqual(mock_anexar.call_args.args[0], "5313")
        mock_finalizar.assert_called_once()

    def test_tem_anexo_sim_aceita_excel_com_content_type_correto(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.side_effect = [[{"id": "6394"}], []]
        mock_anexar.return_value = {"ok": True}
        mock_finalizar.return_value = {"ok": True}
        zip_arquivos = _zip_com_pdf("proposta.xlsx", conteudo=b"conteudo do excel")

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "SIM",
                "Fechar_Todas_OS": "SIM",
                "Nome_Anexo": "proposta.xlsx",
            },
            zip_arquivos=zip_arquivos,
        )

        self.assertTrue(status)
        mock_anexar.assert_called_once()
        arquivo_enviado = mock_anexar.call_args.args[1]
        self.assertEqual(arquivo_enviado.name, "proposta.xlsx")
        self.assertEqual(
            arquivo_enviado.content_type,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_tem_anexo_sim_sem_nome_no_zip_nao_fecha_nenhuma_os(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        zip_arquivos = _zip_com_pdf("outro_arquivo.pdf")

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "SIM",
                "Fechar_Todas_OS": "SIM",
                "Nome_Anexo": "comunicado.pdf",
            },
            zip_arquivos=zip_arquivos,
        )

        self.assertFalse(status)
        self.assertIn("Nenhum arquivo chamado", mensagem)
        self.assertEqual(os_fechadas, "")
        mock_anexar.assert_not_called()
        mock_listar_os.assert_not_called()
        mock_finalizar.assert_not_called()

    def test_fecha_os_criada_pelo_workflow_apos_fechamento_anterior(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.side_effect = [
            [{"id": "6394"}],
            [{"id": "6395"}],
            [],
        ]
        mock_finalizar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394, 6395")
        self.assertEqual(mock_finalizar.call_count, 2)
        self.assertEqual(mock_listar_os.call_count, 3)

    def test_limite_de_rodadas_atingido_retorna_falha(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.return_value = [{"id": "6394"}]
        mock_finalizar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertIn("limite de 20 rodadas", mensagem)
        self.assertEqual(mock_finalizar.call_count, 20)

    def test_fechar_todas_os_nao_fecha_somente_a_os_atual(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.return_value = [{"id": "6394"}, {"id": "6395"}]
        mock_finalizar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "NAO",
            },
            zip_arquivos=None,
        )

        self.assertTrue(status)
        self.assertEqual(os_fechadas, "6394")
        mock_finalizar.assert_called_once()
        self.assertEqual(mock_finalizar.call_args.args[0], "6394")
        self.assertEqual(mock_listar_os.call_count, 1)

    def test_atendimento_com_status_diferente_de_em_progresso_bloqueia(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "F", "su_status": "S"}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertIn("Em progresso", mensagem)
        self.assertEqual(os_fechadas, "")
        mock_listar_os.assert_not_called()
        mock_finalizar.assert_not_called()
        mock_anexar.assert_not_called()

    def test_falha_de_comunicacao_ao_buscar_atendimento_nao_diz_nao_encontrado(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        # Bug corrigido: uma falha ao consultar o IXC (timeout, HTTP != 200) nao
        # pode ser relatada como "atendimento nao encontrado" — sao causas
        # diferentes e a segunda esconde a real (ex.: instabilidade do IXC).
        mock_buscar_atendimento.side_effect = IXCConsultaIndisponivelError(
            "falha ao consultar 'su_ticket' no IXC (HTTP 500)"
        )

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertEqual(atendimento_id, "5313")
        self.assertIn("Nao foi possivel confirmar", mensagem)
        self.assertNotIn("nao encontrado", mensagem)
        self.assertEqual(os_fechadas, "")
        mock_listar_os.assert_not_called()
        mock_finalizar.assert_not_called()

    def test_falha_de_comunicacao_ao_listar_os_mantem_progresso_parcial(
        self, mock_anexar, mock_buscar_atendimento, mock_listar_os, mock_finalizar
    ):
        mock_buscar_atendimento.return_value = {"id": "5313", "status": "A", "su_status": "EP"}
        mock_listar_os.side_effect = [
            [{"id": "6394"}],
            IXCConsultaIndisponivelError("falha ao consultar 'su_oss_chamado' no IXC (HTTP 503)"),
        ]
        mock_finalizar.return_value = {"ok": True}

        status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
            {
                "Atendimento_ID": 5313,
                "Confirmar_Resolucao": "SIM",
                "Tem_Anexo": "NAO",
                "Fechar_Todas_OS": "SIM",
            },
            zip_arquivos=None,
        )

        self.assertFalse(status)
        self.assertIn("Nao foi possivel confirmar", mensagem)
        self.assertIn("6394", mensagem)
        self.assertEqual(os_fechadas, "6394")


def _dados_abertura_atendimento(**overrides):
    dados = {
        "Cliente_ID": "123",
        "Login_ID": "456",
        "Contrato_ID": "789",
        "Assunto_ID": "10",
        "Filial_ID": "1",
        "Departamento_ID": "5",
        "Assunto_Descricao": "Teste",
        "Descricao": "Descricao de teste",
        "Endereco": "Rua Teste, 100",
        "Workflow_ID": "",
    }
    dados.update(overrides)
    return dados


class ExecutarAberturaAtendimentoTests(SimpleTestCase):
    """PO-025: cria_atendimento_ixc passou a usar IXCClient em vez de HTTP proprio."""

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_sucesso_retorna_id_do_ticket(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            200, {"type": "success", "id": "999"},
        )
        status, mensagem = executar_abertura_atendimento(_dados_abertura_atendimento())
        self.assertTrue(status)
        self.assertIn("999", mensagem)

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_ixc_nega_o_ticket(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            200, {"type": "error", "message": "Cliente invalido"},
        )
        status, mensagem = executar_abertura_atendimento(_dados_abertura_atendimento())
        self.assertFalse(status)
        self.assertIn("Cliente invalido", mensagem)

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_sem_id_retornado(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            200, {"type": "success"},
        )
        status, mensagem = executar_abertura_atendimento(_dados_abertura_atendimento())
        self.assertFalse(status)
        self.assertIn("sem ID retornado", mensagem)

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_erro_401(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            401, {"type": "error", "message": "token invalido"},
        )
        status, mensagem = executar_abertura_atendimento(_dados_abertura_atendimento())
        self.assertFalse(status)
        self.assertIn("401", mensagem)

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_erro_http_generico(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            500, {"message": "Erro interno"},
        )
        status, mensagem = executar_abertura_atendimento(_dados_abertura_atendimento())
        self.assertFalse(status)
        self.assertIn("500", mensagem)

    @patch("apps.integracoes.ixc.services.cria_atendimento_ixc.IXCClient")
    def test_campo_obrigatorio_ausente_nao_chama_ixc(self, mock_ixc_client_cls):
        status, mensagem = executar_abertura_atendimento(
            _dados_abertura_atendimento(Cliente_ID="")
        )
        self.assertFalse(status)
        mock_ixc_client_cls.return_value.escrever.assert_not_called()


class ExecutarCadastroIxcTests(TestCase):
    """PO-025: cria_login_atendimento passou a usar IXCClient em vez de HTTP proprio."""

    def _dados_login(self, **overrides):
        dados = {
            "Cliente_ID": "123",
            "Login_Contrato_ID": "789",
            "Plano_ID": "55",
            "Login_Login": "cliente.teste",
            "Login_Senha_Cliente": "segredo123",
            "End_CEP": "60000000",
            "End_Bairro": "Centro",
            "End_Cidade_ID_IXC": "",
            "End_Logradouro": "Rua Teste",
            "End_Numero": "100",
            "End_Referencia": "",
            "Obs_Cliente": "",
        }
        dados.update(overrides)
        return dados

    @patch("apps.integracoes.ixc.services.cria_login_atendimento.IXCClient")
    def test_sucesso_retorna_id_ixc(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            200, {"type": "success", "id": "321"},
        )
        status, mensagem, id_ixc = executar_cadastro_ixc(self._dados_login())
        self.assertTrue(status)
        self.assertEqual(id_ixc, "321")

    @patch("apps.integracoes.ixc.services.cria_login_atendimento.IXCClient")
    def test_ixc_nega_o_login(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (
            200, {"type": "error", "message": "Login duplicado", "id": None},
        )
        status, mensagem, id_ixc = executar_cadastro_ixc(self._dados_login())
        self.assertFalse(status)
        self.assertIn("Login duplicado", mensagem)
        self.assertIsNone(id_ixc)

    @patch("apps.integracoes.ixc.services.cria_login_atendimento.IXCClient")
    def test_erro_http(self, mock_ixc_client_cls):
        mock_ixc_client_cls.return_value.escrever.return_value = (500, {"message": "Erro interno"})
        status, mensagem, id_ixc = executar_cadastro_ixc(self._dados_login())
        self.assertFalse(status)
        self.assertIn("500", mensagem)
        self.assertIsNone(id_ixc)
