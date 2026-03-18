import pandas as pd
import requests
import base64
import urllib3
import json
import os # Sugestão: usar variáveis de ambiente

# Desativa avisos de segurança
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações (Dica: Em produção, use variáveis de ambiente ou arquivos .env)
IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"

# Criar uma sessão global melhora a performance em processamentos de muitas linhas
session = requests.Session()
token_b64 = base64.b64encode(IXC_TOKEN.encode()).decode()
session.headers.update({
    "Authorization": f"Basic {token_b64}",
    "Content-Type": "application/json"
})

def executar_abertura_atendimento(dados):
    endpoint_ticket = f"{IXC_URL}/su_ticket"

    # Limpeza de chaves e valores (Dict Comprehension eficiente)
    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    def limpar_campo(valor, is_id=False):
        """Função unificada de limpeza."""
        if pd.isna(valor) or str(valor).strip().lower() in ("nan", "", "none"):
            return ""
        texto = str(valor).strip()
        return texto.split(".")[0] if is_id else texto

    # Mapeamento de variáveis
    id_cliente = limpar_campo(linha.get("Cliente_ID"), is_id=True)
    id_ticket_setor = limpar_campo(linha.get("Departamento_ID"), is_id=True)
    mensagem = limpar_campo(linha.get("Descricao"))

    # Validações críticas
    if not mensagem:
        return False, f"Erro: Descrição vazia (Cliente {id_cliente})"
    if not id_ticket_setor:
        return False, f"Erro: Departamento ausente (Cliente {id_cliente})"

    payload = {
        "tipo": "I",
        "id_cliente": id_cliente,
        "id_login": limpar_campo(linha.get("Login_ID"), is_id=True),
        "id_assunto": limpar_campo(linha.get("Assunto_ID"), is_id=True),
        "id_filial": limpar_campo(linha.get("Filial_ID"), is_id=True),
        "prioridade": "M",
        "titulo": limpar_campo(linha.get("Assunto_Descricao")),
        "menssagem": mensagem, # Mantido conforme seu teste de sucesso
        "su_status": "N",
        "id_ticket_setor": id_ticket_setor,
        "id_wfl_processo": "18"
    }

    try:
        # Uso da 'session' em vez de 'requests' puro para reaproveitar a conexão TCP
        response = session.post(endpoint_ticket, json=payload, verify=False, timeout=25)
        
        # Tenta decodificar o JSON com tratamento de erro
        try:
            resposta = response.json()
        except ValueError:
            return False, f"Resposta inválida do servidor (Status {response.status_code})"

        # Verificação de status HTTP
        if response.status_code == 401:
            return False, "Erro de Autenticação: Token inválido"
        
        if response.status_code != 200:
            return False, f"Erro IXC (HTTP {response.status_code}): {resposta.get('message', 'Erro desconhecido')}"

        if resposta.get("type") == "success":
            return True, f"Ticket: {resposta.get('id')}"
        
        return False, f"IXC Negou: {resposta.get('message')}"

    except requests.exceptions.Timeout:
        return False, "Erro: O servidor do IXC demorou muito a responder."
    except Exception as e:
        return False, f"Erro Técnico: {str(e)}"