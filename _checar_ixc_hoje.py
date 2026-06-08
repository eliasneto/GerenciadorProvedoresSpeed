import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "c:/Projetos/sgpspeed/GerenciadorProvedoresSpeed")

from scripts.integracoes.ixc_client import IXCClient

client = IXCClient()
payload = {
    "qtype": "cliente.data_cadastro",
    "query": "2026-06-08",
    "oper": "=",
    "page": "1",
    "rp": "1000",
    "sortname": "id",
    "sortorder": "desc",
}
status, body = client.listar("cliente", payload)
print(f"HTTP: {status}")

if isinstance(body, dict):
    total = body.get("total", "?")
    registros = body.get("registros") or []
    print(f"Total criados hoje (08/06/2026): {total}")
    print()
    for r in registros:
        print(f"  ID {r.get('id'):>6} | {r.get('razao','')[:55]:<55} | {r.get('cnpj_cpf','')}")
else:
    print("Resposta inesperada:", body)
