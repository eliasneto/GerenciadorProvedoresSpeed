import os
import sys
import json
import base64

import requests
import urllib3


DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

APPS_DIR = os.path.join(BASE_DIR, 'apps')
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from clientes.models import Endereco


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

TOKEN_B64 = base64.b64encode(IXC_TOKEN.encode('utf-8')).decode('utf-8')
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {TOKEN_B64}',
    'ixcsoft': 'listar',
}


def consultar_ixc_raw(tabela, payload):
    url = f"{IXC_URL}/{tabela}"
    response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False, timeout=30)
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return response.status_code, body


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/integracoes/debug_primeira_os_ixc.py <endereco_id>")
        raise SystemExit(1)

    endereco = Endereco.objects.select_related('cliente').get(pk=int(sys.argv[1]))

    print("\n=== ENDERECO LOCAL ===")
    print(f"ID local: {endereco.id}")
    print(f"Cliente local: {endereco.cliente_id}")
    print(f"Cliente IXC: {getattr(endereco.cliente, 'id_ixc', '')}")
    print(f"Login IXC: {endereco.login_ixc}")
    print(f"Login ID IXC: {endereco.login_id_ixc}")
    print(f"Contrato ID IXC: {endereco.contrato_id_ixc}")

    consultas = [
        ("id_login", str(endereco.login_id_ixc or '').strip()),
        ("id_contrato", str(endereco.contrato_id_ixc or '').strip()),
        ("id_cliente", str(getattr(endereco.cliente, 'id_ixc', '') or '').strip()),
        ("login", str(endereco.login_ixc or '').strip()),
    ]

    for qtype, query in consultas:
        if not query:
            continue

        payload = {
            "qtype": qtype,
            "query": query,
            "oper": "=",
            "page": "1",
            "rp": "5",
            "sortname": "id",
            "sortorder": "asc",
        }

        status_code, body = consultar_ixc_raw("su_ticket", payload)
        print(f"\n=== CONSULTA su_ticket | qtype={qtype} | query={query} ===")
        print(f"HTTP: {status_code}")
        print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
