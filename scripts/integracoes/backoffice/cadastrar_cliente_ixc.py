import re
from datetime import datetime

import pandas as pd

from scripts.integracoes.backoffice.cria_atendimento_ixc import normalizar_id_numerico
from scripts.integracoes.ixc_client import IXCClient
from scripts.integracoes.ixc_finalizacao_service import normalizar_texto


CONFIRMACAO_CADASTRO_VALIDAS = {"SIM", "S", "TRUE", "1", "CONFIRMADO", "CONFIRMAR"}


def limpar_texto(valor):
    if pd.isna(valor) or valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() == "nan":
        return ""
    return texto


def normalizar_confirmacao_cadastro(valor):
    texto = limpar_texto(valor).upper()
    if texto in CONFIRMACAO_CADASTRO_VALIDAS:
        return True, None
    return False, "Confirmar_Cadastro deve ser preenchido com SIM para criar o cliente no IXC."


def somente_digitos(valor):
    return re.sub(r"\D", "", limpar_texto(valor))


def formatar_documento_ixc(valor):
    digitos = somente_digitos(valor)
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return limpar_texto(valor)


def normalizar_cep(valor):
    digitos = somente_digitos(valor)
    if not digitos:
        return ""
    if len(digitos) == 8:
        return f"{digitos[:5]}-{digitos[5:]}"
    return digitos


def normalizar_telefone(valor):
    texto = limpar_texto(valor)
    if not texto:
        return ""

    digitos = somente_digitos(texto)
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return texto


def normalizar_numero_endereco(valor):
    texto = limpar_texto(valor).upper()
    if not texto:
        return "SN"
    if texto in {"S/N", "S.N", "SEM NUMERO", "SEM NUMERO.", "SN"}:
        return "SN"
    return texto


def inferir_tipo_pessoa(documento, valor_informado=""):
    tipo = limpar_texto(valor_informado).upper()
    if tipo in {"F", "PF", "FISICA", "FISICA/PF"}:
        return "F"
    if tipo in {"J", "PJ", "JURIDICA", "JURIDICA/PJ"}:
        return "J"

    if len(somente_digitos(documento)) == 11:
        return "F"
    return "J"


def normalizar_prospeccao(valor):
    texto = limpar_texto(valor).upper()
    if texto in {"SIM", "S", "TRUE", "1"}:
        return "S"
    if texto in {"NAO", "NAO", "N", "FALSE", "0", "NÃO"}:
        return "N"
    return ""


def normalizar_contribuinte_icms(valor, tipo_pessoa, ie_rg):
    texto = limpar_texto(valor).upper()
    if texto in {"SIM", "S", "TRUE", "1"}:
        return "S"
    if texto in {"NAO", "N", "FALSE", "0"}:
        return "N"
    if texto in {"ISENTO", "I"}:
        return "I"

    if tipo_pessoa == "F":
        return "N"
    if limpar_texto(ie_rg).upper() == "ISENTO":
        return "I"
    if limpar_texto(ie_rg):
        return "S"
    return "N"


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


def buscar_cliente_por_cnpj_cpf(cnpj_cpf):
    documento = somente_digitos(cnpj_cpf)
    if not documento:
        return {}

    for consulta in {documento, limpar_texto(cnpj_cpf), formatar_documento_ixc(cnpj_cpf)}:
        if not consulta:
            continue
        for qtype in ("cnpj_cpf", "cliente.cnpj_cpf"):
            registros = _listar_registros("cliente", qtype, consulta, limite="5")
            for registro in registros:
                if somente_digitos(registro.get("cnpj_cpf")) == documento:
                    return registro
    return {}


def buscar_cliente_por_razao_social(razao_social):
    razao_social = limpar_texto(razao_social)
    if not razao_social:
        return {}

    for qtype in ("razao", "cliente.razao"):
        registros = _listar_registros("cliente", qtype, razao_social, limite="5")
        for registro in registros:
            if limpar_texto(registro.get("razao")).casefold() == razao_social.casefold():
                return registro
    return {}


