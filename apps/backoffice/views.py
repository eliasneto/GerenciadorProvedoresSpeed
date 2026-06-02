import os
from pathlib import Path
from io import BytesIO

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.integration_audit import (
    atualizar_auditoria_integracao,
    criar_auditoria_integracao,
    dataframe_to_records,
    registrar_auditoria_integracao,
    registrar_item_auditoria_integracao,
)
from core.models import IntegrationAudit
from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    executar_abertura_atendimento,
)
from scripts.integracoes.backoffice.cria_login_atendimento import (
    executar_cadastro_ixc,
)

ATENDIMENTO_COLUNAS = [
    "Cliente_ID",
    "Login_ID",
    "Contrato_ID",
    "Filial_ID",
    "Assunto_ID",
    "Departamento_ID",
    "Assunto_Descricao",
    "Descricao",
]

ATENDIMENTO_COLUNAS_ID = [
    "Cliente_ID",
    "Login_ID",
    "Contrato_ID",
    "Filial_ID",
    "Assunto_ID",
    "Departamento_ID",
]

IMPORT_STATUS_RUNNING = "em_andamento"
IMPORT_STATUS_SUCCESS = "concluido"
IMPORT_STATUS_ERROR = "interrompido"
RELATORIO_STATUS_PENDING = True


def grupo_backoffice_required(user):
    if not user.is_authenticated:
        return False
    if user.groups.filter(name="Backoffice").exists() or user.is_superuser:
        return True
    raise PermissionDenied


def aplicar_validacao_campos_id(workbook, worksheet, colunas, campos_id):
    header_format = workbook.add_format({"bold": True, "bg_color": "#D7E4BC", "border": 1})
    inteiro_format = workbook.add_format({"num_format": "0"})

    for col_num, value in enumerate(colunas):
        worksheet.write(0, col_num, value, header_format)
        worksheet.set_column(col_num, col_num, 24, inteiro_format if value in campos_id else None)

        if value not in campos_id:
            continue

        worksheet.data_validation(
            1,
            col_num,
            5000,
            col_num,
            {
                "validate": "integer",
                "criteria": ">=",
                "value": 0,
                "ignore_blank": True,
                "input_title": f"{value} numerico",
                "input_message": "Informe apenas o ID numerico do IXC.",
                "error_title": "Valor invalido",
                "error_message": f"O campo {value} aceita somente numeros inteiros.",
            },
        )


def serializar_linha_para_auditoria(dataframe, index):
    return {str(k).strip(): dataframe.at[index, k] for k in dataframe.columns}


def buscar_execucao_em_andamento(integration_code):
    auditorias = IntegrationAudit.objects.filter(
        integration=integration_code,
        action="execucao_integracao",
    ).order_by("-criado_em")[:10]

    for audit in auditorias:
        if (audit.detalhes_json or {}).get("processamento_status") == IMPORT_STATUS_RUNNING:
            return audit
    return None


def serializar_execucao_em_andamento(audit):
    if not audit:
        return None

    detalhes = audit.detalhes_json or {}
    return {
        "id": audit.id,
        "arquivo_nome": audit.arquivo_nome or detalhes.get("arquivo_nome") or "",
        "mensagem": detalhes.get("mensagem") or "Processando planilha...",
        "processadas": audit.total_registros or 0,
        "sucessos": audit.total_sucessos or 0,
        "erros": audit.total_erros or 0,
        "total_previsto": detalhes.get("total_previsto") or 0,
        "ultima_linha_processada": detalhes.get("ultima_linha_processada") or "",
        "ultimo_id_ixc_criado": detalhes.get("ultimo_id_ixc_criado") or "",
        "criado_em": audit.criado_em,
    }


