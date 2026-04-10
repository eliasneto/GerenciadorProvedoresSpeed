import pandas as pd
import requests
import base64
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = "https://megainfraestrutura.com.br/webservice/v1"
IXC_TOKEN = "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61"
USUARIO_IXC_PADRAO = "76"


def get_headers():
    token_b64 = base64.b64encode(IXC_TOKEN.encode()).decode()
    return {
        "Authorization": f"Basic {token_b64}",
        "Content-Type": "application/json"
    }


def limpar_id(valor):
    if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor in ("", None):
        return ""
    return str(valor).split(".")[0].strip()


def limpar_texto(valor):
    if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor is None:
        return ""
    return str(valor).strip()


def executar_abertura_atendimento(dados):
    endpoint_ticket = f"{IXC_URL}/su_ticket"
    headers = get_headers()

    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    id_cliente = limpar_id(linha.get("Cliente_ID"))
    id_login = limpar_id(linha.get("Login_ID"))
    id_contrato = limpar_id(linha.get("Contrato_ID"))
    id_assunto = limpar_id(linha.get("Assunto_ID"))
    id_filial = limpar_id(linha.get("Filial_ID"))
    id_ticket_setor = limpar_id(linha.get("Departamento_ID"))

    titulo = limpar_texto(linha.get("Assunto_Descricao"))
    mensagem = limpar_texto(linha.get("Descricao"))
    endereco = limpar_texto(linha.get("Endereco"))

    if not id_login:
        id_login = limpar_id(linha.get("Login_Contrato_ID"))

    if not id_cliente:
        return False, "Cliente_ID inválido"

    if not id_login:
        return False, f"Login_ID inválido para cliente {id_cliente}"

    if not id_assunto:
        return False, f"Assunto_ID inválido para cliente {id_cliente}"

    if not id_filial:
        return False, f"Filial_ID inválido para cliente {id_cliente}"

    if not id_ticket_setor:
        return False, f"Departamento_ID inválido para cliente {id_cliente}"

    if not titulo:
        titulo = "Atendimento via API"

    if not mensagem:
        return False, f"Descrição vazia para cliente {id_cliente}"

    payload = {
        "action": "novo",
        "tipo": "C",
        "id_cliente": id_cliente,
        "id_login": id_login,
        "id_contrato": id_contrato,  # opcional
        "id_filial": id_filial,
        "id_assunto": id_assunto,
        "titulo": titulo,
        "origem_endereco": "L",
        "origem_endereco_estrutura": "E",
        "endereco": endereco,
        "id_wfl_processo": "18",
        "id_ticket_setor": id_ticket_setor,
        "id_usuarios": USUARIO_IXC_PADRAO,
        "prioridade": "M",
        "menssagem": mensagem,
        "interacao_pendente": "N",
        "su_status": "N",
        "status": "T",
        "finalizar_atendimento": "N",
        "origem_cadastro": "P",
        "mensagens_nao_lida_cli": "0",
        "mensagens_nao_lida_sup": "0",
        "id_ticket_origem": "I",
        "melhor_horario_reserva": "Q"
    }

    payload = {k: v for k, v in payload.items() if v not in ("", None)}

    print("\n--- DEBUG TICKET PAYLOAD ---")
    print("URL TICKET:", endpoint_ticket)
    print("id_cliente:", id_cliente)
    print("id_login:", id_login)
    print("id_contrato:", id_contrato)
    print("id_assunto:", id_assunto)
    print("id_filial:", id_filial)
    print("id_ticket_setor:", id_ticket_setor)
    print("id_usuarios:", USUARIO_IXC_PADRAO)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("----------------------------\n")

    try:
        response = requests.post(
            endpoint_ticket,
            json=payload,
            headers=headers,
            verify=False,
            timeout=30
        )

        print("STATUS TICKET:", response.status_code)
        print("RESPOSTA BRUTA TICKET:", response.text)

        try:
            resposta = response.json()
        except Exception:
            return False, f"Erro HTTP {response.status_code}: {response.text[:500]}"

        print("\n--- DEBUG RESPOSTA TICKET ---")
        print(json.dumps(resposta, indent=2, ensure_ascii=False))
        print("-----------------------------\n")

        if response.status_code == 401:
            return False, "Erro 401: token inválido ou sem permissão"

        if response.status_code != 200:
            return False, f"Erro HTTP {response.status_code}"

        if resposta.get("type") != "success":
            return False, f"IXC negou o ticket: {resposta.get('message')}"

        id_ticket = resposta.get("id")

        if not id_ticket:
            return False, "Ticket criado sem ID retornado pela API"

        print(f"[+] Ticket criado com sucesso. ID: {id_ticket}")

        return True, (
            f"Ticket aberto com sucesso! ID: {id_ticket} | "
            f"Aguardando workflow abrir a primeira OS automaticamente."
        )

    except Exception as e:
        return False, f"Erro Técnico: {str(e)}"