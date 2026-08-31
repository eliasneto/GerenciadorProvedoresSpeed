"""Camada de servicos do Backoffice: orquestracao das importacoes de planilha.

Cada `processar_*` recebe o arquivo enviado e o usuario, executa o fluxo
completo (leitura, auditoria, validacao quando aplicavel, execucao linha a
linha, geracao do relatorio) e devolve `(output, filename)` prontos para a
view transformar em HttpResponse. As views ficam responsaveis apenas por
HTTP: metodo/arquivo da requisicao, mensagens e redirecionamentos (PO-023,
ADR-005).
"""
import logging
import re
from io import BytesIO

import pandas as pd

from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from apps.integracoes.ixc.services.cadastrar_cliente_ixc import (
    detectar_cnpj_duplicado_na_planilha,
    executar_cadastro_cliente_ixc,
    limpar_texto,
    somente_digitos,
    validar_linha_pre_envio,
    verificar_duplicidade_ixc,
)
from apps.integracoes.ixc.services.cria_atendimento_ixc import (
    executar_abertura_atendimento,
    validar_tipo_processo,
)
from apps.integracoes.ixc.services.cria_login_atendimento import executar_cadastro_ixc
from apps.integracoes.ixc.client import IXCClient

logger = logging.getLogger(__name__)

CADASTRO_CLIENTE_IXC_INTEGRATION = "cadastro_cliente_ixc"


def serializar_linha_para_auditoria(dataframe, index):
    return {str(k).strip(): dataframe.at[index, k] for k in dataframe.columns}


def _ler_planilha_com_fallback(arquivo):
    """Le Excel ou CSV, com fallback de encoding latin1 quando utf-8 falha."""
    if arquivo.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            arquivo.seek(0)
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")

    try:
        return pd.read_excel(arquivo)
    except ValueError:
        arquivo.seek(0)
        try:
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            arquivo.seek(0)
            return pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")


def ler_dataframe_upload(arquivo):
    """Le a planilha e normaliza nomes de coluna (remove BOM/espacos/asterisco de obrigatoriedade)."""
    df = _ler_planilha_com_fallback(arquivo).copy()
    df.columns = [
        re.sub(r"\s*\*\s*$", "", str(coluna).replace("﻿", "").strip())
        for coluna in df.columns
    ]
    return df


def buscar_opcoes_ixc(endpoint, campo_nome="nome", limite=200):
    payload = {
        "qtype": "id",
        "query": "0",
        "oper": ">",
        "page": "1",
        "rp": str(limite),
        "sortname": "id",
        "sortorder": "asc",
    }
    try:
        status_code, body = IXCClient().listar(endpoint, payload)
        if status_code != 200 or not isinstance(body, dict):
            return []
        registros = body.get("registros") or []
        return [
            (str(r.get("id") or "").strip(), str(r.get(campo_nome) or r.get("nome") or r.get("razao") or "").strip())
            for r in registros
            if str(r.get("id") or "").strip()
        ]
    except Exception:
        logger.exception("Falha ao buscar opcoes de %s no IXC.", endpoint)
        return []


def processar_cotacao_import(arquivo, usuario):
    """Retorna (output: BytesIO, filename: str, sucessos: int, falhas: int)."""
    df = pd.read_excel(arquivo)
    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration="logins_ixc",
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=len(itens_importados),
        detalhes={"colunas": list(df.columns)},
        itens=itens_importados,
    )
    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""

    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index, linha in df.iterrows():
        if pd.notna(linha.get("Login_Login")):
            resultado = executar_cadastro_ixc(linha)
            if len(resultado) == 3:
                status, mensagem, id_ixc = resultado
            else:
                status, mensagem = resultado
                id_ixc = ""

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = id_ixc or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "id_ixc": id_ixc or "",
                    "dados_json": serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration="logins_ixc",
        action="execucao_integracao",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=sucessos + falhas,
        total_sucessos=sucessos,
        total_erros=falhas,
        detalhes={"colunas": list(df.columns)},
        itens=itens_execucao,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado_Processamento")
        worksheet = writer.sheets["Resultado_Processamento"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, 22)

    return output, "Relatorio_Importacao_IXC.xlsx", sucessos, falhas


