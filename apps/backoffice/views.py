from io import BytesIO

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from scripts.integracoes.backoffice.cria_atendimento_ixc import (
    executar_abertura_atendimento,
)
from scripts.integracoes.backoffice.cria_login_atendimento import (
    executar_cadastro_ixc,
)


def grupo_backoffice_required(user):
    if not user.is_authenticated:
        return False
    if user.groups.filter(name="Backoffice").exists() or user.is_superuser:
        return True
    raise PermissionDenied


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

            sucessos = 0
            falhas = 0
            itens_execucao = []

            for index, linha in df.iterrows():
                if pd.notna(linha.get("Login_Login")):
                    status, mensagem = executar_cadastro_ixc(linha)

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
                            "dados_json": {str(k).strip(): linha[k] for k in df.columns if k in linha},
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
    colunas = [
        "Cliente_ID",
        "Login_Contrato_ID",
        "Plano_ID",
        "Login_Login",
        "Login_Senha_Cliente",
        "End_CEP",
        "End_Bairro",
        "End_Cidade",
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
            "Codigo da Cidade no IXC (Ex: 948)",
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
    colunas = [
        "Cliente_ID",
        "Login_ID",
        "Contrato_ID",
        "Filial_ID",
        "Assunto_ID",
        "Departamento_ID",
        "Assunto_Descricao",
        "Descricao",
    ]
    df = pd.DataFrame(columns=colunas)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Modelo_OS")

    output.seek(0)
    registrar_auditoria_integracao(
        integration="atendimento_ixc",
        action="download_modelo",
        usuario=request.user,
        arquivo_nome="Modelo_Importacao_OS_IXC.xlsx",
        detalhes={"colunas": colunas},
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
            sucessos = 0
            falhas = 0
            itens_execucao = []

            for index, linha in df.iterrows():
                if pd.notna(linha.get("Cliente_ID")):
                    status, mensagem = executar_abertura_atendimento(linha)

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
                            "dados_json": {str(k).strip(): linha[k] for k in df.columns if k in linha},
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
