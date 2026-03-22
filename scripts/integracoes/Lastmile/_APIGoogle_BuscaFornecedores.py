import pandas as pd
import googlemaps
import time
import os
from decouple import config # Usando a mesma lib do seu settings.py

# Pega a chave do seu arquivo .env em vez de deixar exposta!
API_KEY = config('GOOGLE_MAPS_API_KEY', default='')
gmaps = googlemaps.Client(key=API_KEY)

def processar_planilha(caminho_entrada, caminho_saida):
    df = pd.read_excel(caminho_entrada)
    resultados = []

    print(f"Iniciando processamento de {len(df)} linhas...")

    # 2. Percorre cada linha da sua planilha (Ajustado para Serviço, Cidade, Estado)
    for index, linha in df.iterrows():
        # Usamos o .get() para evitar erro caso a coluna venha vazia
        servico = str(linha.get('Serviço', '')).strip()
        cidade = str(linha.get('Cidade', '')).strip()
        estado = str(linha.get('Estado', '')).strip()
        
        query = f"{servico} em {cidade} - {estado}"
        print(f"[{index+1}/{len(df)}] Buscando: {query}...")
        
        try:
            # Busca inicial (Traz até 20 resultados básicos)
            busca = gmaps.places(query=query, language='pt-BR')
            
            # O SEGREDO ESTÁ AQUI: O [:5] garante que ele pegue no máximo 5 resultados!
            for lugar in busca.get('results', [])[:5]:
                
                # Detalhes específicos (Telefone, Site, Endereço) - Isso é cobrado por requisição!
                detalhes = gmaps.place(
                    place_id=lugar['place_id'],
                    fields=['name', 'formatted_phone_number', 'website', 'address_components'],
                    language='pt-BR'
                ).get('result', {})
                
                # Extração de endereço
                comp = detalhes.get('address_components', [])
                rua = next((c['long_name'] for c in comp if 'route' in c['types']), "")
                num = next((c['long_name'] for c in comp if 'street_number' in c['types']), "")
                bairro_encontrado = next((c['long_name'] for c in comp if 'sublocality' in c['types'] or 'neighborhood' in c['types']), "")
                
                # Adiciona ao nosso banco de dados temporário
                resultados.append({
                    'Busca Original': query,
                    'Nome Fantasia': detalhes.get('name', lugar.get('name')),
                    'Telefone': detalhes.get('formatted_phone_number', 'Não informado'),
                    'Site': detalhes.get('website', 'Não informado'),
                    'Rua': rua,
                    'Numero': num,
                    'Bairro': bairro_encontrado,
                    'Cidade': cidade,
                    'Estado': estado
                })
        
            # Pausa para respeitar a API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Erro ao processar '{query}': {e}")

    # 3. Gera a nova planilha
    df_final = pd.DataFrame(resultados)
    df_final.to_excel(caminho_saida, index=False)
    print(f"\n✅ Automação concluída! Encontrados {len(resultados)} fornecedores.")
    print(f"📁 Arquivo salvo em: {caminho_saida}")


# --- COLE ISSO NO FINAL DO SEU ARQUIVO APIGoogle_BuscaFornecedores.py ---

if __name__ == "__main__":
    import os
    
    # 1. Cria dados falsos para o teste
    print("🛠️ Criando planilha de teste...")
    dados_teste = {
        'Serviço': ['Provedor de Internet', 'Link Dedicado'],
        'Cidade': ['Fortaleza', 'Eusébio'],
        'Estado': ['CE', 'CE']
    }
    
    # Transformamos o dicionário em um DataFrame do Pandas
    df_teste = pd.DataFrame(dados_teste)
    
    # Nomes dos arquivos temporários
    arquivo_entrada = 'planilha_teste_entrada.xlsx'
    arquivo_saida = 'planilha_teste_saida.xlsx'
    
    # Salva o arquivo de entrada
    df_teste.to_excel(arquivo_entrada, index=False)
    print(f"✅ Planilha {arquivo_entrada} criada com sucesso!")
    
    # 2. Roda a função principal usando o arquivo que acabamos de criar
    print("\n🚀 Iniciando a comunicação com a API do Google...")
    processar_planilha(arquivo_entrada, arquivo_saida)
    
    print(f"\n🎉 Teste finalizado! Abra o arquivo '{arquivo_saida}' no seu computador para conferir se ele trouxe os 5 fornecedores de cada cidade.")