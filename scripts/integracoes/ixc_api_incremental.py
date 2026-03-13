import os
import sys
import requests
import json
import base64
import urllib3
from datetime import datetime, timedelta
from tqdm import tqdm  
import traceback
from clientes.models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC
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
        print(" Nenhuma alteração nova no IXC para sincronizar.")
        return

    print("\n 🔍 Analisando e gravando alterações...")
    pbar_save = tqdm(total=len(dados_ixc), desc=" Processando", unit="cli")

    for dado in dados_ixc:
        id_ixc = dado['id_ixc']
        cnpj_novo = str(dado.get('cpf_cnpj') or '').strip()
        razao_nova = dado['nome_com_id']
        
        # 1. VERIFICA ALTERAÇÕES NO CLIENTE (RAZÃO OU CNPJ)
        cliente_obj = Cliente.objects.filter(id_ixc=id_ixc).first()
        
        if cliente_obj:
            if cliente_obj.cnpj_cpf != cnpj_novo:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="cnpj_cpf", valor_antigo=cliente_obj.cnpj_cpf, valor_novo=cnpj_novo)
            if cliente_obj.razao_social != razao_nova:
                LogAlteracaoIXC.objects.create(cliente=cliente_obj, campo_alterado="razao_social", valor_antigo=cliente_obj.razao_social, valor_novo=razao_nova)
        
        # Atualiza ou cria o Cliente
        cliente_obj, _ = Cliente.objects.update_or_create(
            id_ixc=id_ixc,
            defaults={'cnpj_cpf': cnpj_novo, 'razao_social': razao_nova, 'nome_fantasia': dado['fantasia']}
        )

        # 2. VERIFICA ALTERAÇÕES NOS ENDEREÇOS/LOGINS
        for lg in dado.get('logins', []):
            login_nome = lg['login']
            con_pai = next((c for c in dado['contratos'] if str(c['id_contrato']) == str(lg['id_contrato'])), {})
            
            # Lógica de Status (Mesma que você já usa)
            status_login_ixc = str(lg.get('ativo', 'S')).strip().upper()
            status_contrato_ixc = str(con_pai.get('status', 'A')).strip().upper()
            status_novo = 'cancelado' if status_contrato_ixc in ['C', 'D', 'CM'] else ('inativo' if status_login_ixc == 'N' else 'ativo')

            # BUSCA O REGISTRO ATUAL PARA COMPARAR
            endereco_atual = Endereco.objects.filter(cliente=cliente_obj, login_ixc=login_nome).first()
            
            if endereco_atual:
                # Se o status mudou, loga!
                if endereco_atual.status != status_novo:
                    LogAlteracaoIXC.objects.create(
                        cliente=cliente_obj, 
                        login_ixc=login_nome, 
                        campo_alterado="status_login", 
                        valor_antigo=endereco_atual.status, 
                        valor_novo=status_novo
                    )
                
                # Se a filial mudou, loga!
                filial_nova = mapa_filiais.get(con_pai.get('filial_id'), f"Filial {con_pai.get('filial_id')}")
                if endereco_atual.filial_ixc != filial_nova:
                    LogAlteracaoIXC.objects.create(
                        cliente=cliente_obj, 
                        login_ixc=login_nome, 
                        campo_alterado="filial", 
                        valor_antigo=endereco_atual.filial_ixc, 
                        valor_novo=filial_nova
                    )

            # Grava a atualização final
            Endereco.objects.update_or_create(
                cliente=cliente_obj,
                login_ixc=login_nome,
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