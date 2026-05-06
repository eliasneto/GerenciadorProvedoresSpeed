import os
import re
import unicodedata
from datetime import datetime
from html import unescape

from scripts.integracoes.ixc_client import IXCClient


USUARIO_IXC_PADRAO = os.getenv("IXC_DEFAULT_USER_ID", "76")
TECNICO_IXC_PADRAO = os.getenv("IXC_DEFAULT_TECNICO_ID", "84")


def normalizar_texto(valor):
    return str(valor or "").strip()


def agora_ixc():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def primeiro_preenchido(origem, chaves):
    for chave in chaves:
        valor = normalizar_texto((origem or {}).get(chave))
        if valor:
            return valor
    return ""


def buscar_os_por_id(os_id):
    client = IXCClient()
    payload = {
        "qtype": "su_oss_chamado.id",
        "query": normalizar_texto(os_id),
        "oper": "=",
        "page": "1",
        "rp": "1",
        "sortname": "su_oss_chamado.id",
        "sortorder": "desc",
    }
    status_code, body = client.listar("su_oss_chamado", payload)
    if status_code != 200 or not isinstance(body, dict):
        return {}
    registros = body.get("registros") or []
    return registros[0] if registros else {}


def buscar_registros_fechamento_os(os_id, limite=5):
    payload = {
        "qtype": "id_chamado",
        "query": normalizar_texto(os_id),
        "oper": "=",
        "page": "1",
        "rp": str(limite),
        "sortname": "id",
        "sortorder": "desc",
    }
    status_code, body = IXCClient().listar("su_oss_chamado_fechar", payload)
    if status_code != 200 or not isinstance(body, dict):
        return []
    return body.get("registros") or []


def buscar_usuarios_ixc(qtype, query, rp="10"):
    query = normalizar_texto(query)
    if not query:
        return []

    payload = {
        "qtype": qtype,
        "query": query,
        "oper": "=",
        "page": "1",
        "rp": rp,
        "sortname": "usuarios.id",
        "sortorder": "desc",
    }
    status_code, body = IXCClient().listar("usuarios", payload)
    if status_code != 200 or not isinstance(body, dict):
        return []
    return body.get("registros") or []


def resolver_usuario_ixc_por_email(email):
    email = normalizar_texto(email)
    fallback = {
        "usuario_ixc_id": USUARIO_IXC_PADRAO,
        "tecnico_ixc_id": TECNICO_IXC_PADRAO,
        "origem": "fallback",
        "fallback": True,
        "registro": {},
    }
    if not email:
        return fallback

    for qtype in ("usuarios.email", "email"):
        registros = buscar_usuarios_ixc(qtype, email)
        for registro in registros:
            if _valor_normalizado_minusculo(registro.get("email")) == email.casefold():
                return _extrair_resolucao_usuario_ixc(registro, "email_manual")

    return fallback


def _valor_normalizado_minusculo(valor):
    return normalizar_texto(valor).casefold()


def _normalizar_chave_comparacao(valor):
    texto = unicodedata.normalize("NFKD", normalizar_texto(valor))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _montar_candidatos_nome_usuario(user):
    candidatos = []
    if not user:
        return candidatos

    valores = [
        getattr(user, "first_name", ""),
        getattr(user, "get_full_name", lambda: "")(),
        getattr(user, "username", ""),
    ]
    for valor in valores:
        valor = normalizar_texto(valor)
        if valor and valor.casefold() not in {item.casefold() for item in candidatos}:
            candidatos.append(valor)
    return candidatos


def _montar_candidatos_username_usuario(user):
    candidatos = []
    username = normalizar_texto(getattr(user, "username", ""))
    email = normalizar_texto(getattr(user, "email", ""))

    for valor in [
        username,
        username.split("@", 1)[0] if "@" in username else username,
        email.split("@", 1)[0] if "@" in email else "",
    ]:
        valor = normalizar_texto(valor)
        if valor and valor.casefold() not in {item.casefold() for item in candidatos}:
            candidatos.append(valor)
    return candidatos


def _extrair_resolucao_usuario_ixc(registro, origem):
    tecnico_ixc_id = primeiro_preenchido(registro, ["funcionario"])
    if tecnico_ixc_id == "0":
        tecnico_ixc_id = ""

    return {
        "usuario_ixc_id": primeiro_preenchido(registro, ["id"]) or USUARIO_IXC_PADRAO,
        "tecnico_ixc_id": tecnico_ixc_id or TECNICO_IXC_PADRAO,
        "origem": origem,
        "fallback": False,
        "registro": registro,
    }


