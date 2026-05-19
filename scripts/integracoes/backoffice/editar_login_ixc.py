import re
import unicodedata

import pandas as pd

from scripts.integracoes.backoffice.cria_atendimento_ixc import normalizar_id_numerico
from scripts.integracoes.backoffice.cria_login_atendimento import (
    _atualizar_endereco_tecnico,
)
from scripts.integracoes.ixc_client import IXCClient


CONFIRMACAO_ALTERACAO_VALIDAS = {"SIM", "S", "TRUE", "1", "CONFIRMADO", "CONFIRMAR"}
COLUNAS_OBRIGATORIAS_EDICAO_LOGIN_IXC = ["Login_ID", "Confirmar_Alteracao"]
COLUNAS_OPCIONAIS_EDICAO_LOGIN_IXC = [
    "Cliente_ID",
    "Login_Contrato_ID",
    "Plano_ID",
    "Login_Login",
    "Login_Senha_Cliente",
    "End_CEP",
    "End_Bairro",
    "End_Cidade_ID_IXC",
    "End_Logradouro",
    "End_Numero",
    "End_Referencia",
    "Obs_Cliente",
    "VELOCIDADE",
    "TIPO DE ACESSO",
    "BLOCO IP",
    "DUPLA ABORDAGEM",
    "ENTREGA RB",
]

MAPA_CAMPOS_TECNICOS_OBS = {
    "VELOCIDADE": "VELOCIDADE",
    "TIPO DE ACESSO": "TIPO DE ACESSO",
    "BLOCO IP": "BLOCO IP",
    "DUPLA ABORDAGEM": "DUPLA ABORDAGEM",
    "ENTREGA RB": "ENTREGA RB",
}

INSTRUCOES_EDICAO_LOGIN_IXC = [
    {
        "Campo": "Login_ID",
        "Descricao": "ID numerico do login no IXC que sera alterado.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Sim",
        "Regras / Exemplo": "Use apenas o ID do login no IXC. Ex.: 4441",
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
        "Descricao": "ID do cliente vinculado ao login no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser alterar o cliente vinculado.",
    },
    {
        "Campo": "Login_Contrato_ID",
        "Descricao": "ID do contrato do login no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Opcional. Informe apenas se quiser alterar o contrato vinculado.",
    },
    {
        "Campo": "Plano_ID",
        "Descricao": "ID do plano/grupo do login no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Se informado, a automacao atualiza `id_plano` e `id_grupo` com o mesmo valor.",
    },
    {
        "Campo": "Login_Login",
        "Descricao": "Nome do login PPPoE no IXC.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Aceita apenas letras, numeros, traco e underscore. Ex.: cliente_teste",
    },
    {
        "Campo": "Login_Senha_Cliente",
        "Descricao": "Senha do login no IXC.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Se informado, a automacao envia a senha e a confirmacao com o mesmo valor.",
    },
    {
        "Campo": "End_CEP",
        "Descricao": "CEP do endereco do login.",
        "Tipo de dado": "Texto numerico",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Aceita com ou sem mascara. Ex.: 60346165",
    },
    {
        "Campo": "End_Bairro",
        "Descricao": "Bairro do endereco do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Ex.: MESSEJANA",
    },
    {
        "Campo": "End_Cidade_ID_IXC",
        "Descricao": "ID numerico da cidade no IXC.",
        "Tipo de dado": "Numero inteiro",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Use apenas o ID numerico da cidade. Ex.: 948",
    },
    {
        "Campo": "End_Logradouro",
        "Descricao": "Logradouro do endereco do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Ex.: RUA CANARIO",
    },
    {
        "Campo": "End_Numero",
        "Descricao": "Numero do endereco do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Ex.: 120 ou SN",
    },
    {
        "Campo": "End_Referencia",
        "Descricao": "Referencia adicional do endereco do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Ex.: PROXIMO AO POSTO",
    },
    {
        "Campo": "Obs_Cliente",
        "Descricao": "Bloco principal de observacao do login no IXC.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Se informado, substitui o texto livre principal e preserva os campos tecnicos nao alterados.",
    },
    {
        "Campo": "VELOCIDADE",
        "Descricao": "Linha tecnica de velocidade gravada na observacao do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Atualiza ou adiciona `VELOCIDADE: valor` dentro da observacao.",
    },
    {
        "Campo": "TIPO DE ACESSO",
        "Descricao": "Linha tecnica de tipo de acesso gravada na observacao do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Atualiza ou adiciona `TIPO DE ACESSO: valor` dentro da observacao.",
    },
    {
        "Campo": "BLOCO IP",
        "Descricao": "Linha tecnica de bloco IP gravada na observacao do login.",
        "Tipo de dado": "Texto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Atualiza ou adiciona `BLOCO IP: valor` dentro da observacao.",
    },
    {
        "Campo": "DUPLA ABORDAGEM",
        "Descricao": "Linha tecnica de dupla abordagem gravada na observacao do login.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Use Sim ou Nao. A automacao padroniza o valor antes de salvar.",
    },
    {
        "Campo": "ENTREGA RB",
        "Descricao": "Linha tecnica de entrega RB gravada na observacao do login.",
        "Tipo de dado": "Texto curto",
        "Obrigatorio?": "Nao",
        "Regras / Exemplo": "Use Sim ou Nao. A automacao padroniza o valor antes de salvar.",
    },
]


