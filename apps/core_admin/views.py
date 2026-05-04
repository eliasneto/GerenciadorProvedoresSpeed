from io import BytesIO
import logging
import os
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

from core.views import grupo_Administrador_required
from core_admin.models import ConfiguracaoEmailEnvio

from .forms import BackupRestoreForm, ExcelUploadForm, SMTPTestForm
from .import_services import (
    IMPORT_STATUS_ERROR,
    IMPORT_STATUS_RUNNING,
    IMPORT_STATUS_SUCCESS,
    LEAD_IMPORT_COLUMNS,
    buscar_importacao_em_andamento,
    buscar_ultima_importacao,
    criar_auditoria_importacao,
    salvar_arquivo_importacao,
)


logger = logging.getLogger(__name__)


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


def _render_importacao(request, form):
    importacao_em_andamento = buscar_importacao_em_andamento()
    ultima_importacao = buscar_ultima_importacao()

    return render(
        request,
        "core_admin/import_form.html",
        {
            "form": form,
            "importacao_em_andamento": _serializar_importacao(importacao_em_andamento),
            "ultima_importacao": _serializar_importacao(ultima_importacao),
            "import_status_running": IMPORT_STATUS_RUNNING,
            "import_status_success": IMPORT_STATUS_SUCCESS,
            "import_status_error": IMPORT_STATUS_ERROR,
        },
    )


def import_prospects(request):
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
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

                subprocess.Popen(
                    [
                        sys.executable,
                        str(Path(settings.BASE_DIR) / "scripts" / "integracoes" / "importar_leads_planilha.py"),
                        str(audit.id),
                        str(caminho_salvo),
                    ]
                )

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


@user_passes_test(grupo_Administrador_required)
@login_required
def restore_backup(request):
    backup_choices = _listar_backups_disponiveis()

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
            else:
                if not backup_zip or not backup_zip.name.lower().endswith(".zip"):
                    messages.error(request, "Envie um arquivo .zip valido.")
                    return render(
                        request,
                        "core_admin/restore_backup_form.html",
                        {"form": form, "backups_disponiveis": backup_choices},
                    )

                temp_zip = Path(temp_dir) / backup_zip.name
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

            db_conf = settings.DATABASES["default"]
            mysql_host = db_conf.get("HOST") or "localhost"
            mysql_port = str(db_conf.get("PORT") or 3306)
            mysql_name = db_conf.get("NAME")
            mysql_user = os.getenv("DB_ADMIN_USER", "root")
            mysql_password = os.getenv("DB_ADMIN_PASSWORD", os.getenv("MYSQL_ROOT_PASSWORD", ""))

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

            messages.success(
                request,
                "Backup restaurado com sucesso. Banco de dados atualizado" + (" e midia sincronizada." if media_restaurado else "."),
            )
            return redirect("import_prospects")
        except Exception as exc:
            messages.error(request, f"Falha ao restaurar backup: {exc}")
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

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
