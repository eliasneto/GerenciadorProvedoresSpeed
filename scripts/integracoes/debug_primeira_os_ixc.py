import os
import sys
import json


DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.clientes.models import Endereco
from apps.integracoes.ixc.client import IXCClient

# Toda leitura do IXC passa pelo IXCClient (ADR-005, PO-025).


def consultar_ixc_raw(tabela, payload):
    return IXCClient().listar(tabela, payload)


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