def limpar_texto(valor):
    if pd.isna(valor) or valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() == "nan":
        return ""
    return texto


def normalizar_confirmacao_alteracao(valor):
    texto = limpar_texto(valor).upper()
    if texto in CONFIRMACAO_ALTERACAO_VALIDAS:
        return True, None
    return False, "Confirmar_Alteracao deve ser preenchido com SIM para editar o login no IXC."


def limpar_login(texto):
    texto = limpar_texto(texto)
    if not texto:
        return ""
    texto = texto.replace(" ", "")
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8")
    return re.sub(r"[^a-zA-Z0-9_-]", "", texto)


def normalizar_cep(valor):
    texto = limpar_texto(valor)
    if not texto:
        return ""
    digitos = re.sub(r"[^0-9]", "", texto)
    if not digitos:
        return ""
    if len(digitos) == 8:
        return f"{digitos[:5]}-{digitos[5:]}"
    return digitos.zfill(8)


def normalizar_numero(valor):
    texto = limpar_texto(valor)
    if not texto:
        return ""
    return texto.split(".")[0].strip()


def normalizar_sim_nao(valor):
    texto = limpar_texto(valor).lower()
    if texto in {"sim", "s", "yes", "y", "true", "1"}:
        return "Sim"
    if texto in {"nao", "não", "n", "no", "false", "0"}:
        return "Nao"
    return limpar_texto(valor)


def buscar_login_ixc_por_id(login_id):
    status_code, body = IXCClient().listar(
        "radusuarios",
        {
            "qtype": "id",
            "query": str(login_id),
            "oper": "=",
            "page": "1",
            "rp": "1",
        },
    )
    if status_code != 200 or not isinstance(body, dict):
        return {}, "Nao foi possivel consultar o login no IXC."

    registros = body.get("registros") or []
    if not registros:
        return {}, f"Login_ID {login_id} nao encontrado no IXC."

    return registros[0], None


def _quebrar_observacao_existente(obs_atual):
    linhas_livres = []
    campos_tecnicos = {}

    for linha in limpar_texto(obs_atual).splitlines():
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue

        if ":" not in linha_limpa:
            linhas_livres.append(linha_limpa)
            continue

        chave_bruta, valor_bruto = linha_limpa.split(":", 1)
        chave = chave_bruta.strip().upper()
        valor = valor_bruto.strip()
        if chave in MAPA_CAMPOS_TECNICOS_OBS:
            campos_tecnicos[chave] = valor
        else:
            linhas_livres.append(linha_limpa)

    return linhas_livres, campos_tecnicos


def montar_observacao_atualizada(linha, login_atual):
    colunas_presentes = {str(chave).strip() for chave in linha.keys()}
    obs_cliente = limpar_texto(linha.get("Obs_Cliente"))
    alterou_observacao = bool(obs_cliente)
    alterou_tecnico = any(limpar_texto(linha.get(campo)) for campo in MAPA_CAMPOS_TECNICOS_OBS)
    if not alterou_observacao and not alterou_tecnico:
        return "", False

    linhas_livres, campos_tecnicos = _quebrar_observacao_existente(login_atual.get("obs"))

    if alterou_observacao and obs_cliente:
        linhas_livres = [obs_cliente]

    for campo in MAPA_CAMPOS_TECNICOS_OBS:
        if campo not in colunas_presentes:
            continue
        valor = limpar_texto(linha.get(campo))
        if not valor:
            continue
        if campo in {"DUPLA ABORDAGEM", "ENTREGA RB"}:
            valor = normalizar_sim_nao(valor)
        campos_tecnicos[campo] = valor

    linhas_finais = list(linhas_livres)
    for campo in MAPA_CAMPOS_TECNICOS_OBS:
        valor = limpar_texto(campos_tecnicos.get(campo))
        if valor:
            linhas_finais.append(f"{campo}: {valor}")

    return "\n".join(linhas_finais).strip(), True


