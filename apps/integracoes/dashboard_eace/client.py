import os

import requests


def _parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


class DashboardEACEClient:
    """Cliente HTTP para a API do DashboardEACE (ADR-009, contrato em
    API_EXTERNA.md).

    Autenticacao via header `X-API-Key` (chave unica e fixa, sem
    multiplos clientes ou revogacao individual). Nao reaproveita a
    convencao propria do IXC (qtype/query/oper via POST) — essa e uma
    API REST convencional, diferente.
    """

    def __init__(self, base_url=None, token=None, verify_ssl=None, timeout=None):
        self.base_url = (base_url or os.getenv("DASHBOARD_EACE_URL") or "").rstrip("/")
        if not self.base_url:
            raise RuntimeError(
                "DASHBOARD_EACE_URL nao configurado. Defina a variavel de ambiente "
                "DASHBOARD_EACE_URL ou informe o parametro base_url."
            )

        self.token = token or os.getenv("DASHBOARD_EACE_TOKEN")
        if not self.token:
            raise RuntimeError(
                "DASHBOARD_EACE_TOKEN nao configurado. Defina a variavel de ambiente "
                "DASHBOARD_EACE_TOKEN ou informe o parametro token."
            )

        self.verify_ssl = (
            verify_ssl if verify_ssl is not None
            else _parse_bool(os.getenv("DASHBOARD_EACE_SSL_VERIFY"), default=True)
        )
        self.timeout = int(timeout or os.getenv("DASHBOARD_EACE_TIMEOUT") or 30)

    @property
    def headers(self):
        return {
            "X-API-Key": self.token,
            "Content-Type": "application/json; charset=utf-8",
        }

    def get(self, endpoint, params=None):
        url = f"{self.base_url}/{str(endpoint).lstrip('/')}"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params or {},
                verify=self.verify_ssl,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            return 408, {"type": "error", "message": f"Timeout ao conectar com o DashboardEACE ({self.timeout}s)."}
        except requests.exceptions.ConnectionError as exc:
            return 503, {"type": "error", "message": f"Falha de conexao com o DashboardEACE: {exc}"}
        except requests.exceptions.RequestException as exc:
            return 500, {"type": "error", "message": f"Erro de rede ao acessar o DashboardEACE: {exc}"}

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        return response.status_code, body
