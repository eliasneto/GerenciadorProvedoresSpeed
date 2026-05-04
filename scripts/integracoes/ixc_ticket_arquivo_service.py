import base64
import json
import os

import requests

from scripts.integracoes.ixc_client import IXCClient
from scripts.integracoes.ixc_finalizacao_service import buscar_os_por_id, normalizar_texto, primeiro_preenchido


IXC_PANEL_EMAIL = os.getenv("IXC_PANEL_EMAIL", "").strip()
IXC_PANEL_PASSWORD = os.getenv("IXC_PANEL_PASSWORD", "").strip()


def _panel_base_url():
    client = IXCClient()
    return client.base_url.replace("/webservice/v1", "").rstrip("/")


def _sessao_painel_ixc(email=None, password=None):
    email = normalizar_texto(email) or IXC_PANEL_EMAIL
    password = normalizar_texto(password) or IXC_PANEL_PASSWORD

    if not email or not password:
        return None, {
            "ok": False,
            "message": "Informe Usuario IXC e Senha IXC para enviar anexos ao atendimento no IXC.",
        }

    base_url = _panel_base_url()
    client = IXCClient()
    session = requests.Session()

    response = session.post(
        f"{base_url}/api-module/auth/login",
        json={
            "email": email,
            "password": password,
        },
        verify=client.verify_ssl,
        timeout=client.timeout,
    )

    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}

    sucesso = False
    if isinstance(body, dict):
        status = normalizar_texto(body.get("status"))
        if status and status not in {"0", "false", "False"}:
            sucesso = True
        elif "token" in body or "redirect" in body:
            sucesso = True

    if not sucesso:
        return None, {
            "ok": False,
            "message": "Falha ao autenticar no painel do IXC para envio do anexo.",
            "status_code": response.status_code,
            "body": body,
        }

    cookies = session.cookies.get_dict()
    possui_sessao_web = bool(cookies.get("IXC_Session"))
    if not possui_sessao_web:
        return None, {
            "ok": False,
            "message": (
                "O IXC respondeu ao login, mas nao abriu uma sessao web valida para upload de anexos. "
                "Isso normalmente acontece quando o endpoint de login retorna token/redirect sem criar a cookie IXC_Session."
            ),
            "status_code": response.status_code,
            "body": body,
            "cookies": list(cookies.keys()),
        }

    return session, {
        "ok": True,
        "status_code": response.status_code,
        "body": body,
        "cookies": list(cookies.keys()),
    }


def listar_arquivos_ticket(ticket_id, limite=20):
    payload = {
        "qtype": "id_ticket",
        "query": normalizar_texto(ticket_id),
        "oper": "=",
        "page": "1",
        "rp": str(limite),
        "sortname": "id",
        "sortorder": "desc",
    }
    status_code, body = IXCClient().listar("su_ticket_arquivos", payload)
    if status_code != 200 or not isinstance(body, dict):
        return []
    return body.get("registros") or []


def anexar_arquivo_ticket_ixc(ticket_id, uploaded_file, descricao=None, email_ixc=None, senha_ixc=None):
    ticket_id = normalizar_texto(ticket_id)
    if not ticket_id:
        return {
            "ok": False,
            "message": "Ticket do atendimento nao informado para envio do anexo no IXC.",
        }
    if not uploaded_file:
        return {
            "ok": False,
            "message": "Nenhum arquivo informado para envio ao atendimento no IXC.",
        }

    client = IXCClient()
    token_b64 = base64.b64encode(client.token.encode("utf-8")).decode("utf-8")
    nome_arquivo = normalizar_texto(getattr(uploaded_file, "name", "")) or "anexo"
    tipo_conteudo = getattr(uploaded_file, "content_type", None) or "application/octet-stream"
    descricao_envio = normalizar_texto(descricao) or nome_arquivo

    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    conteudo = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    response = requests.post(
        f"{client.base_url}/su_ticket_arquivos",
        data={
            "id_ticket": ticket_id,
            "descricao": descricao_envio,
            "nome_arquivo": "",
            "data_envio": "",
        },
        files={
            "local_arquivo": (nome_arquivo, conteudo, tipo_conteudo),
        },
        headers={
            "Authorization": f"Basic {token_b64}",
        },
        verify=client.verify_ssl,
        timeout=max(client.timeout, 120),
    )

    try:
        body = response.json()
    except Exception:
        try:
            body = json.loads(response.text)
        except Exception:
            body = {"raw": response.text}

    sucesso = (
        response.status_code in (200, 201)
        and isinstance(body, dict)
        and normalizar_texto(body.get("type")).lower() == "success"
    )
    registros = listar_arquivos_ticket(ticket_id, limite=5) if sucesso else []

    return {
        "ok": sucesso,
        "status_code": response.status_code,
        "body": body,
        "ticket_id": ticket_id,
        "arquivo_nome": nome_arquivo,
        "descricao": descricao_envio,
        "registros": registros,
    }


def anexar_arquivo_atendimento_por_os(os_id, uploaded_file, descricao=None, email_ixc=None, senha_ixc=None):
    detalhes_os = buscar_os_por_id(os_id)
    if not detalhes_os:
        return {
            "ok": False,
            "message": f"O.S. {os_id} nao encontrada no IXC para envio de anexo.",
        }

    ticket_id = primeiro_preenchido(detalhes_os, ["id_ticket", "id_atendimento", "id_su_ticket", "id_chamado"])
    if not ticket_id:
        return {
            "ok": False,
            "message": f"A O.S. {os_id} nao possui atendimento vinculado identificado para envio de anexo.",
            "detalhes_os": detalhes_os,
        }

    resultado = anexar_arquivo_ticket_ixc(
        ticket_id,
        uploaded_file,
        descricao=descricao,
        email_ixc=email_ixc,
        senha_ixc=senha_ixc,
    )
    resultado["detalhes_os"] = detalhes_os
    return resultado
