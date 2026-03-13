import requests
import json
import base64
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "COLOQUE_SEU_TOKEN_AQUI" # Cole o mesmo token que funcionou no outro script!

token_b64 = base64.b64encode(IXC_TOKEN.encode('utf-8')).decode('utf-8')
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {token_b64}',
    'ixcsoft': 'listar'
}

def explorar_tabela(nome_tabela):
    """Busca apenas 1 registro da tabela e lista todos os campos disponíveis"""
    print(f"\n{'='*50}")
    print(f"🔍 EXPLORANDO TABELA: {nome_tabela.upper()}")
    print(f"{'='*50}")
    
    url = f"{IXC_URL}/{nome_tabela}"
    
    # Payload pedindo apenas 1 registro (rp: 1)
    payload = {
        "qtype": "id",
        "query": "0",
        "oper": ">",
        "page": "1",
        "rp": "1"
    }
    
    try:
        response = requests.post(url, headers=HEADERS, data=json.dumps(payload), verify=False)
        dados = response.json()
        
        if 'registros' in dados and len(dados['registros']) > 0:
            registro_exemplo = dados['registros'][0]
            
            # Pega todas as "chaves" (nomes dos campos) do JSON
            campos = list(registro_exemplo.keys())
            campos.sort() # Coloca em ordem alfabética para facilitar a leitura
            
            print(f"✅ Encontrados {len(campos)} campos nesta tabela. São eles:\n")
            
            # Imprime os campos em colunas para ficar bonito no terminal
            for i in range(0, len(campos), 3):
                linha = campos[i:i+3]
                print("{:<30} {:<30} {:<30}".format(*linha + [''] * (3 - len(linha))))
                
            print("\n💡 Exemplo de dados do primeiro registro:")
            # Mostra alguns dados reais para você ver o formato
            print(f"   ID: {registro_exemplo.get('id')}")
            if nome_tabela == 'cliente':
                print(f"   Nome/Razão: {registro_exemplo.get('razao')}")
                print(f"   Data Cadastro: {registro_exemplo.get('data_cadastro')}")
        else:
            print("Nenhum registro encontrado nesta tabela.")
            
    except Exception as e:
        print(f"Erro ao acessar {nome_tabela}: {e}")

if __name__ == "__main__":
    # Vamos explorar as 3 tabelas principais!
    explorar_tabela("cliente")
    explorar_tabela("cliente_contrato")
    explorar_tabela("radusuarios")