def buscar_relatorio_disponivel(integration_code):
    auditorias = IntegrationAudit.objects.filter(
        integration=integration_code,
        action="execucao_integracao",
    ).order_by("-criado_em")[:10]

    for audit in auditorias:
        detalhes = audit.detalhes_json or {}
        if detalhes.get("relatorio_disponivel") is RELATORIO_STATUS_PENDING:
            return audit
    return None


def serializar_relatorio_disponivel(audit):
    if not audit:
        return None

    detalhes = audit.detalhes_json or {}
    return {
        "id": audit.id,
        "arquivo_nome": audit.arquivo_nome or "",
        "relatorio_nome_arquivo": detalhes.get("relatorio_nome_arquivo") or "",
        "url_download": reverse("backoffice:download_relatorio_automacao", args=[audit.id]),
        "gerado_em": detalhes.get("relatorio_gerado_em") or "",
    }


def render_backoffice_automacoes(request):
    return render(
        request,
        "backoffice/cotacao_import.html",
        {
            "logins_ixc_em_andamento": serializar_execucao_em_andamento(
                buscar_execucao_em_andamento("logins_ixc")
            ),
            "atendimento_ixc_em_andamento": serializar_execucao_em_andamento(
                buscar_execucao_em_andamento("atendimento_ixc")
            ),
            "logins_ixc_relatorio_disponivel": serializar_relatorio_disponivel(
                buscar_relatorio_disponivel("logins_ixc")
            ),
            "atendimento_ixc_relatorio_disponivel": serializar_relatorio_disponivel(
                buscar_relatorio_disponivel("atendimento_ixc")
            ),
        },
    )


def obter_limite_registros_atendimento_ixc():
    valor = (os.getenv("ATENDIMENTO_IXC_MAX_REGISTROS_POR_PROCESSAMENTO") or "1000").strip()
    try:
        return max(int(valor), 1)
    except ValueError:
        return 1000


def contar_registros_atendimento_importaveis(dataframe):
    if "Cliente_ID" not in dataframe.columns:
        return 0
    return int(dataframe["Cliente_ID"].notna().sum())


def construir_abas_relatorio_atendimento(
    dataframe,
    *,
    arquivo_nome,
    total_registros,
    sucessos,
    falhas,
    limite_registros,
    ultimo_id_ixc="",
    ultima_linha_processada=None,
):
    completo = dataframe.copy()
    criados = completo[completo["Status_Importacao"] == "SUCESSO"].copy()
    erros = completo[completo["Status_Importacao"] == "ERRO"].copy()
    pendentes = completo[
        ~completo["Status_Importacao"].isin(["SUCESSO", "ERRO"])
    ].copy()

    resumo = pd.DataFrame(
        [
            {"Indicador": "Arquivo de origem", "Valor": arquivo_nome},
            {"Indicador": "Total de registros processaveis", "Valor": total_registros},
            {"Indicador": "Total criado no IXC", "Valor": sucessos},
            {"Indicador": "Total com erro", "Valor": falhas},
            {
                "Indicador": "Total nao processado",
                "Valor": max(total_registros - sucessos - falhas, 0),
            },
            {"Indicador": "Limite configurado por processamento", "Valor": limite_registros},
            {
                "Indicador": "Ultima linha processada",
                "Valor": ultima_linha_processada or "",
            },
            {"Indicador": "Ultimo ID IXC criado", "Valor": ultimo_id_ixc or ""},
        ]
    )

    abas = [
        ("Resumo", resumo),
        ("Criados", criados),
        ("Erros", erros),
    ]
    if not pendentes.empty:
        abas.append(("Pendentes", pendentes))
    abas.append(("Completo", completo))
    return abas


