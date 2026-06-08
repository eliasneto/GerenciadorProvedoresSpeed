import os
import base64
import json
import re
from datetime import datetime

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IXC_URL = os.getenv("IXC_URL", "https://megainfraestrutura.com.br/webservice/v1")
IXC_TOKEN = os.getenv("IXC_TOKEN", "76:54f35af33ea35f3b8a9a8fa14868322662d0465ebbb63fc56c3fb499ac3e1b61")
USUARIO_IXC_PADRAO = "76"
MENSAGEM_CAMPO_ID_NUMERICO = (
    "deve conter apenas o ID numerico do IXC. Nao use endereco, nome ou outro texto."
)


def get_headers():
    token_b64 = base64.b64encode(IXC_TOKEN.encode()).decode()
    return {
        "Authorization": f"Basic {token_b64}",
        "Content-Type": "application/json",
    }


def limpar_id(valor):
    if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor in ("", None):
        return ""
    return str(valor).split(".")[0].strip()


def normalizar_id_numerico(valor, nome_campo, *, obrigatorio=False):
    if pd.isna(valor) or valor in ("", None):
        if obrigatorio:
            return None, f"{nome_campo} invalido"
        return "", None

    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        if obrigatorio:
            return None, f"{nome_campo} invalido"
        return "", None

    if isinstance(valor, float) and not valor.is_integer():
        return None, f"{nome_campo} {MENSAGEM_CAMPO_ID_NUMERICO}"

    if not re.fullmatch(r"\d+(?:\.0+)?", texto):
        return None, f"{nome_campo} {MENSAGEM_CAMPO_ID_NUMERICO}"

    return texto.split(".")[0].strip(), None


def limpar_texto(valor):
    if pd.isna(valor) or str(valor).strip().lower() == "nan" or valor is None:
        return ""
    return str(valor).strip()


def montar_identificacao_usuario_importacao(usuario_sistema=None):
    if not usuario_sistema or not getattr(usuario_sistema, "is_authenticated", False):
        return ""

    nome = (getattr(usuario_sistema, "get_full_name", lambda: "")() or "").strip()
    username = (getattr(usuario_sistema, "username", "") or "").strip()
    identificador = nome or username
    if not identificador:
        return ""

    if nome and username and nome != username:
        identificador = f"{nome} ({username})"

    momento = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"Importado por: {identificador} em {momento}"


def executar_abertura_atendimento(dados, usuario_sistema=None):
    endpoint_ticket = f"{IXC_URL}/su_ticket"
    headers = get_headers()

    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    id_cliente, erro = normalizar_id_numerico(
        linha.get("Cliente_ID"), "Cliente_ID", obrigatorio=True
    )
    if erro:
        return False, erro

    id_login, erro = normalizar_id_numerico(linha.get("Login_ID"), "Login_ID")
    if erro:
        return False, erro

    id_contrato, erro = normalizar_id_numerico(linha.get("Contrato_ID"), "Contrato_ID")
    if erro:
        return False, erro

    id_assunto, erro = normalizar_id_numerico(
        linha.get("Assunto_ID"), "Assunto_ID", obrigatorio=True
    )
    if erro:
        return False, erro

    id_filial, erro = normalizar_id_numerico(
        linha.get("Filial_ID"), "Filial_ID", obrigatorio=True
    )
    if erro:
        return False, erro

    id_ticket_setor, erro = normalizar_id_numerico(
        linha.get("Departamento_ID"), "Departamento_ID", obrigatorio=True
    )
    if erro:
        return False, erro

    titulo = limpar_texto(linha.get("Assunto_Descricao"))
    mensagem = limpar_texto(linha.get("Descricao"))
    endereco = limpar_texto(linha.get("Endereco"))

    if not id_login:
        id_login, erro = normalizar_id_numerico(
            linha.get("Login_Contrato_ID"), "Login_ID"
        )
        if erro:
            return False, erro

    if not id_login:
        return False, f"Login_ID invalido para cliente {id_cliente}"

    if not id_assunto:
        return False, f"Assunto_ID invalido para cliente {id_cliente}"

    if not id_filial:
        return False, f"Filial_ID invalido para cliente {id_cliente}"

    if not id_ticket_setor:
        return False, f"Departamento_ID invalido para cliente {id_cliente}"

    if not titulo:
        titulo = "Atendimento via API"

    if not mensagem:
        return False, f"Descricao vazia para cliente {id_cliente}"

    identificacao_usuario = montar_identificacao_usuario_importacao(usuario_sistema)
    if identificacao_usuario:
        mensagem = f"{mensagem}\n\n{identificacao_usuario}"

    payload = {
        "action": "novo",
        "tipo": "C",
        "id_cliente": id_cliente,
        "id_login": id_login,
        "id_contrato": id_contrato,
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
        "melhor_horario_reserva": "Q",
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
            timeout=30,
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
            return False, "Erro 401: token invalido ou sem permissao"

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
        return False, f"Erro Tecnico: {str(e)}"
