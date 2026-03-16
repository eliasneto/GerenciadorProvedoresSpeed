import os
import sys
import requests
import json
import base64
import urllib3
from tqdm import tqdm
import traceback

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

from clientes.models import Cliente, ClienteExcluido, EnderecoExcluido, HistoricoSincronizacao
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

def executar_faxina():
    print("🧹 Iniciando busca por clientes removidos no IXC...")
    
    # 1. Pega a lista de IDs de clientes ativos no IXC (lista rápida de 10 mil itens)
    payload = {"qtype": "id", "query": "0", "oper": ">", "rp": "10000"}
    resposta = consultar_ixc("cliente", payload)
    
    if not resposta or 'registros' not in resposta:
        raise Exception("❌ Erro ao conectar com IXC. A API não retornou dados. Faxina abortada por segurança.")

    ids_no_ixc = {str(r['id']) for r in resposta['registros']}
    
    # 2. Pega todos os clientes que temos no nosso banco
    clientes_locais = Cliente.objects.all()
    removidos = 0

    print(f"🔍 Comparando {clientes_locais.count()} registros locais com o IXC...")

    for cli in tqdm(clientes_locais, desc="Processando", unit="cli"):
        if str(cli.id_ixc) not in ids_no_ixc:
            # 3. MOVER PARA O LIXO
            lixo_cli = ClienteExcluido.objects.create(
                id_ixc=cli.id_ixc,
                razao_social=cli.razao_social,
                cnpj_cpf=cli.cnpj_cpf,
                dados_originais_json={
                    "fantasia": getattr(cli, 'nome_fantasia', ''),
                    "email": getattr(cli, 'email', ''),
                    "telefone": getattr(cli, 'telefone', ''),
                    "contato": getattr(cli, 'contato_nome', '')
                }
            )
            
            # Move endereços/logins associados
            for end in cli.enderecos.all():
                EnderecoExcluido.objects.create(
                    cliente_excluido=lixo_cli,
                    login_ixc=end.login_ixc,
                    agent_circuit_id=end.agent_circuit_id,
                    detalhes_json={
                        "filial": end.filial_ixc,
                        "cidade": end.cidade,
                        "logradouro": end.logradouro,
                        "numero": end.numero,
                        "status_na_epoca": end.status
                    }
                )
            
            # 4. DELETA DA BASE PRINCIPAL
            cli.delete()
            removidos += 1

    print(f"✅ Faxina finalizada. {removidos} clientes movidos para o Lixo IXC.")
    return removidos

if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Registra o início da FAXINA no banco
    historico = HistoricoSincronizacao.objects.create(tipo='faxina', status='rodando')
    
    try:
        total_removidos = executar_faxina()
        
        historico.status = 'sucesso'
        historico.registros_processados = total_removidos
        historico.detalhes = f"Faxina concluída com sucesso. {total_removidos} clientes movidos para o arquivo morto."
        
    except Exception as e:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print(f"❌ Erro fatal registrado no banco: {str(e)}")
        
    finally:
        historico.data_fim = timezone.now()
        historico.save()
        print(f"✅ Fim da rotina {historico.tipo}.")