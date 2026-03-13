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
#  CONFIGURAÇÃO DO AMBIENTE DJANGO
# ==========================================
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(DIRETORIO_ATUAL))

# Adiciona a raiz do projeto ao PATH
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

#  A MÁGICA AQUI: Adiciona a pasta 'apps' ao PATH do script!
APPS_DIR = os.path.join(BASE_DIR, 'apps')
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') 

import django
django.setup()

# Agora sim, com o Django configurado, podemos importar os models!
from clientes.models import Cliente, Endereco, HistoricoSincronizacao
from django.utils import timezone

# ==========================================
#  CONFIGURAÇÕES DA API DO IXC
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
    print(" Mapeando nomes das filiais no IXC...")
    payload = {"qtype": "id", "query": "0", "oper": ">", "page": "1", "rp": "100"}
    res = consultar_ixc("filial", payload)
    mapa = {}
    if res and 'registros' in res:
        for f in res['registros']:
            mapa[str(f['id'])] = f.get('razao') or f.get('filial') or f"Filial {f['id']}"
    return mapa

#  AQUI ESTÁ A REGRA DE TEMPO! 
# dias_retroativos=0 puxa só o dia de HOJE (D-0).
# dias_retroativos=1 puxa ontem e hoje (D-1).
def extrair_clientes_recentes(dias_retroativos=0):
    # Se dias_retroativos for None ou muito alto, vira uma CARGA TOTAL
    if dias_retroativos is None:
        data_limite = "2000-01-01 00:00:00"
        print(" 🚀 Iniciando CARGA TOTAL (Buscando todos os registros)...")
    else:
        data_limite = (datetime.now() - timedelta(days=dias_retroativos)).strftime('%Y-%m-%d 00:00:00')
        print(f" ⏳ Iniciando extração INCREMENTAL (Após {data_limite})...")
    
    pagina_atual = 1
    registros_por_pagina = 100 # Aumentado para ser mais rápido
    base_de_dados_local = []
    parar_busca = False

    pbar = tqdm(desc=" 🔍 Lendo API IXC", unit="cli")

    while not parar_busca:
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
            data_ixc = cliente.get('data_atualizacao') or '2000-01-01 00:00:00'
            
            # O FREIO: Só ativa se não for carga total
            if dias_retroativos is not None and data_ixc < data_limite:
                parar_busca = True
                break

            id_cli = cliente['id']
            
            # BUSCA LOGINS (radusuarios)
            res_logins = consultar_ixc("radusuarios", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
            logins_encontrados = res_logins.get('registros', []) if res_logins else []

            # BUSCA CONTRATOS
            res_con = consultar_ixc("cliente_contrato", {"qtype": "id_cliente", "query": id_cli, "oper": "=", "rp": "50"})
            contratos_encontrados = res_con.get('registros', []) if res_con else []

            dados_completos = {
                "id_ixc": id_cli,
                "nome_com_id": f"{id_cli} - {cliente['razao']}",
                "fantasia": cliente.get('fantasia') or '',
                "cpf_cnpj": cliente.get('cnpj_cpf') or '',
                "contratos": contratos_encontrados,
                "logins": logins_encontrados
            }
            base_de_dados_local.append(dados_completos)
            pbar.update(1)

        pagina_atual += 1

    pbar.close()
    return base_de_dados_local

def salvar_clientes_no_django(dados_ixc, mapa_filiais):
    if not dados_ixc:
        print(" Nenhuma alteração nova no IXC para sincronizar. Sistema já está atualizado!")
        return

    print("\n Atualizando registros no banco de dados...")
    pbar_save = tqdm(total=len(dados_ixc), desc=" Gravando no Banco", unit="cli")

    for dado in dados_ixc:
        cnpj_limpo = str(dado.get('cpf_cnpj') or '').strip()

        cliente_obj, _ = Cliente.objects.update_or_create(
            id_ixc=dado['id_ixc'],
            defaults={
                'cnpj_cpf': cnpj_limpo,
                'razao_social': dado['nome_com_id'],
                'nome_fantasia': dado['fantasia']
            }
        )

        for lg in dado.get('logins', []):
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            
            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_contrato_ixc = str(con_pai.get('status', 'A')).strip().upper()
            
            if status_contrato_ixc in ['C', 'D', 'CM', 'CANCELADO', 'DESISTENCIA', 'DESISTÊNCIA']:
                status_django = 'cancelado'
            elif status_login_ixc == 'N':
                status_django = 'inativo'
            elif status_login_ixc == 'S':
                status_django = 'ativo'
            else:
                status_django = 'pendente'

            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=lg['login'],
                defaults={
                    'logradouro': con_pai.get('endereco') or 'Não informado',
                    'numero': con_pai.get('numero') or 'S/N',
                    'bairro': con_pai.get('bairro', ''),
                    'cidade': con_pai.get('cidade', ''),
                    'estado': str(con_pai.get('uf', 'CE'))[:2].upper(),
                    'tipo': '', 
                    'filial_ixc': mapa_filiais.get(con_pai.get('filial_id'), f"Filial {con_pai.get('filial_id')}"),
                    'agente_id_ixc': con_pai.get('agente_id', ''),
                    'status': status_django
                }
            )
        pbar_save.update(1)

    pbar_save.close()
    print(" Sincronização Incremental concluída com sucesso!")

if __name__ == "__main__":
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # 1. BATE O PONTO DE ENTRADA (Cria o registro dizendo que começou)
    historico = HistoricoSincronizacao.objects.create(status='rodando')
    print(f" [LOG] Iniciando sincronização. ID do Log: {historico.id}")
    
    try:
        # Tenta rodar a integração normalmente
        mapa_f = buscar_mapa_filiais()
        meus_dados = extrair_clientes_recentes(dias_retroativos=0) 
        salvar_clientes_no_django(meus_dados, mapa_f)
        
        # Se chegou até aqui, deu tudo certo! Atualiza o log com Sucesso.
        historico.status = 'sucesso'
        historico.registros_processados = len(meus_dados)
        historico.detalhes = "Sincronização concluída perfeitamente."
        print(" [LOG] Sincronização registrada com SUCESSO no banco.")
        
    except Exception as erro_encontrado:
            # Captura o erro completo, incluindo a linha do código que falhou!
            erro_completo = traceback.format_exc()
            
            historico.status = 'erro'
            historico.detalhes = f"ERRO FATAL NA INTEGRAÇÃO:\n\n{erro_completo}"
            print(" [LOG] ERRO! A integração falhou. O rastro completo foi salvo no painel Admin.")
        
    finally:
        # 2. BATE O PONTO DE SAÍDA (Anota a hora que terminou, dando certo ou errado)
        historico.data_fim = timezone.now()
        historico.save()