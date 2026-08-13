from unittest import mock

import requests
from django.test import SimpleTestCase

from apps.integracoes.dashboard_eace.client import DashboardEACEClient
from apps.integracoes.dashboard_eace.services.escolas import (
    buscar_escola_por_jira_key,
    listar_escolas,
)


class DashboardEACEClientTests(SimpleTestCase):
    """PO-045/ADR-009: cobre somente a estrutura do client (sem endpoint real)."""

    def test_inicializa_com_variaveis_de_ambiente(self):
        with mock.patch.dict(
            "os.environ",
            {"DASHBOARD_EACE_URL": "https://dashboard-eace.exemplo.com/api", "DASHBOARD_EACE_TOKEN": "abc123"},
        ):
            client = DashboardEACEClient()

        self.assertEqual(client.base_url, "https://dashboard-eace.exemplo.com/api")
        self.assertEqual(client.token, "abc123")
        self.assertTrue(client.verify_ssl)
        self.assertEqual(client.timeout, 30)

    def test_parametros_explicitos_tem_prioridade_sobre_variavel_de_ambiente(self):
        with mock.patch.dict(
            "os.environ",
            {"DASHBOARD_EACE_URL": "https://ambiente.exemplo.com", "DASHBOARD_EACE_TOKEN": "do-ambiente"},
        ):
            client = DashboardEACEClient(base_url="https://explicito.exemplo.com/", token="explicito", timeout=10)

        self.assertEqual(client.base_url, "https://explicito.exemplo.com")
        self.assertEqual(client.token, "explicito")
        self.assertEqual(client.timeout, 10)

    def test_falha_com_mensagem_clara_sem_url(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesMessage(RuntimeError, "DASHBOARD_EACE_URL"):
                DashboardEACEClient(token="abc123")

    def test_falha_com_mensagem_clara_sem_token(self):
        with mock.patch.dict("os.environ", {"DASHBOARD_EACE_URL": "https://dashboard-eace.exemplo.com"}, clear=True):
            with self.assertRaisesMessage(RuntimeError, "DASHBOARD_EACE_TOKEN"):
                DashboardEACEClient()

    def test_verify_ssl_padrao_e_seguro(self):
        with mock.patch.dict(
            "os.environ",
            {"DASHBOARD_EACE_URL": "https://dashboard-eace.exemplo.com", "DASHBOARD_EACE_TOKEN": "abc123"},
            clear=True,
        ):
            client = DashboardEACEClient()

        self.assertTrue(client.verify_ssl)

    def test_headers_montam_autenticacao_x_api_key(self):
        client = DashboardEACEClient(base_url="https://dashboard-eace.exemplo.com", token="meu-token")

        self.assertEqual(
            client.headers,
            {
                "X-API-Key": "meu-token",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    @mock.patch("apps.integracoes.dashboard_eace.client.requests.get")
    def test_get_retorna_status_e_corpo_json(self, mock_get):
        mock_get.return_value = mock.Mock(status_code=200, json=lambda: {"ok": True})
        client = DashboardEACEClient(base_url="https://dashboard-eace.exemplo.com", token="meu-token")

        status_code, body = client.get("enderecos", params={"pagina": 1})

        self.assertEqual(status_code, 200)
        self.assertEqual(body, {"ok": True})
        mock_get.assert_called_once_with(
            "https://dashboard-eace.exemplo.com/enderecos",
            headers=client.headers,
            params={"pagina": 1},
            verify=True,
            timeout=30,
        )

    @mock.patch("apps.integracoes.dashboard_eace.client.requests.get")
    def test_get_trata_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()
        client = DashboardEACEClient(base_url="https://dashboard-eace.exemplo.com", token="meu-token")

        status_code, body = client.get("enderecos")

        self.assertEqual(status_code, 408)
        self.assertEqual(body["type"], "error")


class EscolasServiceTests(SimpleTestCase):
    """PO-046: wrappers dos endpoints confirmados em API_EXTERNA.md secao 4.1."""

    def setUp(self):
        self.client = DashboardEACEClient(base_url="https://dashboard-eace.exemplo.com", token="meu-token")

    def test_listar_escolas_sem_filtro(self):
        with mock.patch.object(self.client, "get", return_value=(200, {"escolas": []})) as mock_get:
            status_code, body = listar_escolas(client=self.client)

        self.assertEqual(status_code, 200)
        self.assertEqual(body, {"escolas": []})
        mock_get.assert_called_once_with("escolas", params={})

    def test_listar_escolas_com_filtros(self):
        with mock.patch.object(self.client, "get", return_value=(200, {"escolas": []})) as mock_get:
            listar_escolas(uf="SP", status_escola="Conectado", client=self.client)

        mock_get.assert_called_once_with("escolas", params={"uf": "SP", "status_escola": "Conectado"})

    def test_buscar_escola_por_jira_key_encontrada(self):
        with mock.patch.object(self.client, "get", return_value=(200, {"jira_key": "EACE-123"})) as mock_get:
            status_code, body = buscar_escola_por_jira_key("EACE-123", client=self.client)

        self.assertEqual(status_code, 200)
        self.assertEqual(body["jira_key"], "EACE-123")
        mock_get.assert_called_once_with("escolas/EACE-123")

    def test_buscar_escola_por_jira_key_nao_encontrada(self):
        with mock.patch.object(self.client, "get", return_value=(404, {"detail": "Not Found"})):
            status_code, body = buscar_escola_por_jira_key("EACE-999", client=self.client)

        self.assertEqual(status_code, 404)
        self.assertEqual(body, {"detail": "Not Found"})
