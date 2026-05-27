from unittest.mock import patch

from django.test import SimpleTestCase

from partners.views import (
    _detalhe_os_ixc_para_auditoria,
    _detalhe_os_ixc_para_historico,
    _mensagem_os_ixc_ja_finalizada,
    _status_os_ixc_para_operador,
)
from scripts.integracoes.ixc_finalizacao_service import finalizar_os_existente


class OsIxcFeedbackTests(SimpleTestCase):
    def test_status_indica_quando_os_ja_estava_finalizada(self):
        resultado_ixc = {"already_closed": True}

        self.assertEqual(
            _status_os_ixc_para_operador(True, resultado_ixc),
            "Já estava finalizada",
        )
        self.assertIn(
            "O.S. no IXC: Já estava finalizada",
            _detalhe_os_ixc_para_historico(True, "Encerrada pelo fluxo", resultado_ixc),
        )
        self.assertIn(
            "Status da O.S. no IXC: Já estava finalizada.",
            _detalhe_os_ixc_para_auditoria(True, "Encerrada pelo fluxo", resultado_ixc),
        )

    def test_mensagem_resume_multiplas_os_ja_finalizadas(self):
        proposta_1 = type("Proposal", (), {"codigo_exibicao": "COT-001"})()
        proposta_2 = type("Proposal", (), {"codigo_exibicao": "COT-002"})()

        mensagem = _mensagem_os_ixc_ja_finalizada([proposta_1, proposta_2])

        self.assertIn("2 O.S. já estavam finalizadas no IXC", mensagem)
        self.assertIn("sucesso", mensagem.casefold())


class FinalizacaoOsExistenteTests(SimpleTestCase):
    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_registros_fechamento_os", return_value=[{"id": "99"}])
    @patch("scripts.integracoes.ixc_finalizacao_service.buscar_os_por_id", return_value={"id": "5313", "status": "F"})
    def test_retorno_idempotente_marca_os_ja_finalizada(self, _buscar_os, _buscar_registros):
        resultado = finalizar_os_existente(os_id="5313", mensagem="Teste")

        self.assertTrue(resultado["ok"])
        self.assertTrue(resultado["already_closed"])
        self.assertEqual(resultado["registro_fechamento"]["id"], "99")