def resolver_usuario_ixc_por_usuario_sistema(user):
    fallback = {
        "usuario_ixc_id": USUARIO_IXC_PADRAO,
        "tecnico_ixc_id": TECNICO_IXC_PADRAO,
        "origem": "fallback",
        "fallback": True,
        "registro": {},
    }

    if not user or not getattr(user, "is_authenticated", False):
        return fallback

    email_usuario = normalizar_texto(getattr(user, "email", ""))
    if email_usuario:
        for qtype in ("usuarios.email", "email"):
            registros = buscar_usuarios_ixc(qtype, email_usuario)
            for registro in registros:
                if _valor_normalizado_minusculo(registro.get("email")) == email_usuario.casefold():
                    return _extrair_resolucao_usuario_ixc(registro, "email")

    for nome_candidato in _montar_candidatos_nome_usuario(user):
        for qtype in ("usuarios.nome", "nome"):
            registros = buscar_usuarios_ixc(qtype, nome_candidato)
            for registro in registros:
                if _valor_normalizado_minusculo(registro.get("nome")) == nome_candidato.casefold():
                    return _extrair_resolucao_usuario_ixc(registro, "nome")

    username_candidatos = _montar_candidatos_username_usuario(user)
    if username_candidatos:
        payload = {
            "qtype": "id",
            "query": "0",
            "oper": ">",
            "page": "1",
            "rp": "5000",
            "sortname": "usuarios.id",
            "sortorder": "desc",
        }
        status_code, body = IXCClient().listar("usuarios", payload)
        if status_code == 200 and isinstance(body, dict):
            registros = body.get("registros") or []
            usernames_normalizados = {_normalizar_chave_comparacao(valor) for valor in username_candidatos if valor}
            nomes_normalizados = {
                _normalizar_chave_comparacao(valor)
                for valor in _montar_candidatos_nome_usuario(user)
                if valor
            }
            for registro in registros:
                email_registro = normalizar_texto(registro.get("email"))
                email_local = email_registro.split("@", 1)[0] if "@" in email_registro else email_registro
                nome_registro = normalizar_texto(registro.get("nome"))
                chaves_registro = {
                    _normalizar_chave_comparacao(email_registro),
                    _normalizar_chave_comparacao(email_local),
                    _normalizar_chave_comparacao(nome_registro),
                }
                if chaves_registro & usernames_normalizados or chaves_registro & nomes_normalizados:
                    return _extrair_resolucao_usuario_ixc(registro, "username")

    return fallback


def limpar_html_ixc(texto):
    texto = unescape(normalizar_texto(texto))
    if not texto:
        return ""
    texto = re.sub(r"<br\\s*/?>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", "", texto)
    return re.sub(r"\s+\n", "\n", texto).strip()


def extrair_id_processo_os(detalhes_os):
    mensagem = normalizar_texto((detalhes_os or {}).get("mensagem"))
    correspondencia = re.search(r"processo\s+id:\s*(\d+)", mensagem, flags=re.IGNORECASE)
    return correspondencia.group(1) if correspondencia else ""


def resumir_erro_finalizacao(resultado):
    body = resultado.get("body") if isinstance(resultado, dict) else {}
    detalhes_os = resultado.get("detalhes_os") if isinstance(resultado, dict) else {}
    os_atualizada = resultado.get("os_atualizada") if isinstance(resultado, dict) else {}
    registro_fechamento = resultado.get("registro_fechamento") if isinstance(resultado, dict) else {}
    os_id = primeiro_preenchido(detalhes_os, ["id"])
    login_id = primeiro_preenchido(detalhes_os, ["id_login"])
    setor_id = primeiro_preenchido(detalhes_os, ["setor", "id_setor"])
    tecnico_id = primeiro_preenchido(resultado.get("payload") or {}, ["id_tecnico"])

    mensagem_bruta = ""
    if isinstance(body, dict):
        mensagem_bruta = body.get("message") or ""
    if not mensagem_bruta:
        mensagem_bruta = resultado.get("message") or "Falha ao finalizar a O.S. no IXC."

    mensagem_limpa = limpar_html_ixc(mensagem_bruta)
    mensagem_normalizada = mensagem_limpa.casefold()

    if "não está vinculado ao setor" in mensagem_normalizada or "nao esta vinculado ao setor" in mensagem_normalizada:
        return (
            f"O.S. {os_id or '--'} / login IXC {login_id or '--'}: "
            f"o IXC recusou o fechamento porque o técnico {tecnico_id or '--'} "
            f"não está vinculado ao setor {setor_id or '--'}. "
            f"Verifique o vínculo do colaborador no IXC ou ajuste o técnico usado pela integração."
        )

    if "não encontrada" in mensagem_normalizada or "nao encontrada" in mensagem_normalizada:
        return f"O.S. {os_id or '--'} não foi encontrada no IXC."

    if normalizar_texto(body.get("type")).lower() == "success":
        status_atual = primeiro_preenchido(os_atualizada, ["status"]) or "--"
        registro_id = primeiro_preenchido(registro_fechamento, ["id"]) or "--"
        return (
            f"O IXC inseriu o registro de fechamento {registro_id}, mas a O.S. {os_id or '--'} "
            f"permaneceu com status {status_atual}. O fechamento real do processo não foi concluído."
        )

    return f"O.S. {os_id or '--'} / login IXC {login_id or '--'}: {mensagem_limpa}"


