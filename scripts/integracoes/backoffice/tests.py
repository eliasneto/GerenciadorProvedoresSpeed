import zipfile
from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.integracoes.backoffice.resolver_os_atendimento_ixc import (
    executar_resolucao_os_atendimento_ixc,
    localizar_anexo_no_zip,
    normalizar_fechar_todas_os,
    normalizar_tem_anexo,
)


def _zip_com_pdf(nome_arquivo="comunicado.pdf", conteudo=b"conteudo do pdf"):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo_zip:
        arquivo_zip.writestr(nome_arquivo, conteudo)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


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

    def test_erro_quando_arquivo_nao_e_pdf(self):
        zip_arquivos = _zip_com_pdf("comunicado.docx")
        conteudo, nome_real, erro = localizar_anexo_no_zip(zip_arquivos, "comunicado.docx")
        self.assertIsNone(conteudo)
        self.assertIn("nao e um PDF", erro)

    def test_erro_quando_nenhum_zip_foi_informado(self):
        conteudo, nome_real, erro = localizar_anexo_no_zip(None, "comunicado.pdf")
        self.assertIsNone(conteudo)
        self.assertIn("Nenhum arquivo ZIP", erro)


@patch("scripts.integracoes.backoffice.resolver_os_atendimento_ixc.finalizar_os_existente")
@patch("scripts.integracoes.backoffice.resolver_os_atendimento_ixc.listar_os_para_desativacao")
@patch("scripts.integracoes.backoffice.resolver_os_atendimento_ixc.buscar_atendimento_ixc_por_id")
@patch("scripts.integracoes.backoffice.resolver_os_atendimento_ixc.anexar_arquivo_ticket_ixc")
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