def _normalizar_uf(valor):
    return limpar_texto(valor).upper()


def resolver_cidade_ixc(cidade_id=None):
    cidade_id = limpar_texto(cidade_id)
    if cidade_id:
        registro = {}
        for qtype in ("id", "cidade.id"):
            registros = _listar_registros("cidade", qtype, cidade_id, limite="1")
            if registros:
                registro = registros[0]
                break
        if not registro:
            return "", "", f"Cidade_ID_IXC {cidade_id} nao encontrada no IXC."
        uf_id = limpar_texto(registro.get("id_uf") or registro.get("uf"))
        return limpar_texto(registro.get("id")), uf_id, None
    return "", "", "Cidade_ID_IXC obrigatorio para cadastrar o cliente no IXC."


def montar_payload_cliente_ixc(linha, cidade_id_ixc, uf_id_ixc=""):
    documento = somente_digitos(linha.get("CNPJ_CPF"))
    tipo_pessoa = inferir_tipo_pessoa(documento, linha.get("Tipo_Pessoa"))
    ie_rg = limpar_texto(linha.get("IE_RG"))
    telefone = normalizar_telefone(linha.get("Telefone"))
    email = limpar_texto(linha.get("Email") or linha.get("EMAIL"))
    ativo = "S" if limpar_texto(linha.get("Ativo")).upper() not in {"N", "NAO", "NAO", "FALSE", "0"} else "N"
    prospeccao = normalizar_prospeccao(linha.get("Prospeccao"))
    hoje = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "ativo": ativo,
        "tipo_pessoa": tipo_pessoa,
        "razao": limpar_texto(linha.get("Razao_Social") or linha.get("RAZAO_SOCIAL")),
        "fantasia": limpar_texto(linha.get("Nome_Fantasia") or linha.get("NOME_FANTASIA")),
        "cnpj_cpf": formatar_documento_ixc(documento),
        "ie_rg": ie_rg,
        "contribuinte_icms": normalizar_contribuinte_icms(
            linha.get("Contribuinte_ICMS"),
            tipo_pessoa,
            ie_rg,
        ),
        "data_cadastro": hoje,
        "data_nascimento": "0000-00-00",
        "cob_envia_email": "S",
        "cob_envia_sms": "S",
        "crm_data_novo": hoje,
        "convert_cliente_forn": "N",
        "cep": normalizar_cep(linha.get("CEP")),
        "endereco": limpar_texto(linha.get("Endereco") or linha.get("ENDERECO")),
        "numero": normalizar_numero_endereco(linha.get("Numero") or linha.get("NUMERO")),
        "bairro": limpar_texto(linha.get("Bairro") or linha.get("BAIRRO")),
        "cidade": cidade_id_ixc,
        "uf": uf_id_ixc,
        "complemento": limpar_texto(linha.get("Complemento")),
        "referencia": limpar_texto(linha.get("Referencia")),
        "contato": limpar_texto(linha.get("Contato_Nome") or linha.get("CONTATO_NOME")),
        "email": email,
        "fone": telefone,
        "telefone_comercial": telefone,
        "telefone_celular": telefone,
        "whatsapp": telefone,
        "obs": limpar_texto(linha.get("Observacao") or linha.get("Obs")),
        "prospeccao": prospeccao,
    }

    tipo_cliente_id, _ = normalizar_id_numerico(linha.get("Tipo_Cliente_ID"), "Tipo_Cliente_ID")
    tipo_assinante_id, _ = normalizar_id_numerico(linha.get("Tipo_Assinante_ID"), "Tipo_Assinante_ID")
    filial_id, _ = normalizar_id_numerico(linha.get("Filial_ID"), "Filial_ID")
    vendedor_id, _ = normalizar_id_numerico(linha.get("Vendedor_ID"), "Vendedor_ID")

    if tipo_cliente_id:
        payload["id_tipo_cliente"] = tipo_cliente_id
    payload["tipo_assinante"] = tipo_assinante_id or "3"
    classificacao_iss_raw = limpar_texto(
        linha.get("Tipo_Cliente_Fiscal") or linha.get("Classificacao_ISS")
    )
    if classificacao_iss_raw:
        try:
            classificacao_iss = str(int(classificacao_iss_raw)).zfill(2)
        except ValueError:
            classificacao_iss = classificacao_iss_raw
    else:
        classificacao_iss = "99"
    payload["iss_classificacao_padrao"] = classificacao_iss
    tipo_localidade_raw = limpar_texto(linha.get("Tipo_Localidade")).upper()
    payload["tipo_localidade"] = tipo_localidade_raw if tipo_localidade_raw in {"U", "R"} else "U"
    payload["filial_id"] = filial_id or "1"
    if vendedor_id:
        payload["id_vendedor"] = vendedor_id

    return {chave: valor for chave, valor in payload.items() if valor not in (None, "")}


