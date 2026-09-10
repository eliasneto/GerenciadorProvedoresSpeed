"""Camada de servicos do app core_admin: automacoes administrativas
(importacao de prospects, integracoes IXC, backup/restore) e diagnosticos
(SMTP, API do IXC).

Views ficam responsaveis apenas por HTTP: parametros da requisicao,
mensagens e renderizacao (PO-011, ADR-005).
"""
from io import BytesIO
import logging
import os
import re
import shutil
import subprocess
import sys
import zipfile
from email.utils import parseaddr
from pathlib import Path

import pandas as pd
from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email

from apps.core.automacoes_registry import automacoes_do_menu
from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from apps.leads import services as leads_services
from apps.integracoes.ixc.services.desativar_atendimento_ixc import executar_desativacao_atendimento
from apps.integracoes.ixc.services.editar_atendimento_ixc import (
    COLUNAS_OBRIGATORIAS_EDICAO_ATENDIMENTO_IXC,
    INSTRUCOES_EDICAO_ATENDIMENTO_IXC,
    executar_edicao_atendimento_ixc,
)
from apps.integracoes.ixc.services.editar_login_ixc import (
    COLUNAS_OBRIGATORIAS_EDICAO_LOGIN_IXC,
    INSTRUCOES_EDICAO_LOGIN_IXC,
    executar_edicao_login_ixc,
)
from apps.integracoes.ixc.services.resolver_os_atendimento_ixc import (
    COLUNAS_OBRIGATORIAS_RESOLUCAO_OS_ATENDIMENTO_IXC,
    COLUNAS_OPCIONAIS_RESOLUCAO_OS_ATENDIMENTO_IXC,
    INSTRUCOES_RESOLUCAO_OS_ATENDIMENTO_IXC,
    TAREFAS_DECISAO_CONHECIDAS_RESOLUCAO_OS_ATENDIMENTO_IXC,
    executar_resolucao_os_atendimento_ixc,
)
from apps.integracoes.ixc.client import IXCClient
from apps.core.models import AutomacaoMenu, IntegrationAudit, RestoreBackupAuditoria

from .import_services import (
    IMPORT_STATUS_ERROR,
    IMPORT_STATUS_RUNNING,
    IMPORT_STATUS_STOPPED,
    IMPORT_STATUS_SUCCESS,
    LEAD_IMPORT_COLUMNS,
    atualizar_auditoria_importacao,
    buscar_importacao_em_andamento,
    buscar_ultima_importacao,
    criar_auditoria_importacao,
    salvar_arquivo_importacao,
    solicitar_interrupcao_importacao,
)

logger = logging.getLogger(__name__)

DESATIVACAO_ATENDIMENTO_INTEGRATION = "desativacao_atendimento_ixc"
EDICAO_LOGIN_IXC_INTEGRATION = "edicao_login_ixc"
EDICAO_ATENDIMENTO_IXC_INTEGRATION = "edicao_atendimento_ixc"
RESOLUCAO_OS_ATENDIMENTO_INTEGRATION = "resolucao_os_atendimento_ixc"
CADASTRO_CLIENTE_IXC_INTEGRATION = "cadastro_cliente_ixc"


def _split_email_values(raw_value):
    return [
        item.strip()
        for bloco in str(raw_value or "").replace(";", ",").split(",")
        for item in [bloco.strip()]
        if item
    ]


def validar_lista_emails(raw_value, field_label, required=False):
    valores = _split_email_values(raw_value)
    if required and not valores:
        raise ValueError(f"Informe ao menos um e-mail em {field_label}.")

    for valor in valores:
        _, email = parseaddr(valor)
        validate_email(email or valor)

    return valores


def enviar_email_teste(*, remetente, destinatarios, copia, subject, body):
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=remetente,
        to=destinatarios,
        cc=copia,
        reply_to=[remetente],
        connection=get_connection(fail_silently=False),
    )
    return email.send(fail_silently=False)


def _ler_dataframe_upload(arquivo):
    def _normalizar_dataframe(dataframe):
        dataframe = dataframe.copy()
        dataframe.columns = [
            re.sub(r"\s*\*\s*$", "", str(coluna).replace("﻿", "").strip())
            for coluna in dataframe.columns
        ]
        return dataframe

    if arquivo.name.lower().endswith(".csv"):
        try:
            return _normalizar_dataframe(
                pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
            )
        except UnicodeDecodeError:
            arquivo.seek(0)
            return _normalizar_dataframe(
                pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")
            )

    try:
        return _normalizar_dataframe(pd.read_excel(arquivo))
    except ValueError:
        arquivo.seek(0)
        try:
            return _normalizar_dataframe(
                pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
            )
        except UnicodeDecodeError:
            arquivo.seek(0)
            return _normalizar_dataframe(
                pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")
            )


def _serializar_linha_para_auditoria(dataframe, index):
    return {str(k).strip(): dataframe.at[index, k] for k in dataframe.columns}


