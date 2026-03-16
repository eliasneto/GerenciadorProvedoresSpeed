import os
import sys
import requests
import json
import base64
import urllib3
from tqdm import tqdm  

# ==========================================
# ⚙️ CONFIGURAÇÃO DO AMBIENTE DJANGO
# ==========================================
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

from clientes.models import Cliente, Endereco, LogAlteracaoIXC

# ==========================================
# 🌐 CONFIGURAÇÕES DA API DO IXC
# ==========================================
IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"  
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

token_b64 = base64.b64encode(IXC_TOKEN.encode('utf-8')).decode('utf-8')

HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {token_b64}',
    'ixcsoft': 'listar' 
}

def consultar_ixc(tabela, payload):
    url = f"{IXC_URL}/{tabela}"
    try:
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False) 
        response.raise_for_status()
        return response.json()
    except Exception:
        return None

def buscar_mapa_filiais():
    """Busca os nomes reais das filiais no IXC"""
    print("🏢 Mapeando nomes das filiais no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("filial", payload)
    mapa = {}
    if res and 'registros' in res:
        for f in res['registros']:
            mapa[str(f['id'])] = f.get('razao') or f.get('filial') or f"Filial {f['id']}"
    return mapa

def extrair_todos_os_clientes():
    pagina_atual = 1
    registros_por_pagina = 50
    base_de_dados_local = []

    res_total = consultar_ixc("cliente", {"qtype": "ativo", "query": "S", "oper": "=", "rp": "1"})
    total_no_ixc = int(res_total.get('total', 0)) if res_total else 0

    print(f"🚀 Iniciando extração de {total_no_ixc} clientes ativos...")
    pbar = tqdm(total=total_no_ixc, desc="📥 Extraindo da API", unit="cli")

    while True:
        payload_clientes = {
            "qtype": "ativo", "query": "S", "oper": "=",
            "page": str(pagina_atual), "rp": str(registros_por_pagina),
            "sortname": "id", "sortorder": "asc"
        }

        resposta = consultar_ixc("cliente", payload_clientes)
        if not resposta or 'registros' not in resposta:
            break
        clientes = resposta['registros']
        if not clientes:
            break

        for cliente in clientes:
            id_cli = cliente['id']
            res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
            logins_encontrados = res_logins.get('registros', []) if res_logins else []

            if len(logins_encontrados) > 0:
                dados_completos = {
                    "id_ixc": id_cli,
                    "nome_com_id": f"{id_cli} - {cliente['razao']}",
                    "fantasia": cliente.get('fantasia') or '',
                    "cpf_cnpj": cliente.get('cnpj_cpf') or '',
                    "contratos": [],
                    "logins": [
                        {
                            "id_contrato": l.get('id_contrato', ''), 
                            "login": l['login'], 
                            "ativo": l.get('ativo', 'S'),
                            "circuit_id": l.get('agent_circuit_id', '') # <--- PEGA O CAMPO DA API
                        } for l in logins_encontrados]
                }

                res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "5000"})
                if res_con and 'registros' in res_con:
                    for c in res_con['registros']:
                        dados_completos["contratos"].append({
                            "id_contrato": c['id'], "status": c['status'], "endereco": c.get('endereco', ''),
                            "numero": c.get('numero', 'S/N'), "bairro": c.get('bairro', ''), "cidade": c.get('cidade', ''),
                            "uf": c.get('uf', 'CE'), "filial_id": str(c.get('id_filial', '')), "agente_id": c.get('vendedor', '')
                        })
                base_de_dados_local.append(dados_completos)
            pbar.update(1)
        pagina_atual += 1

    pbar.close()
    return base_de_dados_local

def salvar_clientes_no_django(dados_ixc, mapa_filiais):
    print("\n💾 Gravando no banco de dados com Auditoria...")
    pbar_save = tqdm(total=len(dados_ixc), desc="💾 Gravando no Banco", unit="cli")

    for dado in dados_ixc:
        id_ixc = dado['id_ixc']
        cnpj_novo = str(dado.get('cpf_cnpj') or '').strip()
        razao_nova = dado['nome_com_id']

        # --- LOGICA DE AUDITORIA DE CLIENTE ---
        cliente_obj = Cliente.objects.filter(id_ixc=id_ixc).first()
        if cliente_obj:
            if cliente_obj.cnpj_cpf != cnpj_novo:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="cnpj_cpf", valor_antigo=cliente_obj.cnpj_cpf, valor_novo=cnpj_novo)
            if cliente_obj.razao_social != razao_nova:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="razao_social", valor_antigo=cliente_obj.razao_social, valor_novo=razao_nova)

        cliente_obj, _ = Cliente.objects.update_or_create(
            id_ixc=id_ixc,
            defaults={'cnpj_cpf': cnpj_novo, 'razao_social': razao_nova, 'nome_fantasia': dado['fantasia']}
        )

        for lg in dado.get('logins', []):
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            
            # TRADUTOR DE STATUS
            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_contrato_ixc = str(con_pai.get('status', 'A')).strip().upper()
            
            if status_contrato_ixc in ['C', 'D', 'CM', 'CANCELADO']:
                status_django = 'cancelado'
            elif status_login_ixc == 'N':
                status_django = 'inativo'
            else:
                status_django = 'ativo'

            filial_nova = mapa_filiais.get(con_pai.get('filial_id'), f"Filial {con_pai.get('filial_id')}")

            # --- LOGICA DE AUDITORIA DE ENDEREÇO / CIRCUITO ---
            end_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=lg['login']).first()
            if end_atual:
                if end_atual.status != status_django:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=lg['login'], campo_alterado="status", valor_antigo=end_atual.status, valor_novo=status_django)
                if end_atual.agent_circuit_id != lg['circuit_id']:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=lg['login'], campo_alterado="agent_circuit_id", valor_antigo=end_atual.agent_circuit_id, valor_novo=lg['circuit_id'])

            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=lg['login'],
                defaults={
                    'logradouro': con_pai.get('endereco') or 'Não informado',
                    'numero': con_pai.get('numero') or 'S/N',
                    'bairro': con_pai.get('bairro', ''),
                    'cidade': con_pai.get('cidade', ''),
                    'estado': str(con_pai.get('uf', 'CE'))[:2].upper(),
                    'filial_ixc': filial_nova,
                    'agent_circuit_id': lg['circuit_id'], # <--- GRAVA NO BANCO
                    'status': status_django
                }
            )
        pbar_save.update(1)

    pbar_save.close()
    print("✅ Carga total concluída com sucesso!")

if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    mapa_f = buscar_mapa_filiais()
    meus_dados = extrair_todos_os_clientes()
    if meus_dados:
        salvar_clientes_no_django(meus_dados, mapa_f)