import base64
import json
import os

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DEFAULT_IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
DEFAULT_IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "sim", "s", "yes", "y"}


class IXCClient:
    def __init__(self, base_url=None, token=None, verify_ssl=None, timeout=None):
        self.base_url = (base_url or os.getenv("IXC_URL") or DEFAULT_IXC_URL).rstrip("/")
        self.token = token or os.getenv("IXC_TOKEN") or DEFAULT_IXC_TOKEN
        self.verify_ssl = (
            verify_ssl if verify_ssl is not None
            else _parse_bool(os.getenv("IXC_SSL_VERIFY"), default=False)
        )
        self.timeout = int(timeout or os.getenv("IXC_TIMEOUT") or 30)

    @property
    def headers_listar(self):
        token_b64 = base64.b64encode(self.token.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {token_b64}",
            "Content-Type": "application/json",
            "ixcsoft": "listar",
        }

    @property
    def headers_write(self):
        token_b64 = base64.b64encode(self.token.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {token_b64}",
            "Content-Type": "application/json",
        }

    def post(self, endpoint, payload, include_ixcsoft=False):
        url = f"{self.base_url}/{str(endpoint).lstrip('/')}"
        response = requests.post(
            url,
            headers=self.headers_listar if include_ixcsoft else self.headers_write,
            data=json.dumps(payload),
            verify=self.verify_ssl,
            timeout=self.timeout,
        )

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        return response.status_code, body

    def listar(self, endpoint, payload):
        return self.post(endpoint, payload, include_ixcsoft=True)

    def escrever(self, endpoint, payload):
        return self.post(endpoint, payload, include_ixcsoft=False)

    def put(self, endpoint, payload):
        url = f"{self.base_url}/{str(endpoint).lstrip('/')}"
        response = requests.put(
            url,
            headers=self.headers_write,
            data=json.dumps(payload),
            verify=self.verify_ssl,
            timeout=self.timeout,
        )

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        return response.status_code, body