def montar_payload_fechamento_real(
    detalhes_os,
    mensagem,
    usuario_ixc_id=None,
    tecnico_ixc_id=None,
    finaliza_atendimento=False,
):
    usuario_ixc_id = normalizar_texto(usuario_ixc_id) or USUARIO_IXC_PADRAO
    tecnico_ixc_id = (
        normalizar_texto(tecnico_ixc_id)
        or primeiro_preenchido(detalhes_os, ["id_tecnico"])
        or TECNICO_IXC_PADRAO
    )
    data_hora = agora_ixc()

    payload = {
        "id_chamado": primeiro_preenchido(detalhes_os, ["id"]),
        "id_tarefa_atual": primeiro_preenchido(detalhes_os, ["id_wfl_tarefa"]),
        "eh_tarefa_decisao": "N",
        "sequencia_atual": "1",
        "proxima_sequencia_forcada": "3",
        "finaliza_processo_aux": "S",
        "gera_comissao_aux": "ROS",
        "id_processo": extrair_id_processo_os(detalhes_os),
        "data_inicio": primeiro_preenchido(detalhes_os, ["data_inicio"]) or data_hora,
        "data_final": data_hora,
        "id_resposta": "0",
        "mensagem": mensagem,
        "id_tecnico": tecnico_ixc_id,
        "id_equipe": "0",
        "gera_comissao": primeiro_preenchido(detalhes_os, ["gera_comissao"]) or "S",
        "status": "F",
        "data": "",
        "id_evento": "6",
        "id_su_diagnostico": primeiro_preenchido(detalhes_os, ["id_su_diagnostico"]) or "0",
        "id_diagnostico_especifico": "0",
        "justificativa_sla_atrasado": primeiro_preenchido(detalhes_os, ["justificativa_sla_atrasado"]),
        "id_evento_status": "0",
        "id_proxima_tarefa": "0",
        "id_proxima_tarefa_aux": "",
        "latitude": primeiro_preenchido(detalhes_os, ["latitude"]),
        "longitude": primeiro_preenchido(detalhes_os, ["longitude"]),
        "gps_time": "",
        "historico": "",
        "id_operador": usuario_ixc_id,
        "finaliza_processo": "S" if finaliza_atendimento else "N",
    }
    return {chave: valor for chave, valor in payload.items() if valor is not None}


def finalizar_os_existente(
    os_id,
    mensagem,
    usuario_ixc_id=None,
    tecnico_ixc_id=None,
    finaliza_atendimento=False,
    usuario_sistema=None,
    email_ixc=None,
):
    detalhes_os = buscar_os_por_id(os_id)
    if not detalhes_os:
        return {
            "ok": False,
            "message": f"O.S. {os_id} nao encontrada no IXC.",
        }

    if normalizar_texto(detalhes_os.get("status")).upper() == "F":
        registros = buscar_registros_fechamento_os(os_id, limite=1)
        return {
            "ok": True,
            "message": f"O.S. {os_id} já está finalizada no IXC.",
            "detalhes_os": detalhes_os,
            "os_atualizada": detalhes_os,
            "registro_fechamento": registros[0] if registros else {},
        }

    resolucao_usuario = (
        resolver_usuario_ixc_por_email(email_ixc)
        if normalizar_texto(email_ixc)
        else resolver_usuario_ixc_por_usuario_sistema(usuario_sistema)
    )
    usuario_ixc_id = normalizar_texto(usuario_ixc_id) or resolucao_usuario["usuario_ixc_id"]
    tecnico_ixc_id = normalizar_texto(tecnico_ixc_id) or resolucao_usuario["tecnico_ixc_id"]

    payload = montar_payload_fechamento_real(
        detalhes_os,
        mensagem=mensagem,
        usuario_ixc_id=usuario_ixc_id,
        tecnico_ixc_id=tecnico_ixc_id,
        finaliza_atendimento=finaliza_atendimento,
    )
    endpoint = "su_oss_chamado_fechar"
    status_code, body = IXCClient().escrever(endpoint, payload)
    os_atualizada = buscar_os_por_id(os_id)
    registros_fechamento = buscar_registros_fechamento_os(os_id, limite=1)
    registro_fechamento = registros_fechamento[0] if registros_fechamento else {}
    sucesso_api = (
        status_code in (200, 201)
        and isinstance(body, dict)
        and normalizar_texto(body.get("type")).lower() == "success"
    )
    sucesso = sucesso_api and normalizar_texto(os_atualizada.get("status")).upper() == "F"
    return {
        "ok": sucesso,
        "endpoint": endpoint,
        "status_code": status_code,
        "body": body,
        "payload": payload,
        "detalhes_os": detalhes_os,
        "os_atualizada": os_atualizada,
        "registro_fechamento": registro_fechamento,
        "resolucao_usuario": resolucao_usuario,
    }