def gerar_resposta_relatorio_atendimento(
    dataframe,
    *,
    arquivo_nome,
    total_registros,
    sucessos,
    falhas,
    limite_registros,
    ultimo_id_ixc="",
    ultima_linha_processada=None,
):
    abas = construir_abas_relatorio_atendimento(
        dataframe,
        arquivo_nome=arquivo_nome,
        total_registros=total_registros,
        sucessos=sucessos,
        falhas=falhas,
        limite_registros=limite_registros,
        ultimo_id_ixc=ultimo_id_ixc,
        ultima_linha_processada=ultima_linha_processada,
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9EAD3", "border": 1})
        sucesso_format = workbook.add_format({"bg_color": "#EAF4E2"})
        erro_format = workbook.add_format({"bg_color": "#FDE9D9"})
        pendente_format = workbook.add_format({"bg_color": "#FFF2CC"})

        for nome_aba, frame in abas:
            frame.to_excel(writer, index=False, sheet_name=nome_aba)
            worksheet = writer.sheets[nome_aba]

            for col_num, col_name in enumerate(frame.columns):
                worksheet.write(0, col_num, col_name, header_format)
                sample = frame[col_name].fillna("").astype(str).head(1000)
                max_len = max([len(str(col_name))] + [len(valor) for valor in sample])
                worksheet.set_column(col_num, col_num, min(max(max_len + 2, 14), 65))

            worksheet.freeze_panes(1, 0)
            if not frame.empty:
                worksheet.autofilter(0, 0, len(frame), len(frame.columns) - 1)

            if "Status_Importacao" in frame.columns and not frame.empty:
                worksheet.conditional_format(
                    1,
                    0,
                    len(frame),
                    len(frame.columns) - 1,
                    {
                        "type": "formula",
                        "criteria": '=$I2="SUCESSO"',
                        "format": sucesso_format,
                    },
                )
                worksheet.conditional_format(
                    1,
                    0,
                    len(frame),
                    len(frame.columns) - 1,
                    {
                        "type": "formula",
                        "criteria": '=$I2="ERRO"',
                        "format": erro_format,
                    },
                )
                worksheet.conditional_format(
                    1,
                    0,
                    len(frame),
                    len(frame.columns) - 1,
                    {
                        "type": "formula",
                        "criteria": '=$I2=""',
                        "format": pendente_format,
                    },
                )

    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename=Relatorio_OS_IXC.xlsx'
    return response


def gerar_bytes_relatorio_atendimento(
    dataframe,
    *,
    arquivo_nome,
    total_registros,
    sucessos,
    falhas,
    limite_registros,
    ultimo_id_ixc="",
    ultima_linha_processada=None,
):
    response = gerar_resposta_relatorio_atendimento(
        dataframe,
        arquivo_nome=arquivo_nome,
        total_registros=total_registros,
        sucessos=sucessos,
        falhas=falhas,
        limite_registros=limite_registros,
        ultimo_id_ixc=ultimo_id_ixc,
        ultima_linha_processada=ultima_linha_processada,
    )
    return response.content


def gerar_bytes_relatorio_logins(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Resultado_Processamento")
        worksheet = writer.sheets["Resultado_Processamento"]
        for col_num, _ in enumerate(dataframe.columns.values):
            worksheet.set_column(col_num, col_num, 22)
    output.seek(0)
    return output.read()


def salvar_relatorio_automacao(audit, conteudo_bytes, nome_arquivo):
    destino_dir = Path(settings.MEDIA_ROOT) / "relatorios_automacoes" / "backoffice"
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome_salvo = f"audit_{audit.id}_{nome_arquivo}"
    destino = destino_dir / nome_salvo
    destino.write_bytes(conteudo_bytes)

    atualizar_auditoria_integracao(
        audit,
        detalhes={
            "relatorio_disponivel": RELATORIO_STATUS_PENDING,
            "relatorio_nome_arquivo": nome_arquivo,
            "relatorio_caminho_relativo": str(Path("relatorios_automacoes") / "backoffice" / nome_salvo).replace("\\", "/"),
            "relatorio_gerado_em": timezone.now().isoformat(),
            "relatorio_baixado_em": "",
        },
    )
    return destino


def responder_download_relatorio(conteudo_bytes, nome_arquivo):
    response = HttpResponse(
        conteudo_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename={nome_arquivo}'
    return response


@user_passes_test(grupo_backoffice_required)
@login_required
def cotacao_import(request):
    if request.method == "POST" and request.FILES.get("arquivo_cotacao"):
        if buscar_execucao_em_andamento("logins_ixc"):
            messages.warning(
                request,
                "Ja existe uma automacao de criacao de logins em andamento. Aguarde a conclusao antes de iniciar outra.",
            )
            return redirect("backoffice:cotacao_import")
        arquivo = request.FILES["arquivo_cotacao"]
        execucao_audit = None
        sucessos = 0
        falhas = 0
        ultimo_id_ixc = ""
        ultima_linha_processada = None

        try:
            df = pd.read_excel(arquivo)
            itens_importados = dataframe_to_records(df)
            registrar_auditoria_integracao(
                integration="logins_ixc",
                action="importacao_planilha",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=len(itens_importados),
                detalhes={"colunas": list(df.columns)},
                itens=itens_importados,
            )
            df["Status_Importacao"] = ""
            df["Mensagem_Importacao"] = ""
            df["ID_IXC"] = ""
            total_registros = int(df["Login_Login"].notna().sum()) if "Login_Login" in df.columns else 0
            execucao_audit = criar_auditoria_integracao(
                integration="logins_ixc",
                action="execucao_integracao",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=0,
                total_sucessos=0,
                total_erros=0,
                detalhes={
                    "colunas": list(df.columns),
                    "processamento_status": IMPORT_STATUS_RUNNING,
                    "arquivo_nome": arquivo.name,
                    "mensagem": "Criando logins no IXC.",
                    "total_previsto": total_registros,
                    "ultima_linha_processada": None,
                    "ultimo_id_ixc_criado": "",
                },
            )

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
                    ultima_linha_processada = index + 2
                    if id_ixc:
                        ultimo_id_ixc = id_ixc

                    registrar_item_auditoria_integracao(
                        execucao_audit,
                        linha_numero=index + 2,
                        status="sucesso" if status else "erro",
                        mensagem=mensagem,
                        dados_json=serializar_linha_para_auditoria(df, index),
                    )
                    atualizar_auditoria_integracao(
                        execucao_audit,
                        total_registros=sucessos + falhas,
                        total_sucessos=sucessos,
                        total_erros=falhas,
                        detalhes={
                            "processamento_status": IMPORT_STATUS_RUNNING,
                            "mensagem": "Criando logins no IXC.",
                            "ultima_linha_processada": ultima_linha_processada,
                            "ultimo_id_ixc_criado": ultimo_id_ixc,
                        },
                    )

            atualizar_auditoria_integracao(
                execucao_audit,
                total_registros=sucessos + falhas,
                total_sucessos=sucessos,
                total_erros=falhas,
                detalhes={
                    "processamento_status": IMPORT_STATUS_SUCCESS,
                    "mensagem": "Processamento concluido.",
                    "ultima_linha_processada": ultima_linha_processada,
                    "ultimo_id_ixc_criado": ultimo_id_ixc,
                },
            )

            messages.info(
                request,
                f"Processamento concluido! {sucessos} Sucessos | {falhas} Erros. O relatorio foi transferido automaticamente.",
            )
            relatorio_bytes = gerar_bytes_relatorio_logins(df)
            salvar_relatorio_automacao(execucao_audit, relatorio_bytes, "Relatorio_Importacao_IXC.xlsx")
            return responder_download_relatorio(relatorio_bytes, "Relatorio_Importacao_IXC.xlsx")

        except Exception as e:
            if execucao_audit is not None:
                atualizar_auditoria_integracao(
                    execucao_audit,
                    total_registros=sucessos + falhas,
                    total_sucessos=sucessos,
                    total_erros=falhas,
                    detalhes={
                        "processamento_status": IMPORT_STATUS_ERROR,
                        "mensagem": "Processamento interrompido por erro.",
                        "ultima_linha_processada": ultima_linha_processada,
                        "ultimo_id_ixc_criado": ultimo_id_ixc,
                        "erro_processamento": str(e),
                    },
                )
            messages.error(request, f"Erro ao processar ficheiro: {str(e)}")
            return redirect("backoffice:cotacao_import")

    return render_backoffice_automacoes(request)


@user_passes_test(grupo_backoffice_required)
@login_required
def download_modelo_cotacao(request):
    colunas = [
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

    instrucoes = {
        "Campo": colunas,
        "O que colocar?": [
            "ID do Cliente no IXC (Ex: 55)",
            "ID do Contrato do Cliente (Ex: 1151)",
            "ID do Plano de Velocidade (Ex: 4)",
            "O nome de utilizador PPPoE (Ex: joao_silva)",
            "A palavra-passe do login (Ex: 123456)",
            "CEP sem traco (Ex: 60346165)",
            "Nome do Bairro",
            "ID numerico da Cidade no IXC (Ex: 948). Nao usar nome da cidade.",
            "Rua/Avenida",
            "Numero da residencia",
            "Ponto de referencia",
            "Alguma observacao importante",
            "Velocidade contratada do endereco (Ex: 500 Mbps)",
            "Tipo de acesso do endereco (Ex: Fibra, Radio, MPLS)",
            "Bloco de IP do endereco (Ex: /30, /29, IPv4 bloco/30)",
            "Opcional: Sim ou Nao",
            "Opcional: Sim ou Nao",
        ],
        "Obrigatorio?": [
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Nao",
            "Nao",
            "Nao",
            "Nao",
            "Nao",
            "Nao",
            "Nao",
        ],
    }

    df_modelo = pd.DataFrame(columns=colunas)
    df_ajuda = pd.DataFrame(instrucoes)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, index=False, sheet_name="Preencher_Aqui")
        df_ajuda.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet_modelo = writer.sheets["Preencher_Aqui"]
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#D7E4BC", "border": 1}
        )

        for col_num, value in enumerate(df_modelo.columns.values):
            worksheet_modelo.write(0, col_num, value, header_format)
            worksheet_modelo.set_column(col_num, col_num, 24)

    output.seek(0)
    registrar_auditoria_integracao(
        integration="logins_ixc",
        action="download_modelo",
        usuario=request.user,
        arquivo_nome="modelo_importacao_ixc.xlsx",
        detalhes={"colunas": colunas},
    )
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=modelo_importacao_ixc.xlsx"
    return response


@user_passes_test(grupo_backoffice_required)
@login_required
def download_modelo_atendimento(request):
    instrucoes = {
        "Campo": ATENDIMENTO_COLUNAS,
        "O que colocar?": [
            "ID numerico do cliente no IXC",
            "ID numerico do login no IXC. Nao usar endereco, nome ou texto.",
            "ID numerico do contrato no IXC, se houver",
            "ID numerico da filial no IXC",
            "ID numerico do assunto no IXC",
            "ID numerico do departamento no IXC",
            "Titulo do atendimento",
            "Descricao detalhada do atendimento",
        ],
        "Obrigatorio?": [
            "Sim",
            "Sim",
            "Nao",
            "Sim",
            "Sim",
            "Sim",
            "Nao",
            "Sim",
        ],
        "Aceita apenas numero?": [
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Sim",
            "Nao",
            "Nao",
        ],
    }
    df_modelo = pd.DataFrame(columns=ATENDIMENTO_COLUNAS)
    df_ajuda = pd.DataFrame(instrucoes)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_OS")
        df_ajuda.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet_modelo = writer.sheets["Modelo_OS"]
        aplicar_validacao_campos_id(
            workbook,
            worksheet_modelo,
            ATENDIMENTO_COLUNAS,
            ATENDIMENTO_COLUNAS_ID,
        )

    output.seek(0)
    registrar_auditoria_integracao(
        integration="atendimento_ixc",
        action="download_modelo",
        usuario=request.user,
        arquivo_nome="Modelo_Importacao_OS_IXC.xlsx",
        detalhes={"colunas": ATENDIMENTO_COLUNAS, "campos_id_numericos": ATENDIMENTO_COLUNAS_ID},
    )
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Importacao_OS_IXC.xlsx"
    return response


@user_passes_test(grupo_backoffice_required)
@login_required
def atendimento_import(request):
    if request.method == "POST" and request.FILES.get("arquivo_atendimento"):
        if buscar_execucao_em_andamento("atendimento_ixc"):
            messages.warning(
                request,
                "Ja existe uma automacao de criacao de atendimentos em andamento. Aguarde a conclusao antes de iniciar outra.",
            )
            return redirect("backoffice:cotacao_import")
        arquivo = request.FILES["arquivo_atendimento"]
        execucao_audit = None
        sucessos = 0
        falhas = 0
        ultimo_id_ixc = ""
        ultima_linha_processada = None
        limite_registros = obter_limite_registros_atendimento_ixc()
        df = None

        try:
            if arquivo.name.lower().endswith(".csv"):
                try:
                    df = pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
                except UnicodeDecodeError:
                    arquivo.seek(0)
                    df = pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")
            else:
                try:
                    df = pd.read_excel(arquivo)
                except ValueError:
                    arquivo.seek(0)
                    try:
                        df = pd.read_csv(arquivo, sep=None, engine="python", encoding="utf-8")
                    except UnicodeDecodeError:
                        arquivo.seek(0)
                        df = pd.read_csv(arquivo, sep=None, engine="python", encoding="latin1")

            itens_importados = dataframe_to_records(df)
            registrar_auditoria_integracao(
                integration="atendimento_ixc",
                action="importacao_planilha",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=len(itens_importados),
                detalhes={"colunas": list(df.columns)},
                itens=itens_importados,
            )
            total_registros = contar_registros_atendimento_importaveis(df)
            if total_registros > limite_registros:
                messages.error(
                    request,
                    (
                        f"O arquivo possui {total_registros} registros processaveis, acima do limite "
                        f"seguro de {limite_registros} por processamento. Divida a planilha em lotes "
                        "menores antes de importar novamente."
                    ),
                )
                return redirect("backoffice:cotacao_import")

            df["Status_Importacao"] = ""
            df["Mensagem_Importacao"] = ""
            df["ID_IXC"] = ""
            execucao_audit = criar_auditoria_integracao(
                integration="atendimento_ixc",
                action="execucao_integracao",
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=0,
                total_sucessos=0,
                total_erros=0,
                detalhes={
                    "colunas": list(df.columns),
                    "processamento_status": IMPORT_STATUS_RUNNING,
                    "arquivo_nome": arquivo.name,
                    "mensagem": "Criando atendimentos no IXC.",
                    "limite_registros_por_processamento": limite_registros,
                    "total_previsto": total_registros,
                    "ultima_linha_processada": None,
                    "ultimo_id_ixc_criado": "",
                },
            )

            for index, linha in df.iterrows():
                if pd.notna(linha.get("Cliente_ID")):
                    status, mensagem, id_ixc = executar_abertura_atendimento(
                        linha,
                        usuario_sistema=request.user,
                    )

                    if status:
                        sucessos += 1
                        df.at[index, "Status_Importacao"] = "SUCESSO"
                    else:
                        falhas += 1
                        df.at[index, "Status_Importacao"] = "ERRO"

                    df.at[index, "Mensagem_Importacao"] = mensagem
                    df.at[index, "ID_IXC"] = id_ixc or ""
                    ultima_linha_processada = index + 2
                    if id_ixc:
                        ultimo_id_ixc = id_ixc

                    registrar_item_auditoria_integracao(
                        execucao_audit,
                        linha_numero=index + 2,
                        status="sucesso" if status else "erro",
                        mensagem=mensagem,
                        dados_json=serializar_linha_para_auditoria(df, index),
                    )
                    atualizar_auditoria_integracao(
                        execucao_audit,
                        total_registros=sucessos + falhas,
                        total_sucessos=sucessos,
                        total_erros=falhas,
                        detalhes={
                            "processamento_status": IMPORT_STATUS_RUNNING,
                            "mensagem": "Criando atendimentos no IXC.",
                            "ultima_linha_processada": ultima_linha_processada,
                            "ultimo_id_ixc_criado": ultimo_id_ixc,
                        },
                    )

            atualizar_auditoria_integracao(
                execucao_audit,
                total_registros=sucessos + falhas,
                total_sucessos=sucessos,
                total_erros=falhas,
                detalhes={
                    "processamento_status": IMPORT_STATUS_SUCCESS,
                    "mensagem": "Processamento concluido.",
                    "ultima_linha_processada": ultima_linha_processada,
                    "ultimo_id_ixc_criado": ultimo_id_ixc,
                },
            )
            relatorio_bytes = gerar_bytes_relatorio_atendimento(
                df,
                arquivo_nome=arquivo.name,
                total_registros=total_registros,
                sucessos=sucessos,
                falhas=falhas,
                limite_registros=limite_registros,
                ultimo_id_ixc=ultimo_id_ixc,
                ultima_linha_processada=ultima_linha_processada,
            )
            salvar_relatorio_automacao(execucao_audit, relatorio_bytes, "Relatorio_OS_IXC.xlsx")
            return responder_download_relatorio(relatorio_bytes, "Relatorio_OS_IXC.xlsx")

        except Exception as e:
            if execucao_audit is not None:
                atualizar_auditoria_integracao(
                    execucao_audit,
                    total_registros=sucessos + falhas,
                    total_sucessos=sucessos,
                    total_erros=falhas,
                    detalhes={
                        "processamento_status": IMPORT_STATUS_ERROR,
                        "mensagem": "Processamento interrompido por erro.",
                        "ultima_linha_processada": ultima_linha_processada,
                        "ultimo_id_ixc_criado": ultimo_id_ixc,
                        "erro_processamento": str(e),
                    },
                )
            print("\n--- ERRO GRAVE NO VIEWS.PY (OS) ---")
            print(f"Motivo: {str(e)}")
            print("----------------------------------\n")
            return HttpResponse(status=400)

    return redirect("backoffice:cotacao_import")


@user_passes_test(grupo_backoffice_required)
@login_required
def download_relatorio_automacao(request, audit_id):
    audit = IntegrationAudit.objects.filter(
        pk=audit_id,
        integration__in=["logins_ixc", "atendimento_ixc"],
        action="execucao_integracao",
    ).first()
    if not audit:
        raise Http404("Relatorio nao encontrado.")

    detalhes = audit.detalhes_json or {}
    caminho_relativo = detalhes.get("relatorio_caminho_relativo")
    nome_arquivo = detalhes.get("relatorio_nome_arquivo") or f"relatorio_{audit.id}.xlsx"
    if not caminho_relativo:
        raise Http404("Relatorio nao disponivel.")

    arquivo = Path(settings.MEDIA_ROOT) / caminho_relativo
    if not arquivo.exists():
        raise Http404("Arquivo do relatorio nao encontrado.")

    atualizar_auditoria_integracao(
        audit,
        detalhes={
            "relatorio_disponivel": False,
            "relatorio_baixado_em": timezone.now().isoformat(),
            "relatorio_baixado_por": getattr(request.user, "username", "") or "",
        },
    )

    return FileResponse(
        arquivo.open("rb"),
        as_attachment=True,
        filename=nome_arquivo,
    )
