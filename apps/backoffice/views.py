from io import BytesIO
import re

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from scripts.integracoes.backoffice.cadastrar_cliente_ixc import executar_cadastro_cliente_ixc, validar_linha_pre_envio
from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    executar_abertura_atendimento,
    validar_tipo_processo,
    TIPOS_PROCESSO,
)
from scripts.integracoes.backoffice.cria_login_atendimento import (
    executar_cadastro_ixc,
)
from scripts.integracoes.ixc_client import IXCClient

CADASTRO_CLIENTE_IXC_INTEGRATION = "cadastro_cliente_ixc"

ATENDIMENTO_COLUNAS = [
    "Cliente_ID",
    "Login_ID",
    "Contrato_ID",
    "Filial_ID",
    "Assunto_ID",
    "Departamento_ID",
    "Tipo_Processo",
    "Workflow_ID",
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
    "Workflow_ID",
]

ATENDIMENTO_COLUNAS_LISTA = {
    "Tipo_Processo": TIPOS_PROCESSO,
}


def grupo_backoffice_required(user):
    if not user.is_authenticated:
        return False
    if user.groups.filter(name="Backoffice").exists() or user.is_superuser:
        return True
    raise PermissionDenied


def aplicar_validacao_campos_id(workbook, worksheet, colunas, campos_id, campos_lista=None):
    header_format = workbook.add_format({"bold": True, "bg_color": "#D7E4BC", "border": 1})
    inteiro_format = workbook.add_format({"num_format": "0"})
    campos_lista = campos_lista or {}

    for col_num, value in enumerate(colunas):
        worksheet.write(0, col_num, value, header_format)
        worksheet.set_column(col_num, col_num, 24, inteiro_format if value in campos_id else None)

        if value in campos_id:
            worksheet.data_validation(
                1, col_num, 5000, col_num,
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
        elif value in campos_lista:
            opcoes = campos_lista[value]
            worksheet.data_validation(
                1, col_num, 5000, col_num,
                {
                    "validate": "list",
                    "source": opcoes,
                    "ignore_blank": False,
                    "input_title": f"Selecione o {value}",
                    "input_message": f"Opcoes: {', '.join(opcoes)}",
                    "error_title": "Valor invalido",
                    "error_message": f"O campo {value} aceita apenas: {', '.join(opcoes)}.",
                },
            )


def serializar_linha_para_auditoria(dataframe, index):
    return {str(k).strip(): dataframe.at[index, k] for k in dataframe.columns}


@user_passes_test(grupo_backoffice_required)
@login_required
def cotacao_import(request):
    if request.method == "POST" and request.FILES.get("arquivo_cotacao"):
        arquivo = request.FILES["arquivo_cotacao"]

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
                usuario=request.user,
                arquivo_nome=arquivo.name,
                total_registros=sucessos + falhas,
                total_sucessos=sucessos,
                total_erros=falhas,
                detalhes={"colunas": list(df.columns)},
                itens=itens_execucao,
            )

            messages.info(
                request,
                f"Processamento concluido! {sucessos} Sucessos | {falhas} Erros. O relatorio foi transferido automaticamente.",
            )

            output = BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Resultado_Processamento")
                worksheet = writer.sheets["Resultado_Processamento"]
                for col_num, _ in enumerate(df.columns.values):
                    worksheet.set_column(col_num, col_num, 22)

            output.seek(0)

            response = HttpResponse(
                output.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=Relatorio_Importacao_IXC.xlsx"
            return response

        except Exception as e:
            messages.error(request, f"Erro ao processar ficheiro: {str(e)}")
            return redirect("backoffice:cotacao_import")

    return render(request, "backoffice/cotacao_import.html")


@user_passes_test(grupo_backoffice_required)
@login_required
def download_modelo_cotacao(request):
    if request.method != "POST":
        return redirect("backoffice:cotacao_import")
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
    if request.method != "POST":
        return redirect("backoffice:cotacao_import")
    campos_obrigatorios = set(ATENDIMENTO_COLUNAS) - {"Workflow_ID"}

    instrucoes_campos = [
        {
            "Campo": "Cliente_ID",
            "Descricao": "ID numerico do cliente no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Use apenas o ID numerico. Ex.: 1234",
        },
        {
            "Campo": "Login_ID",
            "Descricao": "ID numerico do login do cliente no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Nao usar nome, endereco ou texto. Ex.: 5678",
        },
        {
            "Campo": "Contrato_ID",
            "Descricao": "ID numerico do contrato no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Use apenas o ID numerico do contrato no IXC.",
        },
        {
            "Campo": "Filial_ID",
            "Descricao": "ID numerico da filial do IXC responsavel pelo atendimento.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Use apenas o ID numerico. Ex.: 1",
        },
        {
            "Campo": "Assunto_ID",
            "Descricao": "ID numerico do assunto do ticket cadastrado no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Consulte no IXC em Suporte > Assuntos. Use apenas o ID numerico.",
        },
        {
            "Campo": "Departamento_ID",
            "Descricao": "ID numerico do departamento/setor do IXC que vai receber o atendimento.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Consulte no IXC em Suporte > Departamentos. Use apenas o ID numerico.",
        },
        {
            "Campo": "Tipo_Processo",
            "Descricao": "Define o tipo de processo que sera aberto no IXC. Controla se o workflow sera acionado ou nao.",
            "Tipo de dado": "Lista (Avulso / Cotacao Parceiro / Outro)",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": (
                "Avulso = sem workflow, nenhuma OS gerada automaticamente. "
                "Cotacao Parceiro = workflow 18, gera OS de instalacao automaticamente. "
                "Outro = usa o workflow informado em Workflow_ID."
            ),
        },
        {
            "Campo": "Workflow_ID",
            "Descricao": "ID numerico do workflow do IXC acionado ao abrir o atendimento.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Condicional (depende do Tipo_Processo)",
            "Regras / Exemplo": (
                "Avulso: deixe VAZIO. "
                "Cotacao Parceiro: informe exatamente 18. "
                "Outro: informe o ID do workflow desejado. "
                "Qualquer divergencia bloqueia o envio de toda a planilha."
            ),
        },
        {
            "Campo": "Assunto_Descricao",
            "Descricao": "Titulo do atendimento exibido no IXC.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Titulo que aparece no atendimento dentro do IXC.",
        },
        {
            "Campo": "Descricao",
            "Descricao": "Texto da primeira mensagem do atendimento no IXC.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": (
                "Descreva o motivo do atendimento. "
                "O sistema acrescenta automaticamente o nome e horario do usuario que realizou a importacao."
            ),
        },
    ]

    regras_tipo_processo = [
        {
            "Tipo_Processo": "Avulso",
            "Workflow_ID": "Vazio (deixar em branco)",
            "Resultado": "VALIDO",
            "O que acontece no IXC": "Cria o atendimento sem acionar nenhum workflow. Nenhuma OS e gerada automaticamente.",
        },
        {
            "Tipo_Processo": "Avulso",
            "Workflow_ID": "Qualquer numero preenchido",
            "Resultado": "ERRO",
            "O que acontece no IXC": "Bloqueado antes de enviar. Avulso nao aceita Workflow_ID. Remova o valor ou mude o Tipo_Processo.",
        },
        {
            "Tipo_Processo": "Cotacao Parceiro",
            "Workflow_ID": "18",
            "Resultado": "VALIDO",
            "O que acontece no IXC": "Aciona o workflow 18 do IXC, que gera a OS de instalacao automaticamente.",
        },
        {
            "Tipo_Processo": "Cotacao Parceiro",
            "Workflow_ID": "Vazio ou diferente de 18",
            "Resultado": "ERRO",
            "O que acontece no IXC": "Bloqueado antes de enviar. Cotacao Parceiro exige exatamente Workflow_ID = 18.",
        },
        {
            "Tipo_Processo": "Outro",
            "Workflow_ID": "Qualquer numero preenchido",
            "Resultado": "VALIDO",
            "O que acontece no IXC": "Aciona o workflow informado no IXC. Verifique o ID correto antes de importar.",
        },
        {
            "Tipo_Processo": "Outro",
            "Workflow_ID": "Vazio",
            "Resultado": "ERRO",
            "O que acontece no IXC": "Bloqueado antes de enviar. Outro exige Workflow_ID preenchido.",
        },
    ]

    df_instrucoes = pd.DataFrame(instrucoes_campos)
    df_modelo = pd.DataFrame(columns=ATENDIMENTO_COLUNAS)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_OS")
        df_instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet_modelo = writer.sheets["Modelo_OS"]
        worksheet_ajuda = writer.sheets["Instrucoes_Ajuda"]

        aplicar_validacao_campos_id(
            workbook,
            worksheet_modelo,
            ATENDIMENTO_COLUNAS,
            ATENDIMENTO_COLUNAS_ID,
            campos_lista=ATENDIMENTO_COLUNAS_LISTA,
        )

        header_format = workbook.add_format({"bold": True, "bg_color": "#D7E4BC", "border": 1})
        header_obrig_format = workbook.add_format({"bold": True, "bg_color": "#D7E4BC", "border": 1})
        header_text_format = workbook.add_format({"bold": True})
        required_star_format = workbook.add_format({"bold": True, "font_color": "#DC2626"})

        for col_num, col_name in enumerate(ATENDIMENTO_COLUNAS):
            largura = 28 if col_name in {"Assunto_Descricao", "Descricao"} else 20
            if col_name in campos_obrigatorios:
                worksheet_modelo.write_rich_string(
                    0, col_num,
                    header_text_format, col_name,
                    required_star_format, "*",
                    header_obrig_format,
                )
            else:
                worksheet_modelo.write(0, col_num, col_name, header_format)
            worksheet_modelo.set_column(col_num, col_num, largura)

        larguras_ajuda = [20, 42, 26, 22, 60]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        titulo_format = workbook.add_format({
            "bold": True, "bg_color": "#1E3A5F", "font_color": "#FFFFFF", "border": 1,
        })
        secao_header_format = workbook.add_format({
            "bold": True, "bg_color": "#D7E4BC", "border": 1,
        })
        secao_cell_format = workbook.add_format({"border": 1, "text_wrap": True})
        valido_format = workbook.add_format({
            "border": 1, "bg_color": "#D9EAD3", "bold": True, "text_wrap": True,
        })
        erro_format = workbook.add_format({
            "border": 1, "bg_color": "#F4CCCC", "bold": True, "text_wrap": True,
        })
        aviso_format = workbook.add_format({
            "bold": True, "bg_color": "#FCE5CD", "border": 1, "text_wrap": True,
        })

        linha_ref = len(instrucoes_campos) + 2

        worksheet_ajuda.merge_range(
            linha_ref, 0, linha_ref, 4,
            "Regras de validacao: Tipo_Processo x Workflow_ID",
            titulo_format,
        )
        linha_ref += 1

        cabecalhos_regras = ["Tipo_Processo", "Workflow_ID", "Resultado", "O que acontece no IXC"]
        for col_num, cab in enumerate(cabecalhos_regras):
            worksheet_ajuda.write(linha_ref, col_num, cab, secao_header_format)
        linha_ref += 1

        for regra in regras_tipo_processo:
            resultado = regra["Resultado"]
            fmt_resultado = valido_format if resultado == "VALIDO" else erro_format
            worksheet_ajuda.write(linha_ref, 0, regra["Tipo_Processo"], secao_cell_format)
            worksheet_ajuda.write(linha_ref, 1, regra["Workflow_ID"], secao_cell_format)
            worksheet_ajuda.write(linha_ref, 2, resultado, fmt_resultado)
            worksheet_ajuda.write(linha_ref, 3, regra["O que acontece no IXC"], secao_cell_format)
            worksheet_ajuda.set_row(linha_ref, 36)
            linha_ref += 1

        linha_ref += 1
        worksheet_ajuda.merge_range(
            linha_ref, 0, linha_ref, 4,
            "ATENCAO: Validacao 'tudo ou nada'",
            titulo_format,
        )
        linha_ref += 1
        worksheet_ajuda.merge_range(
            linha_ref, 0, linha_ref, 4,
            (
                "Se qualquer linha da planilha tiver divergencia entre Tipo_Processo e Workflow_ID, "
                "NENHUM registro e enviado ao IXC. O sistema retorna a planilha com os erros identificados "
                "em cada linha. Corrija todos antes de reimportar."
            ),
            aviso_format,
        )
        worksheet_ajuda.set_row(linha_ref, 48)

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
        arquivo = request.FILES["arquivo_atendimento"]

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
                    usuario=request.user,
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
                output.seek(0)
                response = HttpResponse(
                    output.read(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Content-Disposition"] = "attachment; filename=Relatorio_OS_IXC.xlsx"
                return response

            # --- Fase 2: todos passaram — enviar para a API ---
            sucessos = 0
            falhas = 0
            itens_execucao = []

            for index in indices_com_cliente:
                status, mensagem = executar_abertura_atendimento(
                    df.loc[index],
                    usuario_sistema=request.user,
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
                usuario=request.user,
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

            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=Relatorio_OS_IXC.xlsx"
            return response

        except Exception as e:
            print("\n--- ERRO GRAVE NO VIEWS.PY (OS) ---")
            print(f"Motivo: {str(e)}")
            print("----------------------------------\n")
            return HttpResponse(status=400)

    return redirect("backoffice:cotacao_import")


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


def _buscar_opcoes_ixc(endpoint, campo_nome="nome", limite=200):
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
        return []


@user_passes_test(grupo_backoffice_required)
@login_required
def cadastrar_clientes_ixc(request):
    if request.method != "POST":
        return redirect("backoffice:cotacao_import")

    arquivo = request.FILES.get("arquivo_cadastro_cliente_ixc")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar o cadastro de clientes no IXC.")
        return redirect("backoffice:cotacao_import")

    try:
        df = _ler_dataframe_upload(arquivo)
        itens_importados = dataframe_to_records(df)
        registrar_auditoria_integracao(
            integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
            action="importacao_planilha",
            usuario=request.user,
            arquivo_nome=arquivo.name,
            total_registros=len(itens_importados),
            detalhes={"colunas": list(df.columns)},
            itens=itens_importados,
        )

        # --- fase 1: pre-validacao de todos os registros ---
        opcoes_tipo_cliente = _buscar_opcoes_ixc("cliente_tipo")
        opcoes_filial = _buscar_opcoes_ixc("filial")
        ids_tipo_cliente = {id_ for id_, _ in opcoes_tipo_cliente} if opcoes_tipo_cliente else None
        ids_filial = {id_ for id_, _ in opcoes_filial} if opcoes_filial else None

        df["Status_Validacao"] = ""
        df["Erros_Validacao"] = ""

        total_com_erro = 0
        total_ok = 0

        for index, linha in df.iterrows():
            if not (pd.notna(linha.get("Razao_Social")) or pd.notna(linha.get("RAZAO_SOCIAL"))):
                continue
            erros = validar_linha_pre_envio(dict(linha), ids_tipo_cliente, ids_filial)
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
                usuario=request.user,
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

            response = HttpResponse(
                output.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=Validacao_Cadastro_Clientes_IXC.xlsx"
            return response

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
                    status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(linha, usuario_sistema=request.user)
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
            usuario=request.user,
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

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Cadastro_Clientes_IXC.xlsx"
        return response
    except Exception as exc:
        messages.error(request, f"Falha ao processar o cadastro de clientes no IXC: {exc}")
        return redirect("backoffice:cotacao_import")


@user_passes_test(grupo_backoffice_required)
@login_required
def download_template_cadastro_cliente_ixc(request):
    if request.method != "POST":
        return redirect("backoffice:cotacao_import")
    opcoes_tipo_cliente = _buscar_opcoes_ixc("cliente_tipo")
    opcoes_filial = _buscar_opcoes_ixc("filial")

    colunas = [
        "Razao_Social",
        "CNPJ_CPF",
        "Nome_Fantasia",
        "Tipo_Pessoa",
        "IE_RG",
        "Contribuinte_ICMS",
        "Tipo_Cliente_Fiscal",
        "Tipo_Localidade",
        "CEP",
        "Endereco",
        "Numero",
        "Bairro",
        "Cidade_ID_IXC",
        "Complemento",
        "Referencia",
        "Contato_Nome",
        "Email",
        "Telefone",
        "Tipo_Cliente_ID",
        "Tipo_Assinante_ID",
        "Filial_ID",
        "Vendedor_ID",
        "Observacao",
        "Ativo",
        "Permitir_Duplicidade",
        "Prospeccao",
        "Confirmar_Cadastro",
    ]
    campos_obrigatorios_planilha = {
        "Razao_Social",
        "CNPJ_CPF",
        "CEP",
        "Endereco",
        "Bairro",
        "Cidade_ID_IXC",
        "Email",
        "Telefone",
        "Tipo_Cliente_ID",
        "Filial_ID",
        "Confirmar_Cadastro",
    }
    instrucoes_campos = [
        {"Campo": "Razao_Social", "Descricao": "Nome ou razao social que sera cadastrado no cliente do IXC.", "Tipo de dado": "Texto", "Obrigatorio?": "Sim", "Regras / Exemplo": "Ex.: CLIENTE TESTE LTDA"},
        {"Campo": "CNPJ_CPF", "Descricao": "Documento principal do cliente. O sistema usa para evitar duplicidade.", "Tipo de dado": "Texto numerico", "Obrigatorio?": "Sim", "Regras / Exemplo": "Aceita CPF ou CNPJ, com ou sem mascara. Ex.: 12345678000199"},
        {"Campo": "Nome_Fantasia", "Descricao": "Nome fantasia do cliente no IXC.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Ex.: CLIENTE TESTE"},
        {"Campo": "Tipo_Pessoa", "Descricao": "Tipo de pessoa do cadastro.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Use F/PF para fisica ou J/PJ para juridica. Se vazio, a automacao infere pelo documento antes de enviar."},
        {"Campo": "IE_RG", "Descricao": "Inscricao estadual ou RG do cliente.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Pode informar ISENTO quando aplicavel."},
        {"Campo": "Contribuinte_ICMS", "Descricao": "Indica se o cliente e contribuinte de ICMS.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Use N para nao contribuinte, S para contribuinte ou I para isento. Se vazio, a automacao infere o valor antes de enviar."},
        {"Campo": "Tipo_Cliente_Fiscal", "Descricao": "Tipo de cliente fiscal do IXC, enviado pela API como iss_classificacao_padrao.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "01=Comercial | 02=Industrial | 03=Prestacao de Servicos | 04=Produtor Rural | 05=Simples Nacional | 99=Outros. Se vazio, a automacao envia 99."},
        {"Campo": "Tipo_Localidade", "Descricao": "Tipo de localidade do endereco do cliente no IXC.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Use U para Urbano ou R para Rural. Nao coloque UF/estado aqui. Se vazio ou valor invalido, a automacao envia U."},
        {"Campo": "CEP", "Descricao": "CEP do endereco principal do cliente.", "Tipo de dado": "Texto numerico", "Obrigatorio?": "Sim", "Regras / Exemplo": "Aceita com ou sem mascara. Ex.: 60000-000"},
        {"Campo": "Endereco", "Descricao": "Logradouro do endereco principal.", "Tipo de dado": "Texto", "Obrigatorio?": "Sim", "Regras / Exemplo": "Ex.: RUA EXEMPLO"},
        {"Campo": "Numero", "Descricao": "Numero do endereco principal.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Use somente numeros ou SN para sem numero. Se vazio, a automacao envia SN."},
        {"Campo": "Bairro", "Descricao": "Bairro do endereco principal.", "Tipo de dado": "Texto", "Obrigatorio?": "Sim", "Regras / Exemplo": "Ex.: CENTRO"},
        {"Campo": "Cidade_ID_IXC", "Descricao": "ID numerico da cidade cadastrada no IXC.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Sim", "Regras / Exemplo": "Use apenas o ID numerico da cidade no IXC. Ex.: 887"},
        {"Campo": "Complemento", "Descricao": "Complemento do endereco principal.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Ex.: SALA 02"},
        {"Campo": "Referencia", "Descricao": "Referencia adicional do endereco.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Ex.: PROXIMO AO SUPERMERCADO"},
        {"Campo": "Contato_Nome", "Descricao": "Nome do contato principal do cliente.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Ex.: JOAO SILVA"},
        {"Campo": "Email", "Descricao": "E-mail principal do cliente.", "Tipo de dado": "Texto", "Obrigatorio?": "Sim", "Regras / Exemplo": "Ex.: contato@cliente.com.br"},
        {"Campo": "Telefone", "Descricao": "Telefone principal do cliente.", "Tipo de dado": "Texto numerico", "Obrigatorio?": "Sim", "Regras / Exemplo": "Aceita com ou sem mascara. Ex.: 85999999999"},
        {"Campo": "Tipo_Cliente_ID", "Descricao": "ID do tipo de cliente ja cadastrado no IXC.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Sim", "Regras / Exemplo": ("Opcoes disponiveis: " + (", ".join(f"{id_} = {nome}" for id_, nome in opcoes_tipo_cliente) if opcoes_tipo_cliente else "consulte a aba Instrucoes_Ajuda") + ". Use apenas o ID numerico.")},
        {"Campo": "Tipo_Assinante_ID", "Descricao": "ID do tipo de assinante no IXC.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Legenda comum: 1 Comercial/Industrial, 2 Poder Publico, 3 Residencial/Pessoa Fisica, 4 Publico, 5 Semi-Publico, 6 Outros. Se vazio, a automacao envia 3."},
        {"Campo": "Filial_ID", "Descricao": "ID da filial do IXC associada ao cliente.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Sim", "Regras / Exemplo": ("Opcoes disponiveis: " + (", ".join(f"{id_} = {nome}" for id_, nome in opcoes_filial) if opcoes_filial else "consulte a aba Instrucoes_Ajuda") + ". Use apenas o ID numerico.")},
        {"Campo": "Vendedor_ID", "Descricao": "ID do vendedor/responsavel no IXC.", "Tipo de dado": "Numero inteiro", "Obrigatorio?": "Nao", "Regras / Exemplo": "Use apenas o ID numerico do IXC."},
        {"Campo": "Observacao", "Descricao": "Observacao administrativa enviada para o cadastro do cliente.", "Tipo de dado": "Texto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Campo livre para observacoes internas."},
        {"Campo": "Ativo", "Descricao": "Define se o cliente sera criado como ativo ou inativo.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao na planilha / Sim no IXC", "Regras / Exemplo": "Aceita S ou N. Se vazio, a automacao assume S antes de enviar."},
        {"Campo": "Permitir_Duplicidade", "Descricao": "Permite cadastrar o cliente mesmo que ja exista outro com o mesmo CNPJ/CPF no IXC.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Use Sim para ignorar a verificacao de duplicidade e forcar o cadastro. Se vazio ou Nao, o sistema bloqueia o cadastro se ja houver cliente com o mesmo CNPJ/CPF ou razao social."},
        {"Campo": "Prospeccao", "Descricao": "Indica se o cliente deve ser marcado como prospeccao na aba CRM do IXC.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Nao", "Regras / Exemplo": "Use Sim ou S para marcar como prospeccao, Nao ou N para nao marcar. Se vazio, o campo nao e enviado ao IXC."},
        {"Campo": "Confirmar_Cadastro", "Descricao": "Confirmacao explicita para autorizar o cadastro em massa.", "Tipo de dado": "Texto curto", "Obrigatorio?": "Sim", "Regras / Exemplo": "Digite exatamente SIM."},
    ]
    instrucoes = pd.DataFrame(instrucoes_campos)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_modelo = pd.DataFrame(
            [
                {
                    "Razao_Social": "Teste de Cadastro de clinete",
                    "CNPJ_CPF": "123.456.789-09",
                    "Nome_Fantasia": "Teste de Cadastro de clinete",
                    "Tipo_Pessoa": "F",
                    "IE_RG": "",
                    "Contribuinte_ICMS": "N",
                    "Tipo_Cliente_Fiscal": "99",
                    "Tipo_Localidade": "U",
                    "CEP": "60863-012",
                    "Endereco": "Rua Canario",
                    "Numero": "SN",
                    "Bairro": "Messejana",
                    "Cidade_ID_IXC": "948",
                    "Complemento": "",
                    "Referencia": "",
                    "Contato_Nome": "",
                    "Email": "teste.cadastro@exemplo.com.br",
                    "Telefone": "(00) 00000-0000",
                    "Tipo_Cliente_ID": "8",
                    "Tipo_Assinante_ID": "3",
                    "Filial_ID": "1",
                    "Vendedor_ID": "",
                    "Observacao": "Cliente criado via teste de cadastro em massa pela API.",
                    "Ativo": "S",
                    "Permitir_Duplicidade": "Nao",
                    "Prospeccao": "Nao",
                    "Confirmar_Cadastro": "SIM",
                }
            ],
            columns=colunas,
        )
        df_modelo.to_excel(writer, index=False, sheet_name="Modelo_Cadastro_Cliente_IXC")
        instrucoes.to_excel(writer, index=False, sheet_name="Instrucoes_Ajuda")

        workbook = writer.book
        worksheet = writer.sheets["Modelo_Cadastro_Cliente_IXC"]
        worksheet_ajuda = writer.sheets["Instrucoes_Ajuda"]
        header_format = workbook.add_format({"bg_color": "#DCFCE7", "border": 1})
        header_plain_format = workbook.add_format({"bold": True, "bg_color": "#DCFCE7", "border": 1})
        header_text_format = workbook.add_format({"bold": True})
        required_star_format = workbook.add_format({"bold": True, "font_color": "#DC2626"})
        integer_format = workbook.add_format({"num_format": "0"})

        for col_num, value in enumerate(colunas):
            if value in campos_obrigatorios_planilha:
                worksheet.write_rich_string(0, col_num, header_text_format, value, required_star_format, "*", header_format)
            else:
                worksheet.write(0, col_num, value, header_plain_format)
            largura = 22
            if value in {"Razao_Social", "Nome_Fantasia", "Endereco", "Observacao"}:
                largura = 36
            if value in {"Complemento", "Referencia", "Contato_Nome", "Email"}:
                largura = 28
            formato = integer_format if value in {"Cidade_ID_IXC", "Tipo_Cliente_ID", "Tipo_Assinante_ID", "Filial_ID", "Vendedor_ID"} else None
            worksheet.set_column(col_num, col_num, largura, formato)

        larguras_ajuda = [24, 40, 18, 16, 55]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        secao_titulo_format = workbook.add_format({"bold": True, "bg_color": "#1E3A5F", "font_color": "#FFFFFF", "border": 1})
        secao_header_format = workbook.add_format({"bold": True, "bg_color": "#DCFCE7", "border": 1})
        secao_cell_format = workbook.add_format({"border": 1})

        linha_ref = len(instrucoes_campos) + 2
        for titulo, opcoes in [
            ("Opcoes disponiveis: Tipo_Cliente_ID", opcoes_tipo_cliente),
            ("Opcoes disponiveis: Filial_ID", opcoes_filial),
        ]:
            worksheet_ajuda.merge_range(linha_ref, 0, linha_ref, 1, titulo, secao_titulo_format)
            linha_ref += 1
            worksheet_ajuda.write(linha_ref, 0, "ID", secao_header_format)
            worksheet_ajuda.write(linha_ref, 1, "Nome", secao_header_format)
            linha_ref += 1
            if opcoes:
                for id_val, nome_val in opcoes:
                    worksheet_ajuda.write(linha_ref, 0, id_val, secao_cell_format)
                    worksheet_ajuda.write(linha_ref, 1, nome_val, secao_cell_format)
                    linha_ref += 1
            else:
                worksheet_ajuda.merge_range(linha_ref, 0, linha_ref, 1, "Nao foi possivel carregar as opcoes do IXC. Consulte o sistema.", secao_cell_format)
                linha_ref += 1
            linha_ref += 1

        worksheet.data_validation(1, 6, 5000, 6, {"validate": "list", "source": ["01", "02", "03", "04", "05", "99"], "ignore_blank": True, "input_title": "Tipo_Cliente_Fiscal", "input_message": "01=Comercial 02=Industrial 03=Servicos 04=Prod.Rural 05=Simples 99=Outros"})
        worksheet.data_validation(1, 7, 5000, 7, {"validate": "list", "source": ["U", "R"], "ignore_blank": True, "input_title": "Tipo_Localidade", "input_message": "Use U para Urbano ou R para Rural.", "error_title": "Valor invalido", "error_message": "Tipo_Localidade deve ser U (Urbano) ou R (Rural)."})
        worksheet.data_validation(1, 23, 5000, 23, {"validate": "list", "source": ["S", "N"], "ignore_blank": True, "input_title": "Ativo", "input_message": "Deixe S para ativo ou N para inativo."})
        worksheet.data_validation(1, 24, 5000, 24, {"validate": "list", "source": ["Sim", "Nao"], "ignore_blank": True, "input_title": "Permitir_Duplicidade", "input_message": "Sim para cadastrar mesmo que o CNPJ/CPF ja exista no IXC. Nao ou vazio para bloquear duplicatas."})
        worksheet.data_validation(1, 25, 5000, 25, {"validate": "list", "source": ["Sim", "Nao"], "ignore_blank": True, "input_title": "Prospeccao", "input_message": "Sim para marcar como prospeccao no CRM do IXC, Nao para nao marcar."})
        worksheet.data_validation(1, 26, 5000, 26, {"validate": "list", "source": ["SIM"], "ignore_blank": False, "input_title": "Confirmacao obrigatoria", "input_message": "Digite SIM para autorizar o cadastro do cliente.", "error_title": "Confirmacao obrigatoria", "error_message": "Para cadastrar, o campo Confirmar_Cadastro deve conter SIM."})

    registrar_auditoria_integracao(
        integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
        action="download_modelo",
        usuario=request.user,
        arquivo_nome="Modelo_Cadastro_Clientes_IXC.xlsx",
        detalhes={"colunas": colunas},
    )

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Cadastro_Clientes_IXC.xlsx"
    return response
