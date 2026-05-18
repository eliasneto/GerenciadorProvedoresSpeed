import base64
import json
import os
import unicodedata
from pathlib import Path

import requests
from dotenv import load_dotenv

from scripts.integracoes.ixc_client import IXCClient
from scripts.integracoes.ixc_finalizacao_service import buscar_os_por_id, normalizar_texto, primeiro_preenchido


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _painel_email_env():
    return os.getenv("IXC_PANEL_EMAIL", "").strip()


def _painel_password_env():
    return os.getenv("IXC_PANEL_PASSWORD", "").strip()


def _panel_base_url():
    client = IXCClient()
    return client.base_url.replace("/webservice/v1", "").rstrip("/")


def _cabecalhos_navegacao():
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
            "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    }


def _cabecalhos_login_api(base_url):
    return {
        "User-Agent": _cabecalhos_navegacao()["User-Agent"],
        "Accept": "*/*",
        "Accept-Language": _cabecalhos_navegacao()["Accept-Language"],
        "Origin": base_url,
        "Referer": f"{base_url}/app/login",
    }


def _parse_response_json(response):
    try:
        return response.json()
    except Exception:
        try:
            return json.loads(response.text)
        except Exception:
            return {"raw": response.text}


def _extrair_tipo_autenticacao(body):
    if not isinstance(body, dict):
        return ""
    if isinstance(body.get("data"), dict):
        return normalizar_texto(body["data"].get("type")).lower()
    return normalizar_texto(body.get("type")).lower()


def _resposta_autenticacao_ok(body):
    if not isinstance(body, dict):
        return False

    status = normalizar_texto(body.get("status")).lower()
    if status and status not in {"0", "false"}:
        return True

    tipo = _extrair_tipo_autenticacao(body)
    return tipo in {"password", "redirect", "token"}


def _goto_local_autenticacao(body):
    if not isinstance(body, dict):
        return ""
    goto = body.get("goto")
    if isinstance(goto, dict):
        return normalizar_texto(goto.get("local"))
    return ""


def _texto_simples(valor):
    texto = normalizar_texto(valor)
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()


def _mensagem_autenticacao(body):
    if not isinstance(body, dict):
        return ""

    mensagens = body.get("messages")
    if isinstance(mensagens, list):
        partes = []
        for item in mensagens:
            if isinstance(item, dict):
                texto = normalizar_texto(item.get("body") or item.get("message"))
                if texto:
                    partes.append(texto)
        if partes:
            return " | ".join(partes)

    return normalizar_texto(body.get("message") or body.get("error"))


def _sessao_painel_ixc(email=None, password=None):
    email = normalizar_texto(email) or _painel_email_env()
    password = normalizar_texto(password) or _painel_password_env()

    if not email or not password:
        return None, {
            "ok": False,
            "message": "Informe Usuario IXC e Senha IXC para autenticar no painel web do IXC.",
        }

    base_url = _panel_base_url()
    client = IXCClient()
    session = requests.Session()
    login_url = f"{base_url}/api-module/auth/login"

    pagina_login = session.get(
        f"{base_url}/app/login",
        headers=_cabecalhos_navegacao(),
        verify=client.verify_ssl,
        timeout=client.timeout,
    )
    cookies_apos_login = session.cookies.get_dict()
    if not cookies_apos_login.get("IXC_Session"):
        return None, {
            "ok": False,
            "message": "Falha ao iniciar a sessao do painel web do IXC na tela /app/login.",
            "status_code": pagina_login.status_code,
            "body": pagina_login.text[:500],
            "cookies": list(cookies_apos_login.keys()),
        }

    resposta_email = session.post(
        login_url,
        files={"email": (None, email)},
        headers=_cabecalhos_login_api(base_url),
        verify=client.verify_ssl,
        timeout=client.timeout,
    )
    body_email = _parse_response_json(resposta_email)
    if not _resposta_autenticacao_ok(body_email):
        return None, {
            "ok": False,
            "message": "Falha ao validar o e-mail no login do painel do IXC.",
            "status_code": resposta_email.status_code,
            "body": body_email,
            "cookies": list(session.cookies.get_dict().keys()),
        }

    tipo_email = _extrair_tipo_autenticacao(body_email)
    body_final = body_email
    resposta_final = resposta_email

    if tipo_email == "password":
        resposta_password = session.post(
            login_url,
            files={"password": (None, password)},
            headers=_cabecalhos_login_api(base_url),
            verify=client.verify_ssl,
            timeout=client.timeout,
        )
        body_password = _parse_response_json(resposta_password)
        tipo_password = _extrair_tipo_autenticacao(body_password)
        mensagem_password = _texto_simples(_mensagem_autenticacao(body_password))

        # O IXC pode devolver "sessao ativa" na primeira tentativa e aceitar a
        # segunda submissao da senha na mesma sessao web.
        if (
            (not _resposta_autenticacao_ok(body_password) or tipo_password not in {"redirect", "token"})
            and "ja existe uma sessao ativa" in mensagem_password
        ):
            resposta_password = session.post(
                login_url,
                files={"password": (None, password)},
                headers=_cabecalhos_login_api(base_url),
                verify=client.verify_ssl,
                timeout=client.timeout,
            )
            body_password = _parse_response_json(resposta_password)
            tipo_password = _extrair_tipo_autenticacao(body_password)

        if not _resposta_autenticacao_ok(body_password) or tipo_password not in {"redirect", "token"}:
            return None, {
                "ok": False,
                "message": "Falha ao validar a senha no login do painel do IXC.",
                "status_code": resposta_password.status_code,
                "body": body_password,
                "cookies": list(session.cookies.get_dict().keys()),
            }
        body_final = body_password
        resposta_final = resposta_password

    goto_local = _goto_local_autenticacao(body_final) or "/adm.php"
    if not goto_local.startswith("/"):
        goto_local = f"/{goto_local}"

    pagina_admin = session.get(
        f"{base_url}{goto_local}",
        headers={**_cabecalhos_navegacao(), "Referer": f"{base_url}/app/login"},
        verify=client.verify_ssl,
        timeout=client.timeout,
        allow_redirects=True,
    )

    cookies = session.cookies.get_dict()
    pagina_admin_url = normalizar_texto(getattr(pagina_admin, "url", ""))
    pagina_admin_texto = normalizar_texto(getattr(pagina_admin, "text", ""))[:500].lower()
    possui_sessao_web = bool(cookies.get("IXC_Session")) and "/app/login" not in pagina_admin_url
    if not possui_sessao_web or "<title>login" in pagina_admin_texto:
        return None, {
            "ok": False,
            "message": (
                "O IXC respondeu ao login, mas nao concluiu a navegacao autenticada ate o painel /adm.php."
            ),
            "status_code": pagina_admin.status_code,
            "body": body_final,
            "cookies": list(cookies.keys()),
            "pagina_final": pagina_admin_url,
        }

    return session, {
        "ok": True,
        "status_code": resposta_final.status_code,
        "body": body_final,
        "cookies": list(cookies.keys()),
        "pagina_final": pagina_admin_url,
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
