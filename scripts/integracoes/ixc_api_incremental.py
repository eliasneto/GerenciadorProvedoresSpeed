import os
import sys
import requests
import json
import base64
import urllib3
from datetime import datetime, timedelta
from tqdm import tqdm  
import traceback

# ==========================================
# ⚙️ CONFIGURAÇÃO DO AMBIENTE DJANGO
# ==========================================
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# Adiciona a pasta 'apps' ao PATH
APPS_DIR = os.path.join(BASE_DIR, 'apps')
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') 

import django
django.setup()

# Importação dos models (Sempre APÓS o django.setup)
from clientes.models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC
from django.utils import timezone

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
    print("🏢 Mapeando nomes das filiais no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("filial", payload)
    mapa = {}
    if res and 'registros' in res:
        for f in res['registros']:
            mapa[str(f['id'])] = f.get('razao') or f.get('filial') or f"Filial {f['id']}"
    return mapa

def extrair_clientes_recentes(dias_retroativos=0):
    # 1. Calcula a data limite para o "freio"
    data_limite = (datetime.now() - timedelta(days=dias_retroativos)).strftime('%Y-%m-%d 00:00:00')
    
    # 2. Descobrimos o total de clientes ATIVOS (Exatamente como na carga total)
    res_total = consultar_ixc("cliente", {"qtype": "ativo", "query": "S", "oper": "=", "rp": "1"})
    total_ativos = int(res_total.get('total', 0)) if res_total else 0

    print(f"⏳ Analisando {total_ativos} clientes ativos em busca de alterações após {data_limite}...")
    
    pagina_atual = 1
    registros_por_pagina = 50
    base_de_dados_local = []
    parar_busca = False
    
    # Barra de progresso baseada no total de ativos
    pbar = tqdm(total=total_ativos, desc="📥 Varrendo API IXC", unit="cli")

    while not parar_busca:
        # Acessa os clientes exatamente como na automação de carga total
        # Mas ordenando por data_atualizacao desc para achar os novos rápido
        payload = {
            "qtype": "ativo", "query": "S", "oper": "=",
            "page": str(pagina_atual), "rp": str(registros_por_pagina),
            "sortname": "data_atualizacao", "sortorder": "desc" 
        }

        resposta = consultar_ixc("cliente", payload)
        if not resposta or 'registros' not in resposta: break
            
        clientes = resposta['registros']
        if not clientes: break

        for cliente in clientes:
            # 3. AQUI ESTÁ A LÓGICA DO INCREMENTAL:
            # Se chegarmos em um cliente com data de atualização antiga, paramos a busca.
            data_ixc = cliente.get('data_atualizacao') or '2000-01-01 00:00:00'
            
            if data_ixc < data_limite:
                parar_busca = True
                # Preenche a barra até o final e sai
                pbar.update(total_ativos - pbar.n)
                break

            id_cli = cliente['id']
            
            # Busca Logins e Contratos (Igual à carga total)
            res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
            logins_encontrados = res_logins.get('registros', []) if res_logins else []

            res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
            contratos_encontrados = res_con.get('registros', []) if res_con else []

            base_de_dados_local.append({
                "id_ixc": id_cli,
                "nome_com_id": f"{id_cli} - {cliente['razao']}",
                "fantasia": cliente.get('fantasia') or '',
                "cpf_cnpj": cliente.get('cnpj_cpf') or '',
                "contratos": contratos_encontrados,
                "logins": logins_encontrados
            })
            pbar.update(1)

        pagina_atual += 1

    pbar.close()
    return base_de_dados_local

def salvar_clientes_no_django(dados_ixc, mapa_filiais):
    if not dados_ixc:
        print("✅ Sistema já está atualizado!")
        return

    print("\n💾 Gravando e auditando alterações no banco...")
    pbar_save = tqdm(total=len(dados_ixc), desc="💾 Gravando no Banco", unit="cli")

    for dado in dados_ixc:
        id_ixc = dado['id_ixc']
        cnpj_novo = str(dado.get('cpf_cnpj') or '').strip()
        razao_nova = dado['nome_com_id']
        
        # --- AUDITORIA (DE/PARA) ---
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
            login_nome = lg['login']
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            
            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_con_ixc = str(con_pai.get('status', 'A')).strip().upper()
            status_novo = 'cancelado' if status_con_ixc in ['C', 'D', 'CM', 'CANCELADO'] else ('inativo' if status_login_ixc == 'N' else 'ativo')
            filial_nova = mapa_filiais.get(str(con_pai.get('id_filial')), "Filial Não Informada")

            # --- AUDITORIA DE STATUS/FILIAL (DE/PARA) ---
            end_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=login_nome).first()
            if end_atual:
                if end_atual.status != status_novo:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="status", valor_antigo=end_atual.status, valor_novo=status_novo)
                if end_atual.filial_ixc != filial_nova:
                    LogAlteracaoIXC.objects.create(cliente=cliente_obj, login_ixc=login_nome, campo_alterado="filial", valor_antigo=end_atual.filial_ixc, valor_novo=filial_nova)

            Endereco.objects.update_or_create(
                cliente=cliente_obj, login_ixc=login_nome,
                defaults={
                    'logradouro': con_pai.get('endereco') or 'Não informado',
                    'numero': con_pai.get('numero') or 'S/N',
                    'bairro': con_pai.get('bairro', ''),
                    'cidade': con_pai.get('cidade', ''),
                    'estado': str(con_pai.get('uf', 'CE'))[:2].upper(),
                    'filial_ixc': filial_nova,
                    'status': status_novo
                }
            )
        pbar_save.update(1)

    pbar_save.close()
    print("✅ Sincronização concluída com sucesso!")

if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    historico = HistoricoSincronizacao.objects.create(status='rodando')
    
    try:
        mapa_f = buscar_mapa_filiais()
        # Roda o incremental (D-0)
        meus_dados = extrair_clientes_recentes(dias_retroativos=0) 
        salvar_clientes_no_django(meus_dados, mapa_f)
        
        historico.status = 'sucesso'
        historico.registros_processados = len(meus_dados)
        historico.detalhes = f"Incremental concluído. {len(meus_dados)} registros auditados."
    except Exception:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print("❌ Erro fatal registrado no banco.")
    finally:
        historico.data_fim = timezone.now()
        historico.save()