def processar_atendimento_import(arquivo, usuario):
    """Retorna (output: BytesIO, filename: str)."""
    # Usa ler_dataframe_upload (nao _ler_planilha_com_fallback) porque o modelo
    # baixado em download_modelo_atendimento grava os cabecalhos obrigatorios com
    # sufixo "*" (ex.: "Cliente_ID*"). Sem a normalizacao, linha.get("Cliente_ID")
    # nunca encontra a coluna, indices_com_cliente fica vazio e a planilha volta
    # sem erro mas sem nenhum atendimento processado.
    df = ler_dataframe_upload(arquivo)

    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration="atendimento_ixc",
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=len(itens_importados),
        detalhes={"colunas": list(df.columns)},
        itens=itens_importados,
    )
    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""

    # --- Fase 1: validar todos os registros antes de chamar a API ---
    indices_com_cliente = [
        index for index, linha in df.iterrows()
        if pd.notna(linha.get("Cliente_ID"))
    ]
    erros_validacao = {}
    for index in indices_com_cliente:
        ok, msg_erro = validar_tipo_processo(df.loc[index])
        if not ok:
            erros_validacao[index] = msg_erro

    if erros_validacao:
        for index in indices_com_cliente:
            if index in erros_validacao:
                df.at[index, "Status_Importacao"] = "ERRO_VALIDACAO"
                df.at[index, "Mensagem_Importacao"] = erros_validacao[index]
            else:
                df.at[index, "Status_Importacao"] = "NAO_ENVIADO"
                df.at[index, "Mensagem_Importacao"] = (
                    "Nao enviado: outro registro da planilha tem divergencia de validacao."
                )

        itens_validacao = [
            {
                "linha_numero": index + 2,
                "status": "erro" if index in erros_validacao else "bloqueado",
                "mensagem": df.at[index, "Mensagem_Importacao"],
                "id_ixc": "",
                "dados_json": serializar_linha_para_auditoria(df, index),
            }
            for index in indices_com_cliente
        ]
        registrar_auditoria_integracao(
            integration="atendimento_ixc",
            action="validacao_bloqueada",
            usuario=usuario,
            arquivo_nome=arquivo.name,
            total_registros=len(indices_com_cliente),
            total_sucessos=0,
            total_erros=len(erros_validacao),
            detalhes={
                "colunas": list(df.columns),
                "motivo": "Divergencia entre Tipo_Processo e Workflow_ID em um ou mais registros.",
            },
            itens=itens_validacao,
        )

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Resultado_OS")
            worksheet = writer.sheets["Resultado_OS"]
            for col_num, _ in enumerate(df.columns.values):
                worksheet.set_column(col_num, col_num, 22)
        return output, "Relatorio_OS_IXC.xlsx"

    # --- Fase 2: todos passaram — enviar para a API ---
    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index in indices_com_cliente:
        status, mensagem = executar_abertura_atendimento(
            df.loc[index],
            usuario_sistema=usuario,
        )

        if status:
            sucessos += 1
            df.at[index, "Status_Importacao"] = "SUCESSO"
        else:
            falhas += 1
            df.at[index, "Status_Importacao"] = "ERRO"

        df.at[index, "Mensagem_Importacao"] = mensagem
        itens_execucao.append(
            {
                "linha_numero": index + 2,
                "status": "sucesso" if status else "erro",
                "mensagem": mensagem,
                "id_ixc": "",
                "dados_json": serializar_linha_para_auditoria(df, index),
            }
        )

    registrar_auditoria_integracao(
        integration="atendimento_ixc",
        action="execucao_integracao",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=sucessos + falhas,
        total_sucessos=sucessos,
        total_erros=falhas,
        detalhes={"colunas": list(df.columns)},
        itens=itens_execucao,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado_OS")
        worksheet = writer.sheets["Resultado_OS"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, 22)

    return output, "Relatorio_OS_IXC.xlsx"


def processar_cadastro_clientes_ixc(arquivo, usuario):
    """Retorna (output: BytesIO, filename: str)."""
    df = _ler_planilha_com_fallback(arquivo)
    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=len(itens_importados),
        detalhes={"colunas": list(df.columns)},
        itens=itens_importados,
    )

    # --- fase 1: pre-validacao de todos os registros ---
    opcoes_tipo_cliente = buscar_opcoes_ixc("cliente_tipo")
    opcoes_filial = buscar_opcoes_ixc("filial")
    ids_tipo_cliente = {id_ for id_, _ in opcoes_tipo_cliente} if opcoes_tipo_cliente else None
    ids_filial = {id_ for id_, _ in opcoes_filial} if opcoes_filial else None

    df["Status_Validacao"] = ""
    df["Erros_Validacao"] = ""

    linhas_planilha = [dict(linha) for _, linha in df.iterrows()]
    erros_cnpj_duplicado_planilha = detectar_cnpj_duplicado_na_planilha(linhas_planilha)

    total_com_erro = 0
    total_ok = 0

    for index, linha in df.iterrows():
        if not (pd.notna(linha.get("Razao_Social")) or pd.notna(linha.get("RAZAO_SOCIAL"))):
            continue
        erros = validar_linha_pre_envio(dict(linha), ids_tipo_cliente, ids_filial)

        permitir_duplicidade = limpar_texto(linha.get("Permitir_Duplicidade")).upper() in {"SIM", "S", "TRUE", "1"}
        if not permitir_duplicidade:
            erro_duplicado_planilha = erros_cnpj_duplicado_planilha.get(index)
            if erro_duplicado_planilha:
                erros.append(erro_duplicado_planilha)

            razao_social = limpar_texto(linha.get("Razao_Social") or linha.get("RAZAO_SOCIAL"))
            documento = somente_digitos(linha.get("CNPJ_CPF"))
            if razao_social and documento:
                resultado_duplicidade_ixc = verificar_duplicidade_ixc(razao_social, documento)
                if resultado_duplicidade_ixc:
                    mensagem_duplicidade_ixc, _ = resultado_duplicidade_ixc
                    erros.append(mensagem_duplicidade_ixc)

        if erros:
            df.at[index, "Status_Validacao"] = "ERRO"
            df.at[index, "Erros_Validacao"] = " | ".join(erros)
            total_com_erro += 1
        else:
            df.at[index, "Status_Validacao"] = "OK — apto para envio"
            total_ok += 1

    if total_com_erro > 0:
        registrar_auditoria_integracao(
            integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
            action="validacao_planilha_recusada",
            usuario=usuario,
            arquivo_nome=arquivo.name,
            total_registros=total_com_erro + total_ok,
            total_erros=total_com_erro,
            detalhes={
                "motivo": "planilha recusada na validacao pre-envio",
                "registros_com_erro": total_com_erro,
                "registros_ok": total_ok,
            },
        )

        df_report = df[df["Status_Validacao"] != ""].copy()
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_report.to_excel(writer, index=False, sheet_name="Validacao_Cadastro_Clientes_IXC")
            workbook = writer.book
            worksheet = writer.sheets["Validacao_Cadastro_Clientes_IXC"]

            fmt_erro = workbook.add_format({"bg_color": "#FEE2E2", "font_color": "#991B1B", "bold": True, "border": 1})
            fmt_ok = workbook.add_format({"bg_color": "#DCFCE7", "font_color": "#166534", "bold": True, "border": 1})

            status_col = list(df_report.columns).index("Status_Validacao")
            erros_col = list(df_report.columns).index("Erros_Validacao")
            num_rows = len(df_report)

            worksheet.conditional_format(
                1, status_col, num_rows, status_col,
                {"type": "text", "criteria": "containing", "value": "ERRO", "format": fmt_erro},
            )
            worksheet.conditional_format(
                1, status_col, num_rows, status_col,
                {"type": "text", "criteria": "containing", "value": "OK", "format": fmt_ok},
            )

            for col_num, col_name in enumerate(df_report.columns):
                if col_name == "Erros_Validacao":
                    worksheet.set_column(col_num, col_num, 90)
                elif col_name == "Status_Validacao":
                    worksheet.set_column(col_num, col_num, 24)
                elif col_name in {"Razao_Social", "Nome_Fantasia", "Endereco", "Observacao"}:
                    worksheet.set_column(col_num, col_num, 36)
                else:
                    worksheet.set_column(col_num, col_num, 22)

        return output, "Validacao_Cadastro_Clientes_IXC.xlsx"

    # --- fase 2: envio ao IXC (somente se todos passaram na validacao) ---
    df = df.drop(columns=["Status_Validacao", "Erros_Validacao"])
    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""

    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index, linha in df.iterrows():
        if pd.notna(linha.get("Razao_Social")) or pd.notna(linha.get("RAZAO_SOCIAL")):
            try:
                status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(linha, usuario_sistema=usuario)
            except Exception as exc_linha:
                status, mensagem, cliente_ixc_id = False, f"Erro inesperado ao processar linha: {exc_linha}", ""

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = cliente_ixc_id or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "dados_json": serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
        action="execucao_integracao",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=sucessos + falhas,
        total_sucessos=sucessos,
        total_erros=falhas,
        detalhes={"colunas": list(df.columns)},
        itens=itens_execucao,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado_Cadastro_Clientes_IXC")
        worksheet = writer.sheets["Resultado_Cadastro_Clientes_IXC"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, 24 if df.columns[col_num] != "Mensagem_Importacao" else 90)

    return output, "Relatorio_Cadastro_Clientes_IXC.xlsx"