def processar_desativacao_atendimentos(arquivo, usuario):
    df = _ler_dataframe_upload(arquivo)
    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration=DESATIVACAO_ATENDIMENTO_INTEGRATION,
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
        if pd.notna(linha.get("Atendimento_ID")):
            status, mensagem, atendimento_id = executar_desativacao_atendimento(
                linha,
                usuario_sistema=usuario,
            )

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = atendimento_id or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "dados_json": _serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration=DESATIVACAO_ATENDIMENTO_INTEGRATION,
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
        df.to_excel(writer, index=False, sheet_name="Resultado_Desativacao_IXC")
        worksheet = writer.sheets["Resultado_Desativacao_IXC"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(col_num, col_num, 24 if df.columns[col_num] != "Mensagem_Importacao" else 90)

    return output.getvalue()


def processar_edicao_atendimentos_ixc(arquivo, usuario):
    df = _ler_dataframe_upload(arquivo)
    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration=EDICAO_ATENDIMENTO_IXC_INTEGRATION,
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=len(itens_importados),
        detalhes={"colunas": list(df.columns)},
        itens=itens_importados,
    )

    df["Campos_Alterados"] = ""
    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""

    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index, linha in df.iterrows():
        if pd.notna(linha.get("Atendimento_ID")):
            status, mensagem, atendimento_id, campos_alterados = executar_edicao_atendimento_ixc(
                linha,
                usuario_sistema=usuario,
            )

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Campos_Alterados"] = campos_alterados or ""
            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = atendimento_id or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "dados_json": _serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration=EDICAO_ATENDIMENTO_IXC_INTEGRATION,
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
        df.to_excel(writer, index=False, sheet_name="Resultado_Edicao_Atend_IXC")
        worksheet = writer.sheets["Resultado_Edicao_Atend_IXC"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(
                col_num,
                col_num,
                26 if df.columns[col_num] not in {"Mensagem_Importacao"} else 92,
            )

    return output.getvalue()


def processar_resolucao_os_atendimentos(planilha, zip_arquivos, usuario, execucao_id=None):
    df = _ler_dataframe_upload(planilha)
    itens_importados = dataframe_to_records(df)
    total_linhas = len(itens_importados)
    audit_importacao = registrar_auditoria_integracao(
        integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=planilha.name,
        total_registros=total_linhas,
        detalhes={"colunas": list(df.columns), "zip_nome": zip_arquivos.filename if zip_arquivos else ""},
        itens=itens_importados,
        execucao_id=execucao_id,
    )

    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""
    df["OS_Fechadas"] = ""

    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index, linha in df.iterrows():
        if pd.notna(linha.get("Atendimento_ID")):
            if execucao_id:
                atendimento_id_bruto = linha.get("Atendimento_ID")
                audit_importacao.progresso_atual = {
                    "linha_atual": index + 2,
                    "total_linhas": total_linhas,
                    "atendimento_id": "" if pd.isna(atendimento_id_bruto) else str(atendimento_id_bruto),
                }
                audit_importacao.save(update_fields=["progresso_atual"])

            status, mensagem, atendimento_id, os_fechadas = executar_resolucao_os_atendimento_ixc(
                linha,
                zip_arquivos,
                usuario_sistema=usuario,
            )

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO" if os_fechadas else "SEM_OS_ABERTA"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = atendimento_id or ""
            df.at[index, "OS_Fechadas"] = os_fechadas or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "dados_json": _serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
        action="execucao_integracao",
        usuario=usuario,
        arquivo_nome=planilha.name,
        total_registros=sucessos + falhas,
        total_sucessos=sucessos,
        total_erros=falhas,
        detalhes={"colunas": list(df.columns), "zip_nome": zip_arquivos.filename if zip_arquivos else ""},
        itens=itens_execucao,
        execucao_id=execucao_id,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Resultado_Resolucao_OS_IXC")
        worksheet = writer.sheets["Resultado_Resolucao_OS_IXC"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(
                col_num,
                col_num,
                26 if df.columns[col_num] not in {"Mensagem_Importacao"} else 92,
            )

    return output.getvalue()


def obter_progresso_resolucao_os_atendimento(execucao_id):
    if not execucao_id:
        return {"status": "nao_encontrado"}

    concluida = (
        IntegrationAudit.objects.filter(
            integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
            action="execucao_integracao",
            execucao_id=execucao_id,
        )
        .order_by("-id")
        .first()
    )
    if concluida:
        return {
            "status": "concluido",
            "total_registros": concluida.total_registros,
            "total_sucessos": concluida.total_sucessos,
            "total_erros": concluida.total_erros,
        }

    em_andamento = (
        IntegrationAudit.objects.filter(
            integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
            action="importacao_planilha",
            execucao_id=execucao_id,
        )
        .order_by("-id")
        .first()
    )
    if em_andamento:
        return {
            "status": "em_andamento",
            **(em_andamento.progresso_atual or {}),
        }

    return {"status": "nao_encontrado"}


def processar_edicao_logins_ixc(arquivo, usuario):
    df = _ler_dataframe_upload(arquivo)
    itens_importados = dataframe_to_records(df)
    registrar_auditoria_integracao(
        integration=EDICAO_LOGIN_IXC_INTEGRATION,
        action="importacao_planilha",
        usuario=usuario,
        arquivo_nome=arquivo.name,
        total_registros=len(itens_importados),
        detalhes={"colunas": list(df.columns)},
        itens=itens_importados,
    )

    df["Campos_Alterados"] = ""
    df["Status_Importacao"] = ""
    df["Mensagem_Importacao"] = ""
    df["ID_IXC"] = ""

    sucessos = 0
    falhas = 0
    itens_execucao = []

    for index, linha in df.iterrows():
        if pd.notna(linha.get("Login_ID")):
            status, mensagem, login_ixc_id, campos_alterados = executar_edicao_login_ixc(linha, usuario_sistema=usuario)

            if status:
                sucessos += 1
                df.at[index, "Status_Importacao"] = "SUCESSO"
            else:
                falhas += 1
                df.at[index, "Status_Importacao"] = "ERRO"

            df.at[index, "Campos_Alterados"] = campos_alterados or ""
            df.at[index, "Mensagem_Importacao"] = mensagem
            df.at[index, "ID_IXC"] = login_ixc_id or ""
            itens_execucao.append(
                {
                    "linha_numero": index + 2,
                    "status": "sucesso" if status else "erro",
                    "mensagem": mensagem,
                    "dados_json": _serializar_linha_para_auditoria(df, index),
                }
            )

    registrar_auditoria_integracao(
        integration=EDICAO_LOGIN_IXC_INTEGRATION,
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
        df.to_excel(writer, index=False, sheet_name="Resultado_Edicao_Logins_IXC")
        worksheet = writer.sheets["Resultado_Edicao_Logins_IXC"]
        for col_num, _ in enumerate(df.columns.values):
            worksheet.set_column(
                col_num,
                col_num,
                26 if df.columns[col_num] not in {"Mensagem_Importacao"} else 92,
            )

    return output.getvalue()


def _serializar_importacao(audit):
    if not audit:
        return None

    detalhes = dict(audit.detalhes_json or {})
    return {
        "id": audit.id,
        "arquivo_nome": audit.arquivo_nome or detalhes.get("arquivo_nome") or "-",
        "status_execucao": detalhes.get("status_execucao") or "-",
        "mensagem": detalhes.get("mensagem") or "",
        "processadas": detalhes.get("processadas") or 0,
        "total_previsto": detalhes.get("total_previsto") or 0,
        "ignorados": detalhes.get("ignorados") or 0,
        "empresas_novas": detalhes.get("empresas_novas") or 0,
        "enderecos_novos": detalhes.get("enderecos_novos") or 0,
        "leads_novos": detalhes.get("leads_novos") or 0,
        "empresas_atualizadas": detalhes.get("empresas_atualizadas") or 0,
        "enderecos_atualizados": detalhes.get("enderecos_atualizados") or 0,
        "leads_atualizados": detalhes.get("leads_atualizados") or 0,
        "criado_em": audit.criado_em,
        "atualizado_em": detalhes.get("atualizado_em") or "",
        "finalizado_em": detalhes.get("finalizado_em") or "",
        "total_registros": audit.total_registros,
        "total_sucessos": audit.total_sucessos,
        "total_erros": audit.total_erros,
    }


def _serializar_auditoria_planilha(audit):
    if not audit:
        return None

    return {
        "id": audit.id,
        "arquivo_nome": audit.arquivo_nome or "-",
        "criado_em": audit.criado_em,
        "total_registros": audit.total_registros,
        "total_sucessos": audit.total_sucessos,
        "total_erros": audit.total_erros,
        "detalhes": dict(audit.detalhes_json or {}),
    }


def _buscar_ultima_desativacao():
    return (
        IntegrationAudit.objects.filter(
            integration=DESATIVACAO_ATENDIMENTO_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def _buscar_ultima_edicao_login_ixc():
    return (
        IntegrationAudit.objects.filter(
            integration=EDICAO_LOGIN_IXC_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def _buscar_ultima_edicao_atendimento_ixc():
    return (
        IntegrationAudit.objects.filter(
            integration=EDICAO_ATENDIMENTO_IXC_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def _buscar_ultima_resolucao_os_atendimento():
    return (
        IntegrationAudit.objects.filter(
            integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def _buscar_ultimo_cadastro_cliente_ixc():
    return (
        IntegrationAudit.objects.filter(
            integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def montar_contexto_automacoes(form, menu):
    importacao_em_andamento = buscar_importacao_em_andamento()
    ultima_importacao = buscar_ultima_importacao()

    return {
        "form": form,
        "menu_label": dict(AutomacaoMenu.MENU_CHOICES).get(menu, menu),
        "automacoes": automacoes_do_menu(menu),
        "importacao_em_andamento": _serializar_importacao(importacao_em_andamento),
        "ultima_importacao": _serializar_importacao(ultima_importacao),
        "ultima_desativacao": _serializar_auditoria_planilha(_buscar_ultima_desativacao()),
        "ultima_edicao_login_ixc": _serializar_auditoria_planilha(_buscar_ultima_edicao_login_ixc()),
        "ultima_edicao_atendimento_ixc": _serializar_auditoria_planilha(_buscar_ultima_edicao_atendimento_ixc()),
        "ultima_resolucao_os_atendimento": _serializar_auditoria_planilha(_buscar_ultima_resolucao_os_atendimento()),
        "ultima_cadastro_cliente_ixc": _serializar_auditoria_planilha(_buscar_ultimo_cadastro_cliente_ixc()),
        "import_status_running": IMPORT_STATUS_RUNNING,
        "import_status_success": IMPORT_STATUS_SUCCESS,
        "import_status_error": IMPORT_STATUS_ERROR,
        "import_status_stopped": IMPORT_STATUS_STOPPED,
    }


def parar_importacao_em_andamento():
    importacao_em_andamento = buscar_importacao_em_andamento()
    if not importacao_em_andamento:
        return False, "Nao existe importacao em andamento para interromper."

    solicitar_interrupcao_importacao(importacao_em_andamento)
    return True, "Solicitacao de interrupcao enviada. Aguarde alguns segundos para a importacao ser finalizada."


def verificar_importacao_bloqueada():
    importacao_em_andamento = buscar_importacao_em_andamento()
    if not importacao_em_andamento:
        return None
    return (
        f"Ja existe uma importacao em andamento para o arquivo "
        f"{importacao_em_andamento.arquivo_nome or 'selecionado'}. "
        f"Aguarde a conclusao antes de iniciar outra."
    )


def iniciar_importacao_prospects(arquivo, usuario):
    audit = None
    try:
        caminho_salvo = salvar_arquivo_importacao(arquivo, settings.MEDIA_ROOT)
        audit = criar_auditoria_importacao(
            usuario_id=usuario.id if usuario.is_authenticated else None,
            arquivo_nome=arquivo.name,
            arquivo_caminho=str(caminho_salvo),
        )

        processo = subprocess.Popen(
            [
                sys.executable,
                str(Path(settings.BASE_DIR) / "scripts" / "integracoes" / "importar_leads_planilha.py"),
                str(audit.id),
                str(caminho_salvo),
            ]
        )
        atualizar_auditoria_importacao(audit, worker_pid=processo.pid)

        return True, "Importacao iniciada em segundo plano. Esta tela agora mostra o andamento e bloqueia nova execucao paralela."
    except Exception as exc:
        if audit:
            detalhes = dict(audit.detalhes_json or {})
            detalhes["status_execucao"] = IMPORT_STATUS_ERROR
            detalhes["mensagem"] = f"Nao foi possivel iniciar o processo em segundo plano: {exc}"
            audit.detalhes_json = detalhes
            audit.total_erros = 1
            audit.save(update_fields=["detalhes_json", "total_erros"])
        logger.exception("Falha ao iniciar a importacao de leads em segundo plano.")
        return False, f"Nao foi possivel iniciar a importacao: {exc}"


def montar_template_leads_bytes():
    df = pd.DataFrame(columns=LEAD_IMPORT_COLUMNS)
    df.loc[0] = [
        "00.000.000/0001-00",
        "EMPRESA EXEMPLO LTDA",
        "EXEMPLO TELECOM",
        "https://www.exemplo.com.br",
        "60000-000",
        "RUA EXEMPLO",
        "1500",
        "CENTRO",
        "FORTALEZA",
        "CE",
        "JOAO SILVA",
        "contato@exemplo.com",
        "(85) 99999-9999",
        "exemplo_telecom",
        "https://instagram.com/exemplo_telecom",
    ]
    df.loc[1] = [
        "00.000.000/0001-00",
        "EMPRESA EXEMPLO LTDA",
        "EXEMPLO TELECOM",
        "https://www.exemplo.com.br",
        "60100-000",
        "AVENIDA FILIAL",
        "200",
        "ALDEOTA",
        "FORTALEZA",
        "CE",
        "JOAO SILVA",
        "contato@exemplo.com",
        "(85) 99999-9999",
        "exemplo_telecom",
        "https://instagram.com/exemplo_telecom",
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads")
    return output.getvalue()


def montar_template_desativacao_atendimento_bytes(usuario):
    colunas = ["Atendimento_ID", "Mensagem", "Confirmar_Desativacao"]
    instrucoes = pd.DataFrame(
        [
            {
                "Campo": "Atendimento_ID",
                "O que colocar?": "ID numerico do atendimento no IXC.",
                "Obrigatorio?": "Sim",
            },
            {
                "Campo": "Mensagem",
                "O que colocar?": "Mensagem administrativa que sera registrada no fechamento. Se ficar vazio, usamos a padrao.",
                "Obrigatorio?": "Nao",
            },
            {
                "Campo": "Confirmar_Desativacao",
                "O que colocar?": "Digite SIM para autorizar o fechamento do atendimento.",
                "Obrigatorio?": "Sim",
            },
        ]
    )

    df_modelo = pd.DataFrame(columns=colunas)
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_Desativacao_IXC")
        instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet = writer.sheets["Modelo_Desativacao_IXC"]
        header_format = workbook.add_format({"bold": True, "bg_color": "#BFDBFE", "border": 1})
        integer_format = workbook.add_format({"num_format": "0"})

        for col_num, value in enumerate(colunas):
            worksheet.write(0, col_num, value, header_format)
            worksheet.set_column(
                col_num,
                col_num,
                26 if value != "Mensagem" else 80,
                integer_format if value == "Atendimento_ID" else None,
            )

        worksheet.data_validation(
            1,
            0,
            5000,
            0,
            {
                "validate": "integer",
                "criteria": ">=",
                "value": 1,
                "ignore_blank": False,
                "input_title": "ID do atendimento",
                "input_message": "Informe apenas o ID numerico do atendimento no IXC.",
                "error_title": "Valor invalido",
                "error_message": "Atendimento_ID aceita somente numeros inteiros.",
            },
        )
        worksheet.data_validation(
            1,
            2,
            5000,
            2,
            {
                "validate": "list",
                "source": ["SIM"],
                "ignore_blank": False,
                "input_title": "Confirmacao obrigatoria",
                "input_message": "Digite SIM para autorizar a finalizacao do atendimento.",
                "error_title": "Confirmacao obrigatoria",
                "error_message": "Para finalizar, o campo Confirmar_Desativacao deve conter SIM.",
            },
        )

    registrar_auditoria_integracao(
        integration=DESATIVACAO_ATENDIMENTO_INTEGRATION,
        action="download_modelo",
        usuario=usuario,
        arquivo_nome="Modelo_Desativacao_Atendimentos_IXC.xlsx",
        detalhes={"colunas": colunas},
    )

    return output.getvalue()


def montar_template_edicao_login_ixc_bytes(usuario):
    colunas = list(COLUNAS_OBRIGATORIAS_EDICAO_LOGIN_IXC)
    campos_obrigatorios_planilha = set(COLUNAS_OBRIGATORIAS_EDICAO_LOGIN_IXC)
    instrucoes = pd.DataFrame(INSTRUCOES_EDICAO_LOGIN_IXC)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo = pd.DataFrame(
            [
                {
                    "Login_ID": "4441",
                    "Confirmar_Alteracao": "SIM",
                }
            ],
            columns=colunas,
        )
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_Edicao_Login_IXC")
        instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet = writer.sheets["Modelo_Edicao_Login_IXC"]
        worksheet_ajuda = writer.sheets["Instrucoes_Ajuda"]
        header_format = workbook.add_format({"bg_color": "#DBEAFE", "border": 1})
        header_plain_format = workbook.add_format({"bold": True, "bg_color": "#DBEAFE", "border": 1})
        header_text_format = workbook.add_format({"bold": True})
        required_star_format = workbook.add_format({"bold": True, "font_color": "#DC2626"})
        integer_format = workbook.add_format({"num_format": "0"})

        for col_num, value in enumerate(colunas):
            if value in campos_obrigatorios_planilha:
                worksheet.write_rich_string(
                    0,
                    col_num,
                    header_text_format,
                    value,
                    required_star_format,
                    "*",
                    header_format,
                )
            else:
                worksheet.write(0, col_num, value, header_plain_format)
            worksheet.set_column(col_num, col_num, 24, integer_format if value == "Login_ID" else None)

        larguras_ajuda = [24, 44, 18, 18, 72]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        worksheet.data_validation(
            1,
            0,
            5000,
            0,
            {
                "validate": "integer",
                "criteria": ">=",
                "value": 1,
                "ignore_blank": False,
                "input_title": "Login_ID",
                "input_message": "Informe apenas o ID numerico do login no IXC.",
                "error_title": "Valor invalido",
                "error_message": "Login_ID aceita somente numeros inteiros.",
            },
        )
        worksheet.data_validation(
            1,
            1,
            5000,
            1,
            {
                "validate": "list",
                "source": ["SIM"],
                "ignore_blank": False,
                "input_title": "Confirmacao obrigatoria",
                "input_message": "Digite SIM para autorizar a alteracao do login no IXC.",
                "error_title": "Confirmacao obrigatoria",
                "error_message": "Para editar, o campo Confirmar_Alteracao deve conter SIM.",
            },
        )

    registrar_auditoria_integracao(
        integration=EDICAO_LOGIN_IXC_INTEGRATION,
        action="download_modelo",
        usuario=usuario,
        arquivo_nome="Modelo_Edicao_Logins_IXC.xlsx",
        detalhes={
            "colunas_modelo": colunas,
            "colunas_opcionais_aceitas": [
                item["Campo"]
                for item in INSTRUCOES_EDICAO_LOGIN_IXC
                if item["Campo"] not in campos_obrigatorios_planilha
            ],
        },
    )

    return output.getvalue()


def montar_template_edicao_atendimento_ixc_bytes(usuario):
    colunas = list(COLUNAS_OBRIGATORIAS_EDICAO_ATENDIMENTO_IXC)
    campos_obrigatorios_planilha = set(COLUNAS_OBRIGATORIAS_EDICAO_ATENDIMENTO_IXC)
    instrucoes = pd.DataFrame(INSTRUCOES_EDICAO_ATENDIMENTO_IXC)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo = pd.DataFrame(
            [
                {
                    "Atendimento_ID": "6502",
                    "Confirmar_Alteracao": "SIM",
                }
            ],
            columns=colunas,
        )
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_Edicao_Atendimento_IXC")
        instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet = writer.sheets["Modelo_Edicao_Atendimento_IXC"]
        worksheet_ajuda = writer.sheets["Instrucoes_Ajuda"]
        header_format = workbook.add_format({"bg_color": "#FDE68A", "border": 1})
        header_plain_format = workbook.add_format({"bold": True, "bg_color": "#FDE68A", "border": 1})
        header_text_format = workbook.add_format({"bold": True})
        required_star_format = workbook.add_format({"bold": True, "font_color": "#DC2626"})
        integer_format = workbook.add_format({"num_format": "0"})

        for col_num, value in enumerate(colunas):
            if value in campos_obrigatorios_planilha:
                worksheet.write_rich_string(
                    0,
                    col_num,
                    header_text_format,
                    value,
                    required_star_format,
                    "*",
                    header_format,
                )
            else:
                worksheet.write(0, col_num, value, header_plain_format)
            worksheet.set_column(
                col_num,
                col_num,
                28,
                integer_format if value == "Atendimento_ID" else None,
            )

        larguras_ajuda = [24, 44, 18, 18, 72]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        worksheet.data_validation(
            1,
            0,
            5000,
            0,
            {
                "validate": "integer",
                "criteria": ">=",
                "value": 1,
                "ignore_blank": False,
                "input_title": "Atendimento_ID",
                "input_message": "Informe apenas o ID numerico do atendimento no IXC.",
                "error_title": "Valor invalido",
                "error_message": "Atendimento_ID aceita somente numeros inteiros.",
            },
        )
        worksheet.data_validation(
            1,
            1,
            5000,
            1,
            {
                "validate": "list",
                "source": ["SIM"],
                "ignore_blank": False,
                "input_title": "Confirmacao obrigatoria",
                "input_message": "Digite SIM para autorizar a alteracao do atendimento no IXC.",
                "error_title": "Confirmacao obrigatoria",
                "error_message": "Para editar, o campo Confirmar_Alteracao deve conter SIM.",
            },
        )

    registrar_auditoria_integracao(
        integration=EDICAO_ATENDIMENTO_IXC_INTEGRATION,
        action="download_modelo",
        usuario=usuario,
        arquivo_nome="Modelo_Edicao_Atendimentos_IXC.xlsx",
        detalhes={
            "colunas_modelo": colunas,
            "colunas_opcionais_aceitas": [
                item["Campo"]
                for item in INSTRUCOES_EDICAO_ATENDIMENTO_IXC
                if item["Campo"] not in campos_obrigatorios_planilha
            ],
        },
    )

    return output.getvalue()


def montar_template_resolucao_os_atendimento_bytes(usuario):
    colunas = list(COLUNAS_OBRIGATORIAS_RESOLUCAO_OS_ATENDIMENTO_IXC) + list(
        COLUNAS_OPCIONAIS_RESOLUCAO_OS_ATENDIMENTO_IXC
    )
    campos_obrigatorios_planilha = set(COLUNAS_OBRIGATORIAS_RESOLUCAO_OS_ATENDIMENTO_IXC)
    instrucoes = pd.DataFrame(INSTRUCOES_RESOLUCAO_OS_ATENDIMENTO_IXC)
    tarefas_decisao = pd.DataFrame(TAREFAS_DECISAO_CONHECIDAS_RESOLUCAO_OS_ATENDIMENTO_IXC)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo = pd.DataFrame(columns=colunas)
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_Resolucao_OS_IXC")
        instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")
        tarefas_decisao.to_excel(writer, index=False, sheet_name="Tarefas_Decisao_IXC")

        workbook = writer.book
        worksheet = writer.sheets["Modelo_Resolucao_OS_IXC"]
        worksheet_ajuda = writer.sheets["Instrucoes_Ajuda"]
        worksheet_tarefas = writer.sheets["Tarefas_Decisao_IXC"]
        worksheet_tarefas.write(0, 2, "Lista nao exaustiva — confirme com quem opera o IXC se aparecer uma tarefa nao listada aqui.")
        worksheet_tarefas.set_column(0, 0, 14)
        worksheet_tarefas.set_column(1, 1, 44)
        header_format = workbook.add_format({"bg_color": "#DBEAFE", "border": 1})
        header_plain_format = workbook.add_format({"bold": True, "bg_color": "#DBEAFE", "border": 1})
        header_text_format = workbook.add_format({"bold": True})
        required_star_format = workbook.add_format({"bold": True, "font_color": "#DC2626"})
        integer_format = workbook.add_format({"num_format": "0"})

        for col_num, value in enumerate(colunas):
            if value in campos_obrigatorios_planilha:
                worksheet.write_rich_string(
                    0,
                    col_num,
                    header_text_format,
                    value,
                    required_star_format,
                    "*",
                    header_format,
                )
            else:
                worksheet.write(0, col_num, value, header_plain_format)
            worksheet.set_column(
                col_num,
                col_num,
                80 if value == "Mensagem" else 26,
                integer_format if value == "Atendimento_ID" else None,
            )

        larguras_ajuda = [24, 44, 18, 18, 72]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        worksheet.data_validation(
            1,
            0,
            5000,
            0,
            {
                "validate": "integer",
                "criteria": ">=",
                "value": 1,
                "ignore_blank": False,
                "input_title": "Atendimento_ID",
                "input_message": "Informe apenas o ID numerico do atendimento no IXC.",
                "error_title": "Valor invalido",
                "error_message": "Atendimento_ID aceita somente numeros inteiros.",
            },
        )
        worksheet.data_validation(
            1,
            1,
            5000,
            1,
            {
                "validate": "list",
                "source": ["SIM"],
                "ignore_blank": False,
                "input_title": "Confirmacao obrigatoria",
                "input_message": "Digite SIM para autorizar o fechamento das O.S. do atendimento.",
                "error_title": "Confirmacao obrigatoria",
                "error_message": "Para fechar as O.S., o campo Confirmar_Resolucao deve conter SIM.",
            },
        )
        worksheet.data_validation(
            1,
            2,
            5000,
            2,
            {
                "validate": "list",
                "source": ["SIM", "NAO"],
                "ignore_blank": False,
                "input_title": "Tem_Anexo",
                "input_message": "SIM se este atendimento tiver documento a anexar antes do fechamento das O.S.",
                "error_title": "Valor invalido",
                "error_message": "Tem_Anexo aceita somente SIM ou NAO.",
            },
        )
        worksheet.data_validation(
            1,
            3,
            5000,
            3,
            {
                "validate": "list",
                "source": ["SIM", "NAO"],
                "ignore_blank": False,
                "input_title": "Fechar_Todas_OS",
                "input_message": "SIM fecha todas as O.S. abertas do atendimento. NAO fecha somente a O.S. atual.",
                "error_title": "Valor invalido",
                "error_message": "Fechar_Todas_OS aceita somente SIM ou NAO.",
            },
        )
        if "Mais_de_um_anexo" in colunas:
            col_mais_de_um_anexo = colunas.index("Mais_de_um_anexo")
            worksheet.data_validation(
                1,
                col_mais_de_um_anexo,
                5000,
                col_mais_de_um_anexo,
                {
                    "validate": "list",
                    "source": ["SIM", "NAO"],
                    "ignore_blank": True,
                    "input_title": "Mais_de_um_anexo",
                    "input_message": (
                        "Preencha somente quando Tem_Anexo = SIM e houver mais de um documento. "
                        "SIM habilita Nome_Anexo_2 e Nome_Anexo_3."
                    ),
                    "error_title": "Valor invalido",
                    "error_message": "Mais_de_um_anexo aceita somente SIM ou NAO.",
                },
            )
        if "Proxima_Tarefa_ID" in colunas:
            col_proxima_tarefa = colunas.index("Proxima_Tarefa_ID")
            worksheet.data_validation(
                1,
                col_proxima_tarefa,
                5000,
                col_proxima_tarefa,
                {
                    "validate": "integer",
                    "criteria": ">=",
                    "value": 1,
                    "ignore_blank": True,
                    "input_title": "Proxima_Tarefa_ID",
                    "input_message": (
                        "Normalmente NAO precisa preencher: o sistema resolve a proxima tarefa "
                        "sozinho. So preencha se o sistema bloquear a linha pedindo esse ID."
                    ),
                    "error_title": "Valor invalido",
                    "error_message": "Proxima_Tarefa_ID aceita somente o ID numerico da tarefa.",
                },
            )
        if "Informar_Colaborador" in colunas:
            col_informar_colaborador = colunas.index("Informar_Colaborador")
            worksheet.data_validation(
                1,
                col_informar_colaborador,
                5000,
                col_informar_colaborador,
                {
                    "validate": "list",
                    "source": ["SIM", "NAO"],
                    "ignore_blank": True,
                    "input_title": "Informar_Colaborador",
                    "input_message": (
                        "Preencha somente se a finalizacao desta linha deve ser atribuida a outro "
                        "colaborador do IXC. SIM exige Email_Colaborador."
                    ),
                    "error_title": "Valor invalido",
                    "error_message": "Informar_Colaborador aceita somente SIM ou NAO.",
                },
            )

    registrar_auditoria_integracao(
        integration=RESOLUCAO_OS_ATENDIMENTO_INTEGRATION,
        action="download_modelo",
        usuario=usuario,
        arquivo_nome="Modelo_Resolucao_OS_Atendimentos_IXC.xlsx",
        detalhes={"colunas_modelo": colunas},
    )

    return output.getvalue()


def _is_within_directory(base_dir, target_path):
    base_dir = Path(base_dir).resolve()
    target_path = Path(target_path).resolve()
    try:
        target_path.relative_to(base_dir)
        return True
    except ValueError:
        return False


def _extract_zip_safely(zip_path, target_dir):
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            extracted_path = Path(target_dir) / member.filename
            if not _is_within_directory(target_dir, extracted_path):
                raise ValueError(f"Arquivo invalido dentro do ZIP: {member.filename}")
        archive.extractall(target_dir)


def _find_first_file(root_dir, suffix):
    for path in Path(root_dir).rglob(f"*{suffix}"):
        if path.is_file():
            return path
    return None


def _find_media_dir(root_dir):
    candidates = [path for path in Path(root_dir).rglob("media") if path.is_dir()]
    if candidates:
        return candidates[0]
    return None


def _backup_storage_dir():
    return Path(settings.MEDIA_ROOT) / "backups"


def _listar_backups_disponiveis():
    diretorio = _backup_storage_dir()
    if not diretorio.exists():
        return []

    backups = []
    for path in sorted(diretorio.glob("backup_speed_*.zip"), key=lambda item: item.stat().st_mtime, reverse=True):
        tamanho_kb = max(1, round(path.stat().st_size / 1024))
        backups.append((path.name, f"{path.name} ({tamanho_kb} KB)"))
    return backups


def _resolver_backup_existente(nome_arquivo):
    diretorio = _backup_storage_dir().resolve()
    arquivo = (diretorio / str(nome_arquivo or "").strip()).resolve()

    if not str(arquivo).startswith(str(diretorio)):
        raise ValueError("Backup selecionado invalido.")

    if not arquivo.exists() or not arquivo.is_file():
        raise FileNotFoundError("O backup selecionado nao foi encontrado no servidor.")

    if arquivo.suffix.lower() != ".zip":
        raise ValueError("O backup selecionado nao e um arquivo .zip valido.")

    return arquivo


def _extrair_ip_request(request):
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def _registrar_auditoria_restore(
    *,
    request,
    arquivo_nome,
    origem,
    sucesso,
    media_restaurada=False,
    detalhes="",
):
    RestoreBackupAuditoria.objects.create(
        usuario=request.user if getattr(request.user, "is_authenticated", False) else None,
        origem=origem,
        arquivo_nome=(arquivo_nome or "")[:255],
        sucesso=bool(sucesso),
        media_restaurada=bool(media_restaurada),
        endereco_ip=_extrair_ip_request(request) or None,
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        detalhes=detalhes or "",
    )


def restaurar_banco_e_midia(sql_file, media_dir):
    """Executa o restore do dump SQL via `mysql` e, se o ZIP trouxer uma
    pasta `media`, sincroniza seu conteudo com `MEDIA_ROOT`. Levanta
    `RuntimeError` se o comando `mysql` retornar erro."""
    db_conf = settings.DATABASES["default"]
    mysql_host = db_conf.get("HOST") or "localhost"
    mysql_port = str(db_conf.get("PORT") or 3306)
    mysql_name = db_conf.get("NAME")
    mysql_user = (
        os.getenv("DB_ADMIN_USER")
        or db_conf.get("USER")
        or os.getenv("DB_USER")
        or "root"
    )
    mysql_password = (
        os.getenv("DB_ADMIN_PASSWORD")
        or db_conf.get("PASSWORD")
        or os.getenv("DB_PASSWORD")
        or os.getenv("MYSQL_ROOT_PASSWORD", "")
    )

    env = os.environ.copy()
    env["MYSQL_PWD"] = mysql_password

    mysql_cmd = [
        "mysql",
        "-h",
        mysql_host,
        "-P",
        mysql_port,
        "-u",
        mysql_user,
        mysql_name,
    ]

    with open(sql_file, "rb") as sql_handler:
        result = subprocess.run(
            mysql_cmd,
            stdin=sql_handler,
            env=env,
            capture_output=True,
        )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Falha ao restaurar o banco.")

    media_restaurado = False
    if media_dir is not None:
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        for item in media_dir.iterdir():
            destino = media_root / item.name
            if item.is_dir():
                if destino.exists():
                    shutil.rmtree(destino)
                shutil.copytree(item, destino)
            else:
                shutil.copy2(item, destino)
        media_restaurado = True

    return media_restaurado


def consultar_status_ixc():
    client = IXCClient()
    status_code, body = client.listar("/cliente", {"rp": "1", "page": "1"})

    if status_code == 200 and body.get("type") != "error":
        return {"ok": True, "status_code": status_code, "url": client.base_url}

    mensagem = (
        body.get("message")
        or body.get("erro")
        or body.get("error")
        or body.get("raw")
        or str(body)
    )
    return {"ok": False, "status_code": status_code, "erro": mensagem, "url": client.base_url}


# ============================================================
# Exportacao de Setores e Escolas (RN-048/RN-049, PO-071 — substitui a RN-047)
# ============================================================

# Colunas fixas do CSV, na ordem de saida — mesma ordem das colunas ja
# exibidas hoje na tela de Setor/grid de Enderecos Lastmile (RN-048).
COLUNAS_EXPORTACAO_SETORES_ESCOLAS_FIXAS = [
    "INEP", "Nome da Escola", "Estado", "Municipio", "Logradouro", "Numero", "Bairro", "CEP", "Status",
    "Setor RE", "Parceiro RE", "Status RE",
    "Setor RI", "Parceiro RI", "Status RI",
    "Setor MC", "Parceiro MC", "Status MC",
]

# (prefixo de coluna, nome do related_name reverso em Escola) por subatividade.
_SUBATIVIDADES_EXPORTACAO = (("RE", "rede_externa"), ("RI", "rede_interna"), ("MC", "mapa_calor"))

# related_name (alvo em Escola) -> tipo esperado por
# `leads_services._nomes_setor_fora_da_sub_atividade` e sufixo de coluna.
_ALVO_SUBATIVIDADE = {"rede_externa": ("re", "RE"), "rede_interna": ("ri", "RI"), "mapa_calor": ("mc", "MC")}

PREFIXO_CAMPO_PERSONALIZADO = "Campo Personalizado - "


def _colunas_campos_personalizados():
    """RN-049: decide, para cada `Campo` cadastrado (RN-031), se ele gera
    coluna para a Escola (escopo "Escola", `SetorEscopo`) ou uma coluna por
    subatividade aplicavel (escopo "Sub-atividades", ou sem `SetorEscopo`
    cadastrado — comportamento legado de RE+RI+Mapa Calor). Reaproveita a
    mesma logica de escopo ja usada no modal de Campos (RN-032/037), so
    trocando "aparece na tela" por "vira coluna". Retorna lista de
    `(nome_coluna, campo, alvo)`, `alvo` sendo "escola" ou o related_name
    da subatividade em Escola."""
    Campo = django_apps.get_model("escolas", "Campo")
    SetorEscopo = django_apps.get_model("escolas", "SetorEscopo")

    nomes_escola = set(
        SetorEscopo.objects.filter(atividade=SetorEscopo.ATIVIDADE_ESCOLA).values_list("setor_nome", flat=True)
    )
    bloqueados_por_alvo = {
        alvo: leads_services._nomes_setor_fora_da_sub_atividade(tipo)
        for alvo, (tipo, _sufixo) in _ALVO_SUBATIVIDADE.items()
    }

    entradas = []
    for campo in Campo.objects.order_by("setor_nome", "nome"):
        if campo.setor_nome in nomes_escola:
            entradas.append((f"{PREFIXO_CAMPO_PERSONALIZADO}{campo.nome}", campo, "escola"))
            continue
        for alvo, (_tipo, sufixo) in _ALVO_SUBATIVIDADE.items():
            if campo.setor_nome in bloqueados_por_alvo[alvo]:
                continue
            entradas.append((f"{PREFIXO_CAMPO_PERSONALIZADO}{campo.nome} ({sufixo})", campo, alvo))
    return entradas


def _valores_campos_personalizados_em_lote(colunas_campo):
    """RN-049: busca todo `CampoValor` relevante de uma vez por alvo
    (Escola, Rede Externa, Rede Interna, Mapa Calor) — 4 consultas no
    total, independente do numero de Escolas, para nao gerar N+1. Inclui
    tambem o `campo_base` de Campos tipo Calculado, mesmo sem coluna
    propria naquele alvo. Retorna `{(alvo, object_id, campo_id): valor}`."""
    Campo = django_apps.get_model("escolas", "Campo")
    CampoValor = django_apps.get_model("escolas", "CampoValor")
    modelo_por_alvo = {
        "escola": django_apps.get_model("escolas", "Escola"),
        "rede_externa": django_apps.get_model("escolas", "RedeExterna"),
        "rede_interna": django_apps.get_model("escolas", "RedeInterna"),
        "mapa_calor": django_apps.get_model("escolas", "MapaCalor"),
    }

    ids_por_alvo = {}
    for _nome_coluna, campo, alvo in colunas_campo:
        ids = ids_por_alvo.setdefault(alvo, set())
        ids.add(campo.id)
        if campo.tipo == Campo.TIPO_CALCULADO and campo.campo_base_id:
            ids.add(campo.campo_base_id)

    valores = {}
    for alvo, ids in ids_por_alvo.items():
        content_type = ContentType.objects.get_for_model(modelo_por_alvo[alvo])
        for valor in CampoValor.objects.filter(content_type=content_type, campo_id__in=ids):
            valores[(alvo, valor.object_id, valor.campo_id)] = valor.valor
    return valores


def _valor_coluna_campo_personalizado(campo, alvo, instancia, valores_campo):
    """RN-049: valor de uma coluna de Campo personalizado para `instancia`
    (Escola ou uma subatividade dela) — mesma regra de visibilidade/calculo
    do modal (RN-032/039): branco sem a subatividade, Status condicionante
    que nao bate, ou sem valor gravado; Calculado deriva ao vivo do Campo
    base; demais tipos usam a formatacao ja padronizada do historico
    (RN-040)."""
    Campo = django_apps.get_model("escolas", "Campo")
    if instancia is None or not instancia.pk:
        return ""

    status_atual_nome = instancia.status.nome if alvo != "escola" and instancia.status_id else None
    if not leads_services._campo_visivel(campo, status_atual_nome):
        return ""

    if campo.tipo == Campo.TIPO_CALCULADO:
        valor_base = valores_campo.get((alvo, instancia.pk, campo.campo_base_id))
        valor = leads_services._valor_campo_calculado(valor_base, campo.horas_prazo)
    else:
        valor = valores_campo.get((alvo, instancia.pk, campo.id))

    if valor is None or valor == "":
        return ""
    return leads_services._formatar_valor_campo_historico(campo, valor)


def montar_exportacao_setores_escolas():
    """RN-048/RN-049/PO-071: monta as colunas (fixas + Campos
    personalizados descobertos neste momento) e o gerador de linhas — uma
    por Escola — para o CSV de exportacao de Setores e Escolas."""
    colunas_campo = _colunas_campos_personalizados()
    colunas = list(COLUNAS_EXPORTACAO_SETORES_ESCOLAS_FIXAS) + [nome for nome, _campo, _alvo in colunas_campo]
    return colunas, _gerar_linhas_exportacao_setores_escolas(colunas_campo)


def _gerar_linhas_exportacao_setores_escolas(colunas_campo):
    """RN-048/RN-049: uma linha por Escola, replicando as colunas ja
    exibidas na tela de Setor (grid de Enderecos Lastmile) — dados da
    Escola, Setor/Parceiro/Status de cada subatividade, e o valor de cada
    Campo personalizado aplicavel.

    `select_related` cobre Escola + as 3 subatividades e seus
    Setor/Parceiro/Status numa unica consulta com joins; os valores de
    Campo personalizado vem pre-carregados em lote — sem N+1 por Escola.
    """
    Escola = django_apps.get_model("escolas", "Escola")

    campos_relacionados = [
        f"{related_name}__{campo}"
        for _, related_name in _SUBATIVIDADES_EXPORTACAO
        for campo in ("setor", "parceiro", "status")
    ]

    escolas = Escola.objects.all().select_related(*campos_relacionados).order_by("nome")
    valores_campo = _valores_campos_personalizados_em_lote(colunas_campo)

    for escola in escolas.iterator():
        linha = {
            "INEP": escola.inep,
            "Nome da Escola": escola.nome,
            "Estado": escola.uf,
            "Municipio": escola.municipio,
            "Logradouro": escola.logradouro,
            "Numero": escola.numero,
            "Bairro": escola.bairro,
            "CEP": escola.cep,
            "Status": escola.status_escola,
        }
        alvos = {"escola": escola}
        for prefixo, related_name in _SUBATIVIDADES_EXPORTACAO:
            rede = getattr(escola, related_name, None)
            linha[f"Setor {prefixo}"] = rede.setor.nome if rede and rede.setor_id else ""
            linha[f"Parceiro {prefixo}"] = str(rede.parceiro) if rede and rede.parceiro_id else ""
            linha[f"Status {prefixo}"] = rede.status.nome if rede and rede.status_id else ""
            alvos[related_name] = rede

        for nome_coluna, campo, alvo in colunas_campo:
            linha[nome_coluna] = _valor_coluna_campo_personalizado(campo, alvo, alvos[alvo], valores_campo)

        yield linha
