import googlemaps
import time

# Sua chave de API
API_KEY = 'AIzaSyCtz9rsDfujX9Nhlvm1rW1hfKKCsxE3GHk'
gmaps = googlemaps.Client(key=API_KEY)

def buscar_fornecedores_completos(servico, bairro, cidade, estado):
    query = f"{servico} em {bairro}, {cidade} - {estado}"
    
    # 1. Busca a lista de locais
    # Usamos o fields para economizar (buscamos apenas o place_id primeiro)
    busca_resultado = gmaps.places(query=query, language='pt-BR')
    
    for lugar in busca_resultado.get('results', []):
        place_id = lugar['place_id']
        
        # 2. Busca os detalhes específicos deste local
        # Definimos os campos exatos para não sermos cobrados por dados que não usamos
        detalhes = gmaps.place(
            place_id=place_id,
            fields=['name', 'formatted_phone_number', 'website', 'address_components', 'formatted_address'],
            language='pt-BR'
        )['result']
        
        # Tratamento dos componentes de endereço (Rua, Número, Bairro)
        componentes = detalhes.get('address_components', [])
        rua = next((c['long_name'] for c in componentes if 'route' in c['types']), "N/A")
        numero = next((c['long_name'] for c in componentes if 'street_number' in c['types']), "S/N")
        bairro_nome = next((c['long_name'] for c in componentes if 'sublocality_level_1' in c['types']), "N/A")
        
        print(f"\n--- FORNECEDOR ENCONTRADO ---")
        print(f"Nome/Fantasia: {detalhes.get('name')}")
        print(f"Telefone: {detalhes.get('formatted_phone_number', 'Sem telefone')}")
        print(f"Site: {detalhes.get('website', 'Sem site')}")
        print(f"Endereço: {rua}, nº {numero}")
        print(f"Bairro: {bairro_nome}")
        print(f"Cidade/UF: {cidade} - {estado}")
        print(f"E-mail: [O Google não fornece e-mail diretamente]")

# Teste
buscar_fornecedores_completos("Provedor de Internet", "Aldeota", "Fortaleza", "CE")