import re
from datetime import datetime

import pandas as pd

from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    montar_identificacao_usuario_importacao,
    normalizar_id_numerico,
)
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


_PADRAO_CEP = re.compile(r"\d{5}[-\s]{0,2}\d{3}")


def extrair_logradouro(valor):
    """Extrai apenas o logradouro quando o campo vem com endereço completo concatenado.

    Formato típico: 'NOME DA RUA, 123 BAIRRO. 00000-000 Cidade - UF.'
    Se o campo contém um CEP embutido (incluindo CEPs quebrados por newline),
    tudo a partir da primeira vírgula é descartado, restando só o logradouro.
    Caso contrário, retorna o valor limpo sem alteração.
    Sempre limita a 40 caracteres (limite do campo Street no SAP).
    """
    texto = limpar_texto(valor)
    # Normaliza quebras de linha para não quebrar a detecção de CEP
    texto_normalizado = re.sub(r"[\r\n]+", " ", texto)
    if _PADRAO_CEP.search(texto_normalizado):
        if "," in texto_normalizado:
            texto_normalizado = texto_normalizado.split(",")[0]
    return texto_normalizado.strip()[:40]


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
        "endereco": extrair_logradouro(linha.get("Endereco") or linha.get("ENDERECO")),
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

    payload["id_tipo_cliente"] = tipo_cliente_id
    payload["tipo_assinante"] = tipo_assinante_id
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
    payload["filial_id"] = filial_id
    if vendedor_id:
        payload["id_vendedor"] = vendedor_id

    return {chave: valor for chave, valor in payload.items() if valor not in (None, "")}


def _calcular_digito_verificador(digitos, pesos):
    soma = sum(d * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(digitos_str):
    if len(digitos_str) != 11 or len(set(digitos_str)) == 1:
        return False
    d = [int(c) for c in digitos_str]
    d1 = _calcular_digito_verificador(d[:9], range(10, 1, -1))
    d2 = _calcular_digito_verificador(d[:10], range(11, 1, -1))
    return d[9] == d1 and d[10] == d2


def validar_cnpj(digitos_str):
    if len(digitos_str) != 14 or len(set(digitos_str)) == 1:
        return False
    d = [int(c) for c in digitos_str]
    d1 = _calcular_digito_verificador(d[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _calcular_digito_verificador(d[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d[12] == d1 and d[13] == d2


def validar_documento_fiscal(valor):
    digitos = somente_digitos(valor)
    if not digitos:
        return True, None
    if len(digitos) == 11:
        ok = validar_cpf(digitos)
        return ok, (None if ok else f"CPF '{digitos}' invalido — digitos verificadores nao conferem.")
    if len(digitos) == 14:
        ok = validar_cnpj(digitos)
        return ok, (None if ok else f"CNPJ '{digitos}' invalido — digitos verificadores nao conferem.")
    return False, f"CNPJ_CPF invalido: esperado 11 digitos (CPF) ou 14 digitos (CNPJ), encontrado {len(digitos)}."


def _ordenar_ids(ids):
    return sorted(ids, key=lambda x: int(x) if x.isdigit() else x)


def validar_linha_pre_envio(linha, ids_tipo_cliente_validos=None, ids_filial_validos=None):
    linha = {str(k).replace("﻿", "").strip(): v for k, v in linha.items()}
    erros = []

    for campo in ("Razao_Social", "CNPJ_CPF", "CEP", "Endereco", "Bairro", "Cidade_ID_IXC", "Email", "Telefone", "Tipo_Cliente_ID", "Filial_ID"):
        if not limpar_texto(linha.get(campo)):
            erros.append(f"{campo} e obrigatorio e nao foi informado.")

    confirmado, erro_conf = normalizar_confirmacao_cadastro(linha.get("Confirmar_Cadastro"))
    if not confirmado:
        erros.append(erro_conf)

    doc_valor = limpar_texto(linha.get("CNPJ_CPF"))
    if doc_valor:
        valido, msg_doc = validar_documento_fiscal(doc_valor)
        if not valido and msg_doc:
            erros.append(msg_doc)

    tipo_cliente_raw = somente_digitos(limpar_texto(linha.get("Tipo_Cliente_ID", "")))
    if tipo_cliente_raw and ids_tipo_cliente_validos:
        if tipo_cliente_raw not in ids_tipo_cliente_validos:
            erros.append(
                f"Tipo_Cliente_ID '{tipo_cliente_raw}' nao e uma opcao valida no IXC. "
                f"IDs aceitos: {', '.join(_ordenar_ids(ids_tipo_cliente_validos))}."
            )

    filial_raw = somente_digitos(limpar_texto(linha.get("Filial_ID", "")))
    if filial_raw and ids_filial_validos:
        if filial_raw not in ids_filial_validos:
            erros.append(
                f"Filial_ID '{filial_raw}' nao e uma opcao valida no IXC. "
                f"IDs aceitos: {', '.join(_ordenar_ids(ids_filial_validos))}."
            )

    tipo_assinante_raw = somente_digitos(limpar_texto(linha.get("Tipo_Assinante_ID", "")))
    if tipo_assinante_raw and tipo_assinante_raw not in {"1", "2", "3", "4", "5", "6"}:
        erros.append(
            f"Tipo_Assinante_ID '{tipo_assinante_raw}' invalido. "
            "Valores aceitos: 1=Comercial/Industrial, 2=Poder Publico, 3=Residencial/PF, 4=Publico, 5=Semi-Publico, 6=Outros."
        )

    tipo_loc = limpar_texto(linha.get("Tipo_Localidade", "")).upper()
    if tipo_loc and tipo_loc not in {"U", "R"}:
        erros.append(f"Tipo_Localidade '{tipo_loc}' invalido. Use U (Urbano) ou R (Rural).")

    fiscal_raw = limpar_texto(linha.get("Tipo_Cliente_Fiscal", ""))
    if fiscal_raw:
        try:
            fiscal_norm = str(int(fiscal_raw)).zfill(2)
        except (ValueError, TypeError):
            fiscal_norm = fiscal_raw
        if fiscal_norm not in {"01", "02", "03", "04", "05", "99"}:
            erros.append(
                f"Tipo_Cliente_Fiscal '{fiscal_raw}' invalido. "
                "Valores aceitos: 01=Comercial, 02=Industrial, 03=Servicos, 04=Prod.Rural, 05=Simples, 99=Outros."
            )

    ativo_raw = limpar_texto(linha.get("Ativo", "")).upper()
    if ativo_raw and ativo_raw not in {"S", "N"}:
        erros.append(f"Ativo '{ativo_raw}' invalido. Use S (ativo) ou N (inativo).")

    return erros


def executar_cadastro_cliente_ixc(dados, usuario_sistema=None):
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

    if len(documento) not in (11, 14):
        return (
            False,
            f"CNPJ_CPF invalido: esperado 11 digitos (CPF) ou 14 digitos (CNPJ), mas foram informados {len(documento)} digitos."
            " Corrija o campo antes de importar — documentos fora desse formato causam erro 'StartIndex' na integracao SAP.",
            "",
        )

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

    if not somente_digitos(linha.get("Tipo_Cliente_ID")):
        return (
            False,
            "Tipo_Cliente_ID obrigatorio. Valores validos no IXC: 5=Telebras, 6=OI, 7=BNB, 8=Privado, 9=Orgaos Publicos e Outros.",
            "",
        )
    if not somente_digitos(linha.get("Tipo_Assinante_ID")):
        return (
            False,
            "Tipo_Assinante_ID obrigatorio. Valores validos: 1=Comercial/Industrial, 2=Poder Publico, 3=Residencial/PF, 4=Publico, 5=Semi-Publico, 6=Outros.",
            "",
        )
    if not somente_digitos(linha.get("Filial_ID")):
        return (
            False,
            "Filial_ID obrigatorio. Consulte a aba Instrucoes_Ajuda da planilha para ver os IDs das filiais disponíveis.",
            "",
        )

    payload = montar_payload_cliente_ixc(linha, cidade_id_ixc, uf_id_ixc)
    identificacao = montar_identificacao_usuario_importacao(usuario_sistema)
    if identificacao:
        obs_existente = payload.get("obs", "")
        payload["obs"] = f"{obs_existente}\n\n{identificacao}".strip() if obs_existente else identificacao
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
