import pandas as pd
import requests
import json
import time
import os
from decouple import config

# Pega a chave do seu arquivo .env (Atenção: o nome da variável agora é SERPER_API_KEY)
API_KEY = config('SERPER_API_KEY', default='')

def processar_planilha(caminho_entrada, caminho_saida):
    df = pd.read_excel(caminho_entrada)
    resultados = []

    print(f"Iniciando processamento de {len(df)} linhas usando Serper.dev...")

    # URL oficial do Serper para buscar lugares no Google Maps
    url = "https://google.serper.dev/places"
    
    headers = {
        'X-API-KEY': API_KEY,
        'Content-Type': 'application/json'
    }

    for index, linha in df.iterrows():
        servico = str(linha.get('Serviço', '')).strip()
        cidade = str(linha.get('Cidade', '')).strip()
        estado = str(linha.get('Estado', '')).strip()
        
        query = f"{servico} em {cidade} - {estado}"
        print(f"[{index+1}/{len(df)}] Buscando: {query}...")
        
        payload = json.dumps({
            "q": query,
            "gl": "br",     # País: Brasil
            "hl": "pt-br"   # Idioma: Português
        })
        
        try:
            # Faz a busca via Serper
            response = requests.post(url, headers=headers, data=payload)
            dados = response.json()
            
            # RAIO-X: Verifica se a API barrou a gente
            if response.status_code != 200:
                print(f"   ❌ Erro do Serper: {dados}")
                continue
            
            # Pega apenas os 5 primeiros fornecedores da lista
            lugares = dados.get('places', [])[:5]
            
            # RAIO-X: Verifica se a pesquisa não trouxe nada
            if not lugares:
                print(f"   ⚠️ API funcionou, mas não achou fornecedores. Retorno: {dados.keys()}")
            
            for lugar in lugares:
                resultados.append({
                    'Busca Original': query,
                    'Nome Fantasia': lugar.get('title', 'Não informado'),
                    'Telefone': lugar.get('phoneNumber', 'Não informado'),
                    'Site': lugar.get('website', 'Não informado'),
                    'Endereço Completo': lugar.get('address', 'Não informado'),
                    'Cidade': cidade,
                    'Estado': estado
                })
        
            # Pausa para não sobrecarregar a API
            time.sleep(1)
            
        except Exception as e:
            print(f"Erro Crítico ao processar '{query}': {e}")

    # Gera a nova planilha
    df_final = pd.DataFrame(resultados)
    df_final.to_excel(caminho_saida, index=False)
    print(f"\n✅ Automação concluída! Encontrados {len(resultados)} fornecedores.")
    print(f"📁 Arquivo salvo em: {caminho_saida}")

# --- CÓDIGO DE TESTE ISOLADO ---
if __name__ == "__main__":
    print("🛠️ Criando planilha de teste...")
    df_teste = pd.DataFrame({
        'Serviço': ['Provedor de Internet', 'Link Dedicado'],
        'Cidade': ['Fortaleza', 'Eusébio'],
        'Estado': ['CE', 'CE']
    })
    df_teste.to_excel('teste_entrada.xlsx', index=False)
    processar_planilha('teste_entrada.xlsx', 'teste_saida.xlsx')