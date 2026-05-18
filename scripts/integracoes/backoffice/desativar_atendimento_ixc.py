import pandas as pd

from scripts.integracoes.backoffice.cria_atendimento_ixc import normalizar_id_numerico
from scripts.integracoes.ixc_client import IXCClient
from scripts.integracoes.ixc_finalizacao_service import (
    finalizar_os_existente,
    normalizar_texto,
    resumir_erro_finalizacao,
)


CONFIRMACAO_DESATIVACAO_VALIDAS = {"SIM", "S", "TRUE", "1", "CONFIRMADO", "CONFIRMAR"}
MENSAGEM_PADRAO_DESATIVACAO = (
    "Atendimento encerrado administrativamente. "
    "Solicitacao tratada fora do fluxo de exclusao."
)


def limpar_texto(valor):
    if pd.isna(valor) or valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() == "nan":
        return ""
    return texto


def normalizar_confirmacao_desativacao(valor):
    texto = limpar_texto(valor).upper()
    if texto in CONFIRMACAO_DESATIVACAO_VALIDAS:
        return True, None
    return False, "Confirmar_Desativacao deve ser preenchido com SIM para finalizar o atendimento."


def _listar_registros(endpoint, qtype, query, limite="10"):
    payload = {
        "qtype": qtype,
        "query": normalizar_texto(query),
        "oper": "=",
        "page": "1",
        "rp": str(limite),
        "sortname": "id",
        "sortorder": "desc",
    }
    status_code, body = IXCClient().listar(endpoint, payload)
    if status_code != 200 or not isinstance(body, dict):
        return []
    return body.get("registros") or []


def buscar_atendimento_ixc_por_id(atendimento_id):
    for qtype in ("id", "su_ticket.id"):
        for registro in _listar_registros("su_ticket", qtype, atendimento_id, limite="1"):
            if limpar_texto(registro.get("id")) == atendimento_id:
                return registro
    return {}


def buscar_os_atendimento_ixc(atendimento_id):
    qtypes = ("id_ticket", "id_atendimento", "id_su_ticket", "id_chamado")
    registros_por_id = {}
    for qtype in qtypes:
        for registro in _listar_registros("su_oss_chamado", qtype, atendimento_id):
            os_id = limpar_texto(registro.get("id"))
            if os_id:
                registros_por_id[os_id] = registro
    return list(registros_por_id.values())


def _ordenar_os_por_id(registros):
    return sorted(
        registros,
        key=lambda registro: int(normalizar_texto(registro.get("id")) or "0"),
    )


def listar_os_para_desativacao(atendimento_id, os_id=None):
    os_id = normalizar_texto(os_id)
    if os_id:
        registros = _listar_registros("su_oss_chamado", "su_oss_chamado.id", os_id, limite="1")
        return registros[:1]

    registros = buscar_os_atendimento_ixc(atendimento_id)
    registros_abertos = [
        registro
        for registro in registros
        if normalizar_texto(registro.get("status")).upper() != "F"
    ]
    return _ordenar_os_por_id(registros_abertos)


def executar_desativacao_atendimento(dados, usuario_sistema=None):
    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    atendimento_id, erro = normalizar_id_numerico(
        linha.get("Atendimento_ID") or linha.get("ID_IXC"),
        "Atendimento_ID",
        obrigatorio=True,
    )
    if erro:
        return False, erro, ""

    os_id, erro = normalizar_id_numerico(linha.get("OS_ID"), "OS_ID")
    if erro:
        return False, erro, atendimento_id

    confirmado, erro_confirmacao = normalizar_confirmacao_desativacao(
        linha.get("Confirmar_Desativacao")
    )
    if not confirmado:
        return False, erro_confirmacao, atendimento_id

    atendimento = buscar_atendimento_ixc_por_id(atendimento_id)
    if not atendimento:
        return False, f"Atendimento {atendimento_id} nao encontrado no IXC.", atendimento_id

    if normalizar_texto(atendimento.get("status")).upper() == "F":
        return True, f"Atendimento {atendimento_id} ja esta finalizado no IXC.", atendimento_id

    os_alvos = listar_os_para_desativacao(atendimento_id, os_id=os_id)
    if not os_alvos:
        return (
            False,
            (
                f"Atendimento {atendimento_id} nao possui O.S. aberta localizada "
                "para finalizacao automatica."
            ),
            atendimento_id,
        )

    if os_id:
        os_alvo = os_alvos[0]
        os_alvo_id = normalizar_texto(os_alvo.get("id"))
        os_atendimento_id = normalizar_texto(os_alvo.get("id_ticket"))
        if os_atendimento_id and os_atendimento_id != atendimento_id:
            return (
                False,
                f"O.S. {os_alvo_id} esta vinculada ao atendimento {os_atendimento_id}, nao ao atendimento {atendimento_id}.",
                atendimento_id,
            )
    else:
        os_alvo_id = ""

    mensagem = limpar_texto(linha.get("Mensagem")) or MENSAGEM_PADRAO_DESATIVACAO
    email_ixc = limpar_texto(linha.get("Usuario_IXC"))
    resultados = []

    for indice, os_alvo in enumerate(os_alvos):
        os_alvo_id = normalizar_texto(os_alvo.get("id"))
        finaliza_atendimento = indice == len(os_alvos) - 1
        resultado = finalizar_os_existente(
            os_alvo_id,
            mensagem=mensagem,
            finaliza_atendimento=finaliza_atendimento,
            usuario_sistema=usuario_sistema,
            email_ixc=email_ixc,
        )
        resultados.append((os_alvo_id, resultado))

        if not resultado.get("ok"):
            os_sucesso = [item_id for item_id, item_resultado in resultados[:-1] if item_resultado.get("ok")]
            trecho_sucesso = (
                f" O.S. finalizadas antes da falha: {', '.join(os_sucesso)}."
                if os_sucesso
                else ""
            )
            return (
                False,
                (
                    f"Nao foi possivel finalizar o atendimento {atendimento_id}. "
                    f"O.S. com falha: {os_alvo_id}. {resumir_erro_finalizacao(resultado)}"
                    f"{trecho_sucesso}"
                ),
                atendimento_id,
            )

    atendimento_atualizado = buscar_atendimento_ixc_por_id(atendimento_id)
    atendimento_finalizado = normalizar_texto(atendimento_atualizado.get("status")).upper() == "F"
    os_ids_finalizadas = [item_id for item_id, _ in resultados]

    if atendimento_finalizado:
        registro_fechamento = (resultados[-1][1].get("registro_fechamento") or {}) if resultados else {}
        registro_id = normalizar_texto(registro_fechamento.get("id")) or "--"
        return (
            True,
            (
                f"Atendimento {atendimento_id} finalizado com sucesso. "
                f"O.S. finalizadas: {', '.join(os_ids_finalizadas)}. "
                f"Registro de fechamento: {registro_id}."
            ),
            atendimento_id,
        )

    return (
        False,
        (
            f"Nao foi possivel finalizar o atendimento {atendimento_id}. "
            f"As O.S. {', '.join(os_ids_finalizadas)} foram encerradas, mas o atendimento "
            "permaneceu aberto no IXC."
        ),
        atendimento_id,
    )