def executar_cadastro_cliente_ixc(dados):
    linha = {str(k).replace("\ufeff", "").strip(): v for k, v in dados.items()}

    razao_social = limpar_texto(linha.get("Razao_Social") or linha.get("RAZAO_SOCIAL"))
    documento = somente_digitos(linha.get("CNPJ_CPF"))
    if not razao_social:
        return False, "Razao_Social obrigatoria para cadastro do cliente.", ""
    if not documento:
        return False, "CNPJ_CPF obrigatorio para cadastro do cliente.", ""

    confirmado, erro_confirmacao = normalizar_confirmacao_cadastro(
        linha.get("Confirmar_Cadastro")
    )
    if not confirmado:
        return False, erro_confirmacao, ""

    cidade_id_ixc, uf_id_ixc, erro_cidade = resolver_cidade_ixc(linha.get("Cidade_ID_IXC"))
    if erro_cidade:
        return False, erro_cidade, ""

    permitir_duplicidade = limpar_texto(linha.get("Permitir_Duplicidade")).upper() in {"SIM", "S", "TRUE", "1"}
    if not permitir_duplicidade:
        cliente_existente = buscar_cliente_por_cnpj_cpf(documento)
        if not cliente_existente:
            cliente_existente = buscar_cliente_por_razao_social(razao_social)
        if cliente_existente:
            cliente_ixc_id = limpar_texto(cliente_existente.get("id"))
            return (
                True,
                f"Cliente ja existente no IXC (ID {cliente_ixc_id}). Nenhuma alteracao feita para {razao_social}.",
                cliente_ixc_id,
            )

    if not limpar_texto(linha.get("Email") or linha.get("EMAIL")):
        return False, "Email obrigatorio para cadastro do cliente no IXC.", ""
    if not limpar_texto(linha.get("Telefone")):
        return False, "Telefone obrigatorio para cadastro do cliente no IXC.", ""

    payload = montar_payload_cliente_ixc(linha, cidade_id_ixc, uf_id_ixc)
    status_code, body = IXCClient().escrever("cliente", payload)

    cliente_ixc_id = ""
    if isinstance(body, dict):
        cliente_ixc_id = limpar_texto(body.get("id"))

    if not cliente_ixc_id:
        cliente_criado = buscar_cliente_por_cnpj_cpf(documento)
        cliente_ixc_id = limpar_texto(cliente_criado.get("id"))

    sucesso = (
        status_code in (200, 201)
        and isinstance(body, dict)
        and limpar_texto(body.get("type")).lower() == "success"
    )

    if sucesso:
        return (
            True,
            f"Cliente {razao_social} cadastrado com sucesso no IXC. ID {cliente_ixc_id or '--'}.",
            cliente_ixc_id,
        )

    mensagem = ""
    if isinstance(body, dict):
        mensagem = limpar_texto(body.get("message")) or limpar_texto(body.get("error"))
    if not mensagem:
        mensagem = f"IXC retornou HTTP {status_code} ao tentar cadastrar o cliente."

    return False, f"Nao foi possivel cadastrar {razao_social} no IXC. {mensagem}", cliente_ixc_id
