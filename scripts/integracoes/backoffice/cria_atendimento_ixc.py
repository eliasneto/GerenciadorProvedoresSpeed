import pandas as pd
import requests
import base64
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"


def executar_abertura_atendimento(dados):
    endpoint_ticket = f"{IXC_URL}/su_ticket"

    token_b64 = base64.b64encode(IXC_TOKEN.encode()).decode()

    headers = {
        "Authorization": f"Basic {token_b64}",
        "Content-Type": "application/json"
    }

    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    def limpar_id(valor):
        if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor in ("", None):
            return ""
        return str(valor).split(".")[0].strip()

    def limpar_texto(valor):
        if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor is None:
            return ""
        return str(valor).strip()

    id_cliente = limpar_id(linha.get("Cliente_ID"))
    id_login = limpar_id(linha.get("Login_ID"))
    id_assunto = limpar_id(linha.get("Assunto_ID"))
    id_filial = limpar_id(linha.get("Filial_ID"))
    id_ticket_setor = limpar_id(linha.get("Departamento_ID"))
    titulo = limpar_texto(linha.get("Assunto_Descricao"))
    mensagem = limpar_texto(linha.get("Descricao"))

    # validações
    if not mensagem:
        return False, f"Descrição vazia para cliente {id_cliente}"

    if not id_ticket_setor:
        return False, f"Departamento inválido para cliente {id_cliente}"

    payload = {
        "tipo": "I",
        "id_cliente": id_cliente,
        "id_login": id_login,
        "id_assunto": id_assunto,
        "id_filial": id_filial,
        "prioridade": "M",
        "titulo": titulo,
        "menssagem": mensagem,
        "su_status": "N",
        "id_ticket_setor": id_ticket_setor,
        "id_wfl_processo": "18"
    }

    print("\n--- DEBUG PAYLOAD ---")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("----------------------\n")

    try:
        response = requests.post(
            endpoint_ticket,
            json=payload,
            headers=headers,
            verify=False,
            timeout=30
        )

        try:
            resposta = response.json()
        except Exception:
            return False, f"Erro HTTP {response.status_code}: {response.text[:500]}"

        print("\n--- DEBUG RESPOSTA ---")
        print(json.dumps(resposta, indent=2, ensure_ascii=False))
        print("----------------------\n")

        if response.status_code == 401:
            return False, "Erro 401: token inválido ou sem permissão"

        if response.status_code != 200:
            return False, f"Erro HTTP {response.status_code}"

        if resposta.get("type") != "success":
            return False, f"IXC Negou: {resposta.get('message')}"

        return True, f"Ticket aberto com sucesso! ID: {resposta.get('id')}"

    except Exception as e:
        return False, f"Erro Técnico: {str(e)}"