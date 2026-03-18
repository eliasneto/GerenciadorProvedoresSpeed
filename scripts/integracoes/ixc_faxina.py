import os
import sys
import requests
import json
import base64
import urllib3
from tqdm import tqdm
import traceback
from django.utils import timezone
from django.contrib.auth import get_user_model

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

from clientes.models import Cliente, ClienteExcluido, Endereco, EnderecoExcluido, HistoricoSincronizacao

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

def executar_faxina(historico): # <-- ADICIONADO: recebe o histórico
    print("🧹 Iniciando busca por clientes e logins removidos no IXC...")
    
    payload_cli = {"qtype": "id", "query": "0", "oper": ">", "rp": "20000"}
    resposta_cli = consultar_ixc("cliente", payload_cli)
    
    if not resposta_cli or 'registros' not in resposta_cli:
        raise Exception("❌ Erro ao conectar com IXC. Faxina abortada.")

    ids_clientes_ixc = {str(r['id']) for r in resposta_cli['registros']}
    
    payload_logins = {"qtype": "id", "query": "0", "oper": ">", "rp": "50000"}
    resposta_logins = consultar_ixc("radusuarios", payload_logins)
    logins_ixc = {str(r['login']).strip() for r in resposta_logins.get('registros', [])} if resposta_logins else set()

    clientes_locais = Cliente.objects.all()
    clientes_removidos = 0
    logins_removidos = 0

    print(f"🔍 Comparando {clientes_locais.count()} clientes locais com o IXC...")

    # --- FASE 1: CLIENTES ---
    for cli in tqdm(clientes_locais, desc="Auditando Clientes", unit="cli"):
        # 🛑 CHECK DE PARADA
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Faxina interrompida via Admin")

        if str(cli.id_ixc) not in ids_clientes_ixc:
            lixo_cli = ClienteExcluido.objects.create(
                id_ixc=cli.id_ixc,
                razao_social=cli.razao_social,
                cnpj_cpf=cli.cnpj_cpf,
                dados_completos_json={ 
                    "fantasia": getattr(cli, 'nome_fantasia', ''),
                    "email": getattr(cli, 'email', ''),
                    "telefone": getattr(cli, 'telefone', ''),
                    "contato": getattr(cli, 'contato_nome', '')
                },
                data_exclusao=timezone.now()
            )
            
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
            
            cli.delete()
            clientes_removidos += 1

    # --- FASE 2: LOGINS ---
    enderecos_locais = Endereco.objects.all()
    print(f"\n🔍 Verificando {enderecos_locais.count()} logins locais...")

    for end in tqdm(enderecos_locais, desc="Auditando Logins", unit="login"):
        # 🛑 CHECK DE PARADA
        historico.refresh_from_db()
        if historico.detalhes == "STOP":
            raise KeyboardInterrupt("Faxina interrompida via Admin")

        login_atual = str(end.login_ixc).strip()
        if not login_atual or login_atual == "MANUAL / SEM LOGIN":
            continue

        if login_atual not in logins_ixc:
            end.delete()
            logins_removidos += 1

    return clientes_removidos + logins_removidos

if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'
    
    usuario_executor = None
    if eh_manual:
        User = get_user_model()
        usuario_executor = User.objects.filter(is_superuser=True).first()
    
    print(f"🤖 Faxina detectada como: {origem_detectada.upper()}")

    historico = HistoricoSincronizacao.objects.create(
        tipo='faxina', 
        status='rodando',
        origem=origem_detectada,
        executado_por=usuario_executor
    )
    
    try:
        # Passamos o objeto historico para a função
        total_removidos = executar_faxina(historico)
        
        historico.status = 'sucesso'
        historico.registros_processados = total_removidos
        historico.detalhes = f"Faxina concluída via {origem_detectada}. {total_removidos} registros movidos para o lixo."
        
    except KeyboardInterrupt as e:
        historico.status = 'erro'
        msg_erro = str(e) if "Parada" in str(e) else "Faxina interrompida manualmente (Ctrl+C)."
        historico.detalhes = msg_erro
        print(f"\n⚠️ {msg_erro}")

    except Exception as e:
        historico.status = 'erro'
        historico.detalhes = traceback.format_exc()
        print(f"❌ Erro fatal registrado no banco: {str(e)}")
        
    finally:
        historico.data_fim = timezone.now()
        historico.save()
        print(f"✅ Fim da rotina {historico.tipo} ({origem_detectada}).")