import pandas as pd
import requests
import base64
import urllib3
import re
import unicodedata
import json  # Importado para conseguirmos ver o Raio-X no terminal

# Desativa os avisos de segurança (InsecureRequestWarning) no terminal
# Isso deixa o seu log limpo quando usamos o verify=False no requests.post
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

def executar_cadastro_ixc(dados):
    endpoint = f"{IXC_URL}/radusuarios"
    token_b64 = base64.b64encode(IXC_TOKEN.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {token_b64}',
        'Content-Type': 'application/json'
    }

    # 🚀 BLINDAGEM CONTRA O EXCEL:
    # Remove qualquer espaço invisível do nome das colunas lidas da planilha
    # Exemplo: Transforma 'Plano_ID ' em 'Plano_ID' para o Python não se perder
    linha = {str(k).strip(): v for k, v in dados.items()}

    # FUNÇÃO DE LIMPEZA:
    # O Pandas transforma números do Excel em decimais (ex: 4 vira "4.0").
    # Essa função remove o ".0" e tira espaços vazios ao redor do número.
    def limpar_id(valor):
        if pd.isna(valor) or str(valor).strip().lower() == 'nan' or valor == '' or valor is None:
            return ''
        return str(valor).split('.')[0].strip()

    def limpar_login(texto):
        if pd.isna(texto) or texto is None:
            return ''
        
        texto = str(texto).strip() # Tira espaços das pontas
        texto = texto.replace(' ', '') # Tira espaços do meio
        
        # Remove acentos (ex: á vira a, ç vira c, õ vira o)
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
        
        # Remove QUALQUER símbolo que não seja letra, número, traço (-) ou underline (_)
        texto = re.sub(r'[^a-zA-Z0-9_-]', '', texto)
        
        return texto
    
    # 🚀 NOVA FUNÇÃO: Garante que só passem NÚMEROS (Remove .0, traços, etc)
    # 🚀 NOVA FUNÇÃO: Garante que o CEP vá perfeito para o IXC
    def somente_numeros(valor):
        if pd.isna(valor) or str(valor).strip().lower() == 'nan' or valor == '' or valor is None:
            return ''
        
        texto = str(valor).strip()
        
        # Se o Excel mandar como decimal (ex: 60346165.0), tira o .0
        if texto.endswith('.0'):
            texto = texto[:-2]
            
        # Arranca qualquer traço, ponto ou espaço (ex: 60.346-165 vira 60346165)
        numeros = re.sub(r'[^0-9]', '', texto)
        
        # CEP no Brasil TEM que ter 8 dígitos. AQUI ESTÁ A CORREÇÃO DA MÁSCARA:
        # Forçamos o traço no CEP porque o IXC na verdade exige XXXXX-XXX
        if len(numeros) == 8:
            return f"{numeros[:5]}-{numeros[5:]}"
        elif len(numeros) > 0:
            return numeros.zfill(8) # Devolve os zeros perdidos
            
        return ''

    def limpar_texto(valor):
        if pd.isna(valor) or str(valor).strip().lower() == 'nan' or valor is None:
            return ''
        return str(valor).strip()

    # Resgata o ID do plano e já passa pela limpeza
    plano_id = limpar_id(linha.get('Plano_ID'))

    # Junta o logradouro e número para não mandar 'nan'
    logradouro = limpar_texto(linha.get('End_Logradouro'))
    numero = limpar_id(linha.get('End_Numero'))
    endereco_formatado = f"{logradouro}, {numero}" if numero else logradouro

    # MONTAGEM DO PACOTE DE DADOS (PAYLOAD):
    payload = {
        "id_cliente": limpar_id(linha.get('Cliente_ID')),
        "id_contrato": limpar_id(linha.get('Login_Contrato_ID')),
        
        # --- A CORREÇÃO FINAL DO PLANO ---
        # O IXC possui duas tabelas que se cruzam: Planos e Grupos.
        # Estamos enviando nos dois campos para garantir que ele aceite.
        "id_plano": plano_id,
        "id_grupo": plano_id, 
        
        "login": limpar_login(linha.get('Login_Login')),
        "senha": str(linha.get('Login_Senha_Cliente', '')).strip(),
        "confirmar_senha": str(linha.get('Login_Senha_Cliente', '')).strip(),
        
        # --- TIPO DE CONEXÃO ---
        # F = Fibra. Também enviamos duplicado para cobrir qualquer versão do IXC.
        "tipo_conexao": "F",
        "tipo_conexao_mapa": "F",
        
        # --- CAMPOS TÉCNICOS OBRIGATÓRIOS DO IXC ---
        "autenticacao_por_mac": "P",  # P = Padrão
        "ativo": "S",                 # S = Sim
        "autenticacao": "L",          # L = Autenticação por Login/Senha
        "login_simultaneo": "1",      # Apenas 1 conexão por vez permitida
        "senha_md5": "N",             # N = Não
        "fixar_ip": "H",              # H = Herdar do plano
        "auto_preencher_ip": "H",     # H = Herdar
        "auto_preencher_mac": "H",    # H = Herdar
        "relacionar_ip_ao_login": "H",# H = Herdar
        "relacionar_mac_ao_login": "H",# H = Herdar
        "tipo_vinculo_plano": "D",    # D = Vinculado diretamente
        "endereco_padrao_cliente": "N", # N = Não (Força o IXC a ler o nosso CEP perfeito)
        
        # --- DADOS DE ENDEREÇO ---
        "cep": somente_numeros(linha.get('End_CEP')),
        "bairro": limpar_texto(linha.get('End_Bairro')),
        "cidade": limpar_id(linha.get('End_Cidade')),
        "endereco": endereco_formatado,
        "referencia": limpar_texto(linha.get('End_Referencia')),
        "obs": limpar_texto(linha.get('Obs_Cliente')) or "Importado via BackOffice Speed"
    }

    # 🚀 RAIO-X NO TERMINAL:
    # Isso vai imprimir no seu log do Docker EXATAMENTE o que está indo para o IXC.
    # Assim, se o IXC reclamar do plano de novo, nós vamos conseguir ver o porquê.
    print(f"\n--- DEBUG: ENVIANDO LOGIN {payload['login']} ---")
    print(json.dumps(payload, indent=2))
    print("---------------------------------------------------\n")

    try:
        # Envio da requisição (POST) ao IXC
        response = requests.post(endpoint, json=payload, headers=headers, verify=False)
        resposta_json = response.json()

        # Se o servidor respondeu (Status 200 = OK)
        if response.status_code == 200:
            if resposta_json.get('type') == 'success':
                return True, f"Criado com sucesso! ID IXC: {resposta_json.get('id')}"
            
            # Se a requisição chegou, mas o IXC negou
            return False, f"IXC Negou: {resposta_json.get('message')}"
        
        # Erro de rota ou indisponibilidade
        return False, f"Erro HTTP {response.status_code}"

    except Exception as e:
        # Erro de execução do Python
        return False, f"Erro Técnico: {str(e)}"