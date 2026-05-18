from io import BytesIO
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from email.utils import parseaddr
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.core.exceptions import (
    RequestDataTooBig,
    SuspiciousOperation,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.http import HttpResponse, UnreadablePostError
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import redirect, render
from django.utils.datastructures import MultiValueDictKeyError

from apps.core.integration_audit import dataframe_to_records, registrar_auditoria_integracao
from core.models import IntegrationAudit
from core.views import grupo_Administrador_required
from core_admin.models import ConfiguracaoEmailEnvio
from auditoria.models import RestoreBackupAuditoria
from scripts.integracoes.backoffice.cadastrar_cliente_ixc import executar_cadastro_cliente_ixc
from scripts.integracoes.backoffice.desativar_atendimento_ixc import executar_desativacao_atendimento

from .forms import BackupRestoreForm, ExcelUploadForm, SMTPTestForm
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
CADASTRO_CLIENTE_IXC_INTEGRATION = "cadastro_cliente_ixc"


def _split_email_values(raw_value):
    return [
        item.strip()
        for bloco in str(raw_value or "").replace(";", ",").split(",")
        for item in [bloco.strip()]
        if item
    ]


def _validate_email_list(raw_value, field_label, required=False):
    valores = _split_email_values(raw_value)
    if required and not valores:
        raise ValueError(f"Informe ao menos um e-mail em {field_label}.")

    for valor in valores:
        _, email = parseaddr(valor)
        validate_email(email or valor)

    return valores


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


def _buscar_ultimo_cadastro_cliente_ixc():
    return (
        IntegrationAudit.objects.filter(
            integration=CADASTRO_CLIENTE_IXC_INTEGRATION,
            action="execucao_integracao",
        )
        .order_by("-criado_em")
        .first()
    )


def _ler_dataframe_upload(arquivo):
    def _normalizar_dataframe(dataframe):
        dataframe = dataframe.copy()
        dataframe.columns = [
            re.sub(r"\s*\*\s*$", "", str(coluna).replace("\ufeff", "").strip())
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


def _render_importacao(request, form):
    importacao_em_andamento = buscar_importacao_em_andamento()
    ultima_importacao = buscar_ultima_importacao()

    return render(
        request,
        "core_admin/automacoes.html",
        {
            "form": form,
            "importacao_em_andamento": _serializar_importacao(importacao_em_andamento),
            "ultima_importacao": _serializar_importacao(ultima_importacao),
            "ultima_desativacao": _serializar_auditoria_planilha(_buscar_ultima_desativacao()),
            "ultimo_cadastro_cliente_ixc": _serializar_auditoria_planilha(_buscar_ultimo_cadastro_cliente_ixc()),
            "import_status_running": IMPORT_STATUS_RUNNING,
            "import_status_success": IMPORT_STATUS_SUCCESS,
            "import_status_error": IMPORT_STATUS_ERROR,
            "import_status_stopped": IMPORT_STATUS_STOPPED,
        },
    )


@user_passes_test(grupo_Administrador_required)
@login_required
def import_prospects(request):
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if request.POST.get("action") == "stop":
            importacao_em_andamento = buscar_importacao_em_andamento()
            if not importacao_em_andamento:
                messages.warning(request, "Nao existe importacao em andamento para interromper.")
                return redirect("import_prospects")

            solicitar_interrupcao_importacao(importacao_em_andamento)
            messages.success(
                request,
                "Solicitacao de interrupcao enviada. Aguarde alguns segundos para a importacao ser finalizada.",
            )
            return redirect("import_prospects")

        importacao_em_andamento = buscar_importacao_em_andamento()
        if importacao_em_andamento:
            messages.warning(
                request,
                f"Ja existe uma importacao em andamento para o arquivo {importacao_em_andamento.arquivo_nome or 'selecionado'}. Aguarde a conclusao antes de iniciar outra.",
            )
            return redirect("import_prospects")

        if form.is_valid():
            arquivo = form.cleaned_data["file"]
            audit = None
            try:
                caminho_salvo = salvar_arquivo_importacao(arquivo, settings.MEDIA_ROOT)
                audit = criar_auditoria_importacao(
                    usuario_id=request.user.id if request.user.is_authenticated else None,
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

                messages.success(
                    request,
                    "Importacao iniciada em segundo plano. Esta tela agora mostra o andamento e bloqueia nova execucao paralela.",
                )
                return redirect("import_prospects")
            except Exception as exc:
                if audit:
                    detalhes = dict(audit.detalhes_json or {})
                    detalhes["status_execucao"] = IMPORT_STATUS_ERROR
                    detalhes["mensagem"] = f"Nao foi possivel iniciar o processo em segundo plano: {exc}"
                    audit.detalhes_json = detalhes
                    audit.total_erros = 1
                    audit.save(update_fields=["detalhes_json", "total_erros"])
                messages.error(request, f"Nao foi possivel iniciar a importacao: {exc}")

    return _render_importacao(request, form)


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
                raise ValueError(f"Arquivo invÃ¡lido dentro do ZIP: {member.filename}")
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


@user_passes_test(grupo_Administrador_required)
@login_required
def restore_backup(request):
    backup_choices = _listar_backups_disponiveis()
    nome_arquivo_restore = ""
    origem_restore = ""

    if request.method == "GET" and request.GET.get("restore_error") == "1":
        detalhe = (request.GET.get("restore_error_detail") or "").strip()
        messages.error(
            request,
            "Falha ao receber o arquivo enviado. "
            + (f"Detalhe: {detalhe}" if detalhe else "Verifique o ZIP e tente novamente."),
        )

    try:
        form = BackupRestoreForm(request.POST or None, request.FILES or None, backup_choices=backup_choices)
    except (
        RequestDataTooBig,
        MultiPartParserError,
        SuspiciousOperation,
        MultiValueDictKeyError,
        UnreadablePostError,
        TooManyFieldsSent,
        TooManyFilesSent,
    ) as exc:
        logger.exception("Falha ao ler o upload do backup.")
        messages.error(
            request,
            f"Falha ao receber o arquivo enviado. Verifique o ZIP e tente novamente. Detalhe: {exc}",
        )
        form = BackupRestoreForm(backup_choices=backup_choices)
        return render(
            request,
            "core_admin/restore_backup_form.html",
            {"form": form, "backups_disponiveis": backup_choices},
            status=200,
        )

    if request.method == "POST" and form.is_valid():
        temp_dir = tempfile.mkdtemp(prefix="speed_restore_")

        try:
            backup_selecionado = form.cleaned_data.get("backup_existente")
            backup_zip = form.cleaned_data.get("file")

            if backup_selecionado:
                temp_zip = _resolver_backup_existente(backup_selecionado)
                nome_arquivo_restore = temp_zip.name
                origem_restore = "servidor"
            else:
                if not backup_zip or not backup_zip.name.lower().endswith(".zip"):
                    messages.error(request, "Envie um arquivo .zip valido.")
                    return render(
                        request,
                        "core_admin/restore_backup_form.html",
                        {"form": form, "backups_disponiveis": backup_choices},
                    )

                temp_zip = Path(temp_dir) / backup_zip.name
                nome_arquivo_restore = backup_zip.name
                origem_restore = "upload"
                with open(temp_zip, "wb") as handler:
                    for chunk in backup_zip.chunks():
                        handler.write(chunk)

            extract_dir = Path(temp_dir) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)
            _extract_zip_safely(temp_zip, extract_dir)

            sql_file = _find_first_file(extract_dir, ".sql")
            media_dir = _find_media_dir(extract_dir)

            if sql_file is None:
                messages.error(request, "O ZIP nao contem um arquivo .sql de backup.")
                return render(
                    request,
                    "core_admin/restore_backup_form.html",
                    {"form": form, "backups_disponiveis": backup_choices},
                )

            if sql_file.stat().st_size == 0:
                messages.error(request, "O ZIP contem um arquivo .sql vazio. Este backup nao pode ser restaurado com seguranca.")
                return render(
                    request,
                    "core_admin/restore_backup_form.html",
                    {"form": form, "backups_disponiveis": backup_choices},
                )

            # A sessao atual pode desaparecer durante o restore do banco.
            # Encerrar antes evita o Bad Request do Django ao finalizar a resposta.
            request.session.flush()

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

            detalhe_midia = " e a pasta media foi sincronizada" if media_restaurado else ""
            _registrar_auditoria_restore(
                request=request,
                arquivo_nome=nome_arquivo_restore or temp_zip.name,
                origem=origem_restore or "upload",
                sucesso=True,
                media_restaurada=media_restaurado,
                detalhes=f"Restore concluido com sucesso. Banco restaurado{detalhe_midia}.",
            )
            return HttpResponse(
                (
                    "<html><head><meta charset='utf-8'><title>Restore concluido</title></head>"
                    "<body style=\"font-family: Arial, sans-serif; padding: 32px; background: #f8f9fa; color: #111827;\">"
                    "<div style=\"max-width: 720px; margin: 0 auto; background: white; border-radius: 24px; padding: 32px; border: 1px solid #e5e7eb;\">"
                    "<h1 style=\"margin: 0 0 16px; font-size: 28px;\">Backup restaurado com sucesso</h1>"
                    f"<p style=\"margin: 0 0 12px; font-size: 15px;\">O banco de dados foi restaurado{detalhe_midia}.</p>"
                    "<p style=\"margin: 0 0 20px; font-size: 14px; color: #4b5563;\">Por seguranca, entre novamente no sistema para continuar usando a aplicacao.</p>"
                    "<a href=\"/login/\" style=\"display: inline-block; padding: 12px 18px; border-radius: 14px; background: #111827; color: #fbbf24; text-decoration: none; font-weight: 700;\">Ir para o login</a>"
                    "</div></body></html>"
                )
            )
        except Exception as exc:
            _registrar_auditoria_restore(
                request=request,
                arquivo_nome=nome_arquivo_restore or getattr(locals().get("temp_zip", None), "name", "") or "",
                origem=origem_restore or "upload",
                sucesso=False,
                media_restaurada=False,
                detalhes=str(exc),
            )
            messages.error(request, f"Falha ao restaurar backup: {exc}")
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    if request.method == "POST" and not form.is_valid():
        messages.error(request, "Revise os campos do restore e tente novamente.")

    return render(
        request,
        "core_admin/restore_backup_form.html",
        {"form": form, "backups_disponiveis": backup_choices},
    )


def download_template(request):
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

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=modelo_importacao_leads.xlsx"
    return response


@user_passes_test(grupo_Administrador_required)
@login_required
def download_template_desativacao_atendimento(request):
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
        usuario=request.user,
        arquivo_nome="Modelo_Desativacao_Atendimentos_IXC.xlsx",
        detalhes={"colunas": colunas},
    )

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Desativacao_Atendimentos_IXC.xlsx"
    return response


@user_passes_test(grupo_Administrador_required)
@login_required
def download_template_cadastro_cliente_ixc(request):
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
        "Confirmar_Cadastro",
    }
    instrucoes_campos = [
        {
            "Campo": "Razao_Social",
            "Descricao": "Nome ou razao social que sera cadastrado no cliente do IXC.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Ex.: CLIENTE TESTE LTDA",
        },
        {
            "Campo": "CNPJ_CPF",
            "Descricao": "Documento principal do cliente. O sistema usa para evitar duplicidade.",
            "Tipo de dado": "Texto numerico",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Aceita CPF ou CNPJ, com ou sem mascara. Ex.: 12345678000199",
        },
        {
            "Campo": "Nome_Fantasia",
            "Descricao": "Nome fantasia do cliente no IXC.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Ex.: CLIENTE TESTE",
        },
        {
            "Campo": "Tipo_Pessoa",
            "Descricao": "Tipo de pessoa do cadastro.",
            "Tipo de dado": "Texto curto",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Use F/PF para fisica ou J/PJ para juridica. Se vazio, a automacao infere pelo documento antes de enviar.",
        },
        {
            "Campo": "IE_RG",
            "Descricao": "Inscricao estadual ou RG do cliente.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Pode informar ISENTO quando aplicavel.",
        },
        {
            "Campo": "Contribuinte_ICMS",
            "Descricao": "Indica se o cliente e contribuinte de ICMS.",
            "Tipo de dado": "Texto curto",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Use N para nao contribuinte, S para contribuinte ou I para isento. Se vazio, a automacao infere o valor antes de enviar.",
        },
        {
            "Campo": "Tipo_Cliente_Fiscal",
            "Descricao": "Tipo de cliente fiscal do IXC, enviado pela API como iss_classificacao_padrao.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Ex.: 01 Comercial, 03 Residencial/Pessoa Fisica, 99 Outros nao especificados anteriormente. Se vazio, a automacao envia 99.",
        },
        {
            "Campo": "Tipo_Localidade",
            "Descricao": "Tipo de localidade do endereco do cliente.",
            "Tipo de dado": "Texto curto",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Valor homologado no teste: U. Se vazio, a automacao envia U.",
        },
        {
            "Campo": "CEP",
            "Descricao": "CEP do endereco principal do cliente.",
            "Tipo de dado": "Texto numerico",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Aceita com ou sem mascara. Ex.: 60000-000",
        },
        {
            "Campo": "Endereco",
            "Descricao": "Logradouro do endereco principal.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Ex.: RUA EXEMPLO",
        },
        {
            "Campo": "Numero",
            "Descricao": "Numero do endereco principal.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Use somente numeros ou SN para sem numero. Se vazio, a automacao envia SN.",
        },
        {
            "Campo": "Bairro",
            "Descricao": "Bairro do endereco principal.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Ex.: CENTRO",
        },
        {
            "Campo": "Cidade_ID_IXC",
            "Descricao": "ID numerico da cidade cadastrada no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Use apenas o ID numerico da cidade no IXC. Ex.: 887",
        },
        {
            "Campo": "Complemento",
            "Descricao": "Complemento do endereco principal.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Ex.: SALA 02",
        },
        {
            "Campo": "Referencia",
            "Descricao": "Referencia adicional do endereco.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Ex.: PROXIMO AO SUPERMERCADO",
        },
        {
            "Campo": "Contato_Nome",
            "Descricao": "Nome do contato principal do cliente.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Ex.: JOAO SILVA",
        },
        {
            "Campo": "Email",
            "Descricao": "E-mail principal do cliente.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Ex.: contato@cliente.com.br",
        },
        {
            "Campo": "Telefone",
            "Descricao": "Telefone principal do cliente.",
            "Tipo de dado": "Texto numerico",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Aceita com ou sem mascara. Ex.: 85999999999",
        },
        {
            "Campo": "Tipo_Cliente_ID",
            "Descricao": "ID do tipo de cliente ja cadastrado no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Use apenas o ID numerico do IXC.",
        },
        {
            "Campo": "Tipo_Assinante_ID",
            "Descricao": "ID do tipo de assinante no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Legenda comum: 1 Comercial/Industrial, 2 Poder Publico, 3 Residencial/Pessoa Fisica, 4 Publico, 5 Semi-Publico, 6 Outros. Se vazio, a automacao envia 3.",
        },
        {
            "Campo": "Filial_ID",
            "Descricao": "ID da filial do IXC associada ao cliente.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Use apenas o ID numerico do IXC.",
        },
        {
            "Campo": "Vendedor_ID",
            "Descricao": "ID do vendedor/responsavel no IXC.",
            "Tipo de dado": "Numero inteiro",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Use apenas o ID numerico do IXC.",
        },
        {
            "Campo": "Observacao",
            "Descricao": "Observacao administrativa enviada para o cadastro do cliente.",
            "Tipo de dado": "Texto",
            "Obrigatorio?": "Nao",
            "Regras / Exemplo": "Campo livre para observacoes internas.",
        },
        {
            "Campo": "Ativo",
            "Descricao": "Define se o cliente sera criado como ativo ou inativo.",
            "Tipo de dado": "Texto curto",
            "Obrigatorio?": "Nao na planilha / Sim no IXC",
            "Regras / Exemplo": "Aceita S ou N. Se vazio, a automacao assume S antes de enviar.",
        },
        {
            "Campo": "Confirmar_Cadastro",
            "Descricao": "Confirmacao explicita para autorizar o cadastro em massa.",
            "Tipo de dado": "Texto curto",
            "Obrigatorio?": "Sim",
            "Regras / Exemplo": "Digite exatamente SIM.",
        },
    ]
    instrucoes = pd.DataFrame(
        instrucoes_campos
    )

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
            largura = 22
            if value in {"Razao_Social", "Nome_Fantasia", "Endereco", "Observacao"}:
                largura = 36
            if value in {"Complemento", "Referencia", "Contato_Nome", "Email"}:
                largura = 28
            formato = integer_format if value in {"Cidade_ID_IXC", "Tipo_Cliente_ID", "Tipo_Assinante_ID", "Filial_ID", "Vendedor_ID", "Tipo_Cliente_Fiscal"} else None
            worksheet.set_column(col_num, col_num, largura, formato)

        larguras_ajuda = [24, 40, 18, 16, 55]
        for col_num, largura in enumerate(larguras_ajuda):
            worksheet_ajuda.set_column(col_num, col_num, largura)

        worksheet.data_validation(
            1,
            23,
            5000,
            23,
            {
                "validate": "list",
                "source": ["S", "N"],
                "ignore_blank": True,
                "input_title": "Ativo",
                "input_message": "Deixe S para ativo ou N para inativo.",
            },
        )
        worksheet.data_validation(
            1,
            24,
            5000,
            24,
            {
                "validate": "list",
                "source": ["SIM"],
                "ignore_blank": False,
                "input_title": "Confirmacao obrigatoria",
                "input_message": "Digite SIM para autorizar o cadastro do cliente.",
                "error_title": "Confirmacao obrigatoria",
                "error_message": "Para cadastrar, o campo Confirmar_Cadastro deve conter SIM.",
            },
        )

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


@user_passes_test(grupo_Administrador_required)
@login_required
def desativar_atendimentos_ixc(request):
    if request.method != "POST":
        return redirect("import_prospects")

    arquivo = request.FILES.get("arquivo_desativacao_atendimento")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar a desativacao dos atendimentos.")
        return redirect("import_prospects")

    try:
        df = _ler_dataframe_upload(arquivo)
        itens_importados = dataframe_to_records(df)
        registrar_auditoria_integracao(
            integration=DESATIVACAO_ATENDIMENTO_INTEGRATION,
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
            if pd.notna(linha.get("Atendimento_ID")):
                status, mensagem, atendimento_id = executar_desativacao_atendimento(
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
            df.to_excel(writer, index=False, sheet_name="Resultado_Desativacao_IXC")
            worksheet = writer.sheets["Resultado_Desativacao_IXC"]
            for col_num, _ in enumerate(df.columns.values):
                worksheet.set_column(col_num, col_num, 24 if df.columns[col_num] != "Mensagem_Importacao" else 90)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Desativacao_Atendimentos_IXC.xlsx"
        return response
    except Exception as exc:
        messages.error(request, f"Falha ao processar a desativacao dos atendimentos: {exc}")
        return redirect("import_prospects")


@user_passes_test(grupo_Administrador_required)
@login_required
def cadastrar_clientes_ixc(request):
    if request.method != "POST":
        return redirect("import_prospects")

    arquivo = request.FILES.get("arquivo_cadastro_cliente_ixc")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar o cadastro de clientes no IXC.")
        return redirect("import_prospects")

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

        df["Status_Importacao"] = ""
        df["Mensagem_Importacao"] = ""
        df["ID_IXC"] = ""

        sucessos = 0
        falhas = 0
        itens_execucao = []

        for index, linha in df.iterrows():
            if pd.notna(linha.get("Razao_Social")) or pd.notna(linha.get("RAZAO_SOCIAL")):
                status, mensagem, cliente_ixc_id = executar_cadastro_cliente_ixc(linha)

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
                        "dados_json": _serializar_linha_para_auditoria(df, index),
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
        return redirect("import_prospects")


@user_passes_test(grupo_Administrador_required)
@login_required
def smtp_test(request):
    configuracao_email = ConfiguracaoEmailEnvio.objects.order_by("id").first()
    remetente_padrao = (
        configuracao_email.email_remetente_padrao
        if configuracao_email and configuracao_email.email_remetente_padrao
        else settings.DEFAULT_FROM_EMAIL
    )

    initial = {
        "from_email": remetente_padrao or "",
        "subject": "Teste SMTP - Gerenciador Parceiros",
        "body": (
            "Ola,\n\n"
            "Este e um teste de envio SMTP disparado pela area administrativa do sistema.\n\n"
            "Se voce recebeu esta mensagem, a configuracao atual do backend conseguiu enviar o e-mail com sucesso.\n"
            "Neste teste, o sistema autentica com o usuario SMTP configurado no ambiente e envia usando o endereco informado no campo De.\n"
        ),
    }
    form = SMTPTestForm(request.POST or None, initial=initial)
    resultado_envio = None

    if request.method == "POST" and form.is_valid():
        try:
            if not settings.EMAIL_HOST:
                raise ValueError("O EMAIL_HOST nao esta configurado no ambiente.")

            remetente = form.cleaned_data.get("from_email") or remetente_padrao or settings.DEFAULT_FROM_EMAIL
            remetente_validado = _validate_email_list(remetente, "Remetente", required=True)[0]
            destinatarios = _validate_email_list(form.cleaned_data["to_email"], "Destinatario", required=True)
            copia = _validate_email_list(form.cleaned_data.get("cc_email"), "Cc", required=False)

            email = EmailMessage(
                subject=form.cleaned_data["subject"],
                body=form.cleaned_data["body"],
                from_email=remetente_validado,
                to=destinatarios,
                cc=copia,
                reply_to=[remetente_validado],
                connection=get_connection(fail_silently=False),
            )

            quantidade = email.send(fail_silently=False)
            resultado_envio = {
                "ok": True,
                "message": f"Teste concluido com sucesso. Backend reportou {quantidade} envio(s).",
                "from_email": remetente_validado,
                "to_email": ", ".join(destinatarios),
                "cc_email": ", ".join(copia) if copia else "--",
            }
            messages.success(request, resultado_envio["message"])
        except Exception as exc:
            resultado_envio = {
                "ok": False,
                "message": f"Falha no teste SMTP: {exc}",
                "from_email": form.cleaned_data.get("from_email") or remetente_padrao or "--",
                "to_email": form.cleaned_data.get("to_email") or "--",
                "cc_email": form.cleaned_data.get("cc_email") or "--",
            }
            messages.error(request, resultado_envio["message"])

    contexto_config = {
        "email_backend": settings.EMAIL_BACKEND,
        "email_host": settings.EMAIL_HOST or "--",
        "email_port": settings.EMAIL_PORT,
        "email_host_user": settings.EMAIL_HOST_USER or "--",
        "email_use_tls": settings.EMAIL_USE_TLS,
        "email_use_ssl": settings.EMAIL_USE_SSL,
        "default_from_email": settings.DEFAULT_FROM_EMAIL or "--",
        "remetente_padrao_admin": remetente_padrao or "--",
        "send_as_mode": "Sim" if (settings.EMAIL_HOST_USER or "").strip().lower() != (remetente_padrao or settings.DEFAULT_FROM_EMAIL or "").strip().lower() else "Nao",
    }

    return render(
        request,
        "core_admin/smtp_test_form.html",
        {
            "form": form,
            "smtp_config": contexto_config,
            "resultado_envio": resultado_envio,
        },
    )