def construir_payload_edicao_login_ixc(linha, login_atual):
    payload = {}
    campos_alterados = []

    cliente_id, erro = normalizar_id_numerico(linha.get("Cliente_ID"), "Cliente_ID")
    if erro:
        return {}, [], erro
    if cliente_id:
        payload["id_cliente"] = cliente_id
        campos_alterados.append("Cliente_ID")

    contrato_id, erro = normalizar_id_numerico(linha.get("Login_Contrato_ID"), "Login_Contrato_ID")
    if erro:
        return {}, [], erro
    if contrato_id:
        payload["id_contrato"] = contrato_id
        campos_alterados.append("Login_Contrato_ID")

    plano_id, erro = normalizar_id_numerico(linha.get("Plano_ID"), "Plano_ID")
    if erro:
        return {}, [], erro
    if plano_id:
        payload["id_plano"] = plano_id
        payload["id_grupo"] = plano_id
        campos_alterados.append("Plano_ID")

    login_login = limpar_login(linha.get("Login_Login"))
    if login_login:
        payload["login"] = login_login
        campos_alterados.append("Login_Login")

    senha = limpar_texto(linha.get("Login_Senha_Cliente"))
    if senha:
        payload["senha"] = senha
        payload["confirmar_senha"] = senha
        campos_alterados.append("Login_Senha_Cliente")

    cep = normalizar_cep(linha.get("End_CEP"))
    if cep:
        payload["cep"] = cep
        campos_alterados.append("End_CEP")

    bairro = limpar_texto(linha.get("End_Bairro"))
    if bairro:
        payload["bairro"] = bairro
        campos_alterados.append("End_Bairro")

    cidade_id, erro = normalizar_id_numerico(linha.get("End_Cidade_ID_IXC"), "End_Cidade_ID_IXC")
    if erro:
        return {}, [], erro
    if cidade_id:
        payload["cidade"] = cidade_id
        campos_alterados.append("End_Cidade_ID_IXC")

    logradouro = limpar_texto(linha.get("End_Logradouro"))
    if logradouro:
        payload["endereco"] = logradouro
        campos_alterados.append("End_Logradouro")

    numero = normalizar_numero(linha.get("End_Numero"))
    if numero:
        payload["numero"] = numero
        campos_alterados.append("End_Numero")

    referencia = limpar_texto(linha.get("End_Referencia"))
    if referencia:
        payload["referencia"] = referencia
        campos_alterados.append("End_Referencia")

    obs_final, houve_bloco_obs = montar_observacao_atualizada(linha, login_atual)
    if houve_bloco_obs:
        payload["obs"] = obs_final
        for campo in ["Obs_Cliente", *MAPA_CAMPOS_TECNICOS_OBS.keys()]:
            if str(campo) in {str(chave).strip() for chave in linha.keys()} and campo not in campos_alterados:
                campos_alterados.append(campo)

    return payload, campos_alterados, None


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


def executar_edicao_login_ixc(dados):
    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    login_id, erro = normalizar_id_numerico(linha.get("Login_ID"), "Login_ID", obrigatorio=True)
    if erro:
        return False, erro, "", ""

    confirmado, erro_confirmacao = normalizar_confirmacao_alteracao(
        linha.get("Confirmar_Alteracao")
    )
    if not confirmado:
        return False, erro_confirmacao, login_id or "", ""

    login_atual, erro_login = buscar_login_ixc_por_id(login_id)
    if erro_login:
        return False, erro_login, login_id or "", ""

    payload, campos_alterados, erro_payload = construir_payload_edicao_login_ixc(linha, login_atual)
    if erro_payload:
        return False, erro_payload, login_id or "", ""

    if not campos_alterados:
        return False, "Nenhum campo de alteracao informado para o Login_ID selecionado.", login_id or "", ""

    status_code, body = IXCClient().put(f"radusuarios/{login_id}", payload)
    mensagem_api = limpar_texto(body.get("message")) if isinstance(body, dict) else ""
    campos_texto = ", ".join(campos_alterados)
    if resposta_indica_sucesso(status_code, body):
        linha_local = dict(linha)
        linha_local.setdefault("Login_Login", payload.get("login") or login_atual.get("login"))
        linha_local.setdefault("Cliente_ID", payload.get("id_cliente") or login_atual.get("id_cliente"))
        linha_local.setdefault("End_Logradouro", payload.get("endereco") or login_atual.get("endereco"))
        linha_local.setdefault("End_Numero", payload.get("numero") or login_atual.get("numero"))
        linha_local.setdefault("End_Bairro", payload.get("bairro") or login_atual.get("bairro"))
        linha_local.setdefault("End_Cidade_ID_IXC", payload.get("cidade") or login_atual.get("cidade"))
        if "obs" in payload:
            _atualizar_endereco_tecnico(linha_local, payload["obs"])

        mensagem = f"Login {login_id} atualizado com sucesso. Campos alterados: {campos_texto}."
        if mensagem_api:
            mensagem = f"{mensagem} Retorno IXC: {mensagem_api}"
        return True, mensagem, str(login_id), campos_texto

    if not mensagem_api and isinstance(body, dict):
        mensagem_api = limpar_texto(body.get("error")) or limpar_texto(body.get("raw"))
    if not mensagem_api:
        mensagem_api = f"Erro HTTP {status_code}"
    return (
        False,
        f"IXC negou a alteracao do login {login_id}: {mensagem_api}",
        str(login_id),
        campos_texto,
    )
