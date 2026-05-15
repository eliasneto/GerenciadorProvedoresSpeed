import pandas as pd
from django.test import SimpleTestCase

from apps.backoffice.views import serializar_linha_para_auditoria
from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    executar_abertura_atendimento,
    normalizar_id_numerico,
)


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
