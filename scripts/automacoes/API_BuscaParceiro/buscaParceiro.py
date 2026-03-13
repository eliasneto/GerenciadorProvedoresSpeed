import pandas as pd
import googlemaps
import time
import os

# Configurações
API_KEY = 'SUA_CHAVE_AQUI'
gmaps = googlemaps.Client(key=API_KEY)

def processar_planilha(caminho_entrada, caminho_saida):
    # 1. Lê a planilha que você carregou pelo sistema
    df = pd.read_excel(caminho_entrada)
    
    # Lista para armazenar os resultados
    resultados = []

    print(f"Iniciando processamento de {len(df)} linhas...")

    # 2. Percorre cada linha da sua planilha (Ex: colunas 'Servico', 'Bairro', 'Cidade', 'UF')
    for index, linha in df.iterrows():
        servico = linha['Servico']
        bairro = linha['Bairro']
        cidade = linha['Cidade']
        uf = linha['UF']
        
        query = f"{servico} em {bairro}, {cidade} - {uf}"
        
        try:
            # Busca inicial
            busca = gmaps.places(query=query, language='pt-BR')
            
            for lugar in busca.get('results', []):
                # Detalhes específicos (Telefone, Site, Endereço)
                detalhes = gmaps.place(
                    place_id=lugar['place_id'],
                    fields=['name', 'formatted_phone_number', 'website', 'address_components'],
                    language='pt-BR'
                )['result']
                
                # Extração de endereço
                comp = detalhes.get('address_components', [])
                rua = next((c['long_name'] for c in comp if 'route' in c['types']), "")
                num = next((c['long_name'] for c in comp if 'street_number' in c['types']), "")
                
                # Adiciona ao nosso "banco de dados" temporário
                resultados.append({
                    'Busca Original': query,
                    'Nome Fantasia': detalhes.get('name'),
                    'Telefone': detalhes.get('formatted_phone_number'),
                    'Site': detalhes.get('website'),
                    'Rua': rua,
                    'Numero': num,
                    'Bairro': bairro,
                    'Cidade': cidade,
                    'UF': uf
                })
            
            # Pequena pausa para respeitar a API e não queimar créditos por erro
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Erro ao processar {query}: {e}")

    # 3. Gera a nova planilha com os dados encontrados
    df_final = pd.DataFrame(resultados)
    df_final.to_excel(caminho_saida, index=False)
    print(f"Automação concluída! Arquivo salvo em: {caminho_saida}")

# Exemplo de chamada que o seu sistema faria
# processar_planilha('upload_usuario.xlsx', 'resultado_fornecedores.xlsx')