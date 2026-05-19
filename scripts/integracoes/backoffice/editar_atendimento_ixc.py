import pandas as pd

from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    montar_identificacao_usuario_importacao,
    normalizar_id_numerico,
    limpar_texto,
)
from scripts.integracoes.ixc_client import IXCClient


CONFIRMACAO_ALTERACAO_VALIDAS = {"SIM", "S", "TRUE", "1", "CONFIRMADO", "CONFIRMAR"}
COLUNAS_OBRIGATORIAS_EDICAO_ATENDIMENTO_IXC = ["Atendimento_ID", "Confirmar_Alteracao"]
COLUNAS_OPCIONAIS_EDICAO_ATENDIMENTO_IXC = [
    "Cliente_ID",
    "Login_ID",
    "Contrato_ID",
    "Filial_ID",
    "Assunto_ID",
    "Departamento_ID",
    "Assunto_Descricao",
    "Descricao",
    "Endereco",
]

INSTRUCOES_EDICAO_ATENDIMENTO_IXC = [
    {
        "Campo": "Atendimento_ID",
        "Descricao": "ID numerico do atendimento no IXC que sera alterado.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Use apenas o ID numerico do atendimento. Ex.: 6502",
    },
    {
        "Campo": "Confirmar_Alteracao",
        "Descricao": "Confirmacao explicita para autorizar a alteracao em massa.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Digite exatamente SIM.",
    },
    {
        "Campo": "Cliente_ID",
        "Descricao": "ID do cliente vinculado ao atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser alterar o cliente vinculado.",
    },
    {
        "Campo": "Login_ID",
        "Descricao": "ID do login vinculado ao atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser alterar o login vinculado.",
    },
    {
        "Campo": "Contrato_ID",
        "Descricao": "ID do contrato vinculado ao atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser alterar o contrato vinculado.",
    },
    {
        "Campo": "Filial_ID",
        "Descricao": "ID da filial do atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Use apenas o ID numerico da filial.",
    },
    {
        "Campo": "Assunto_ID",
        "Descricao": "ID do assunto do atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Use apenas o ID numerico do assunto.",
    },
    {
        "Campo": "Departamento_ID",
        "Descricao": "ID do departamento/setor do atendimento no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Use apenas o ID numerico do departamento.",
    },
    {
        "Campo": "Assunto_Descricao",
        "Descricao": "Titulo do atendimento no IXC.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Ex.: Processo Cotacao Parceiro",
    },
    {
        "Campo": "Descricao",
        "Descricao": "Mensagem principal do atendimento no IXC.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Se informado, substitui a descricao principal do atendimento.",
    },
    {
        "Campo": "Endereco",
        "Descricao": "Texto de endereco vinculado ao atendimento no IXC.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser atualizar o endereco textual do atendimento.",
    },
]


def normalizar_confirmacao_alteracao(valor):
    texto = limpar_texto(valor).upper()
    if texto in CONFIRMACAO_ALTERACAO_VALIDAS:
        return True, None
    return False, "Confirmar_Alteracao deve ser preenchido com SIM para editar o atendimento no IXC."


def buscar_atendimento_por_id(atendimento_id):
    status_code, body = IXCClient().listar(
        "su_ticket",
        {
            "qtype": "id",
            "query": str(atendimento_id),
            "oper": "=",
            "page": "1",
            "rp": "1",
        },
    )
    if status_code != 200 or not isinstance(body, dict):
        return {}, "Nao foi possivel consultar o atendimento no IXC."

    registros = body.get("registros") or []
    if not registros:
        return {}, f"Atendimento_ID {atendimento_id} nao encontrado no IXC."

    return registros[0], None


def resposta_indica_sucesso(status_code, body):
    if not (200 <= int(status_code or 0) < 300):
        return False

    if not isinstance(body, dict):
        return True

    tipo = limpar_texto(body.get("type")).lower()
    mensagem = limpar_texto(body.get("message")).lower()
    if tipo in {"success", "sucesso"}:
        return True
    if body.get("resultado") is True:
        return True
    if any(termo in mensagem for termo in {"sucesso", "alterad", "atualiz"}):
        return True
    return False


def montar_payload_base(ticket_atual):
    chaves_base = [
        "tipo",
        "id_cliente",
        "id_login",
        "id_contrato",
        "id_filial",
        "id_assunto",
        "titulo",
        "origem_endereco",
        "origem_endereco_estrutura",
        "endereco",
        "id_wfl_processo",
        "id_ticket_setor",
        "id_usuarios",
        "prioridade",
        "menssagem",
        "interacao_pendente",
        "su_status",
        "status",
        "origem_cadastro",
        "mensagens_nao_lida_cli",
        "mensagens_nao_lida_sup",
        "id_ticket_origem",
        "melhor_horario_reserva",
    ]
    payload = {}
    for chave in chaves_base:
        valor = ticket_atual.get(chave)
        if valor not in ("", None):
            payload[chave] = valor
    return payload


def construir_payload_edicao_atendimento(linha, ticket_atual, usuario_sistema=None):
    payload = montar_payload_base(ticket_atual)
    campos_alterados = []

    cliente_id, erro = normalizar_id_numerico(linha.get("Cliente_ID"), "Cliente_ID")
    if erro:
        return {}, [], erro
    if cliente_id:
        payload["id_cliente"] = cliente_id
        campos_alterados.append("Cliente_ID")

    login_id, erro = normalizar_id_numerico(linha.get("Login_ID"), "Login_ID")
    if erro:
        return {}, [], erro
    if login_id:
        payload["id_login"] = login_id
        campos_alterados.append("Login_ID")

    contrato_id, erro = normalizar_id_numerico(linha.get("Contrato_ID"), "Contrato_ID")
    if erro:
        return {}, [], erro
    if contrato_id:
        payload["id_contrato"] = contrato_id
        campos_alterados.append("Contrato_ID")

    filial_id, erro = normalizar_id_numerico(linha.get("Filial_ID"), "Filial_ID")
    if erro:
        return {}, [], erro
    if filial_id:
        payload["id_filial"] = filial_id
        campos_alterados.append("Filial_ID")

    assunto_id, erro = normalizar_id_numerico(linha.get("Assunto_ID"), "Assunto_ID")
    if erro:
        return {}, [], erro
    if assunto_id:
        payload["id_assunto"] = assunto_id
        campos_alterados.append("Assunto_ID")

    departamento_id, erro = normalizar_id_numerico(linha.get("Departamento_ID"), "Departamento_ID")
    if erro:
        return {}, [], erro
    if departamento_id:
        payload["id_ticket_setor"] = departamento_id
        campos_alterados.append("Departamento_ID")

    titulo = limpar_texto(linha.get("Assunto_Descricao"))
    if titulo:
        payload["titulo"] = titulo
        campos_alterados.append("Assunto_Descricao")

    descricao = limpar_texto(linha.get("Descricao"))
    if descricao:
        identificacao_usuario = montar_identificacao_usuario_importacao(usuario_sistema)
        if identificacao_usuario:
            descricao = f"{descricao}\n\n{identificacao_usuario}"
        payload["menssagem"] = descricao
        campos_alterados.append("Descricao")

    endereco = limpar_texto(linha.get("Endereco"))
    if endereco:
        payload["endereco"] = endereco
        campos_alterados.append("Endereco")

    return payload, campos_alterados, None


def executar_edicao_atendimento_ixc(dados, usuario_sistema=None):
    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    atendimento_id, erro = normalizar_id_numerico(
        linha.get("Atendimento_ID"),
        "Atendimento_ID",
        obrigatorio=True,
    )
    if erro:
        return False, erro, "", ""

    confirmado, erro_confirmacao = normalizar_confirmacao_alteracao(
        linha.get("Confirmar_Alteracao")
    )
    if not confirmado:
        return False, erro_confirmacao, atendimento_id or "", ""

    ticket_atual, erro_ticket = buscar_atendimento_por_id(atendimento_id)
    if erro_ticket:
        return False, erro_ticket, atendimento_id or "", ""

    payload, campos_alterados, erro_payload = construir_payload_edicao_atendimento(
        linha,
        ticket_atual,
        usuario_sistema=usuario_sistema,
    )
    if erro_payload:
        return False, erro_payload, atendimento_id or "", ""

    if not campos_alterados:
        return False, "Nenhum campo de alteracao informado para o Atendimento_ID selecionado.", atendimento_id or "", ""

    status_code, body = IXCClient().put(f"su_ticket/{atendimento_id}", payload)
    mensagem_api = limpar_texto(body.get("message")) if isinstance(body, dict) else ""
    campos_texto = ", ".join(campos_alterados)
    if resposta_indica_sucesso(status_code, body):
        mensagem = f"Atendimento {atendimento_id} atualizado com sucesso. Campos alterados: {campos_texto}."
        if mensagem_api:
            mensagem = f"{mensagem} Retorno IXC: {mensagem_api}"
        return True, mensagem, str(atendimento_id), campos_texto

    if not mensagem_api and isinstance(body, dict):
        mensagem_api = limpar_texto(body.get("error")) or limpar_texto(body.get("raw"))
    if not mensagem_api:
        mensagem_api = f"Erro HTTP {status_code}"
    return (
        False,
        f"IXC negou a alteracao do atendimento {atendimento_id}: {mensagem_api}",
        str(atendimento_id),
        campos_texto,
    )
