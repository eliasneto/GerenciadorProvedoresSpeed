import csv
import logging
import os
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import (
    PermissionDenied,
    RequestDataTooBig,
    SuspiciousOperation,
    TooManyFieldsSent,
    TooManyFilesSent,
    ValidationError,
)
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse, UnreadablePostError
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.datastructures import MultiValueDictKeyError

from apps.core.models import AutomacaoMenu
from apps.core.views import grupo_Administrador_required
from apps.core.automacoes_registry import (
    GRUPO_POR_MENU,
    permissao_automacao,
    redirect_kwargs_pagina_automacao,
    usuario_pode_acessar_automacao,
)
from apps.core_admin.models import ConfiguracaoEmailEnvio
from apps.escolas.models import Campo, Processo, Setor, SetorEscopo, SetorStatus

from . import services
from .forms import (
    BackupRestoreForm,
    CampoForm,
    ExcelUploadForm,
    ProcessoForm,
    SetorEscopoForm,
    SetorForm,
    SetorStatusForm,
    SMTPTestForm,
)


logger = logging.getLogger(__name__)


def _redirect_pagina_automacao(slug):
    url_name, kwargs = redirect_kwargs_pagina_automacao(slug)
    return redirect(url_name, **kwargs)


def _render_importacao(request, form):
    return render(
        request,
        "core_admin/automacoes.html",
        services.montar_contexto_automacoes(form, AutomacaoMenu.MENU_ADMINISTRADOR),
    )


@user_passes_test(permissao_automacao("import_prospects"))
@login_required
def import_prospects(request):
    form = ExcelUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST":
        if request.POST.get("action") == "stop":
            sucesso, mensagem = services.parar_importacao_em_andamento()
            (messages.success if sucesso else messages.warning)(request, mensagem)
            return redirect("import_prospects")

        mensagem_bloqueio = services.verificar_importacao_bloqueada()
        if mensagem_bloqueio:
            messages.warning(request, mensagem_bloqueio)
            return redirect("import_prospects")

        if form.is_valid():
            sucesso, mensagem = services.iniciar_importacao_prospects(form.cleaned_data["file"], request.user)
            if sucesso:
                messages.success(request, mensagem)
                return redirect("import_prospects")
            messages.error(request, mensagem)

    return _render_importacao(request, form)


@login_required
def automacoes_area(request, menu):
    # Administrador e Backoffice ja tem pagina propria (import_prospects e
    # backoffice:cotacao_import); esta rota generica atende apenas os menus
    # que ainda nao tem uma pagina de automacoes dedicada.
    menus_validos = {AutomacaoMenu.MENU_LASTMILE, AutomacaoMenu.MENU_PARCEIRO}
    if menu not in menus_validos:
        raise Http404("Menu de automacoes invalido.")

    grupo_exigido = GRUPO_POR_MENU.get(menu)
    if not request.user.is_superuser and not request.user.groups.filter(name=grupo_exigido).exists():
        raise PermissionDenied

    form = ExcelUploadForm()
    return render(
        request,
        "core_admin/automacoes_area.html",
        services.montar_contexto_automacoes(form, menu),
    )


@user_passes_test(grupo_Administrador_required)
@login_required
def restore_backup(request):
    backup_choices = services._listar_backups_disponiveis()
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
                temp_zip = services._resolver_backup_existente(backup_selecionado)
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
            services._extract_zip_safely(temp_zip, extract_dir)

            sql_file = services._find_first_file(extract_dir, ".sql")
            media_dir = services._find_media_dir(extract_dir)

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

            media_restaurado = services.restaurar_banco_e_midia(sql_file, media_dir)

            detalhe_midia = " e a pasta media foi sincronizada" if media_restaurado else ""
            services._registrar_auditoria_restore(
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
            services._registrar_auditoria_restore(
                request=request,
                arquivo_nome=nome_arquivo_restore or getattr(locals().get("temp_zip", None), "name", "") or "",
                origem=origem_restore or "upload",
                sucesso=False,
                media_restaurada=False,
                detalhes=str(exc),
            )
            logger.exception("Falha ao restaurar backup.")
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


@user_passes_test(grupo_Administrador_required)
@login_required
def importacao_exportacao(request):
    return render(request, "core_admin/importacao_exportacao.html", {})


def _resposta_csv_setores_escolas(sufixo_arquivo, incluir_linhas):
    """RN-048/RN-049/RN-050: monta a resposta CSV de Setores e Escolas —
    colunas fixas + Campos personalizados atuais — com ou sem as linhas de
    dado (`incluir_linhas=False` gera so o modelo, sem consultar Escola/
    CampoValor, ja que o gerador de linhas so executa quando iterado)."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    referencia = timezone.localdate() if settings.USE_TZ else date.today()
    nome_arquivo = f"{sufixo_arquivo}_{referencia:%Y-%m-%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    response.write("﻿")

    colunas, linhas = services.montar_exportacao_setores_escolas()
    writer = csv.DictWriter(response, fieldnames=colunas)
    writer.writeheader()
    if incluir_linhas:
        for linha in linhas:
            writer.writerow(linha)
    return response


@user_passes_test(grupo_Administrador_required)
@login_required
def exportar_setores_escolas(request):
    """RN-048/RN-049/PO-071: CSV unico, uma linha por Escola, replicando as
    colunas ja exibidas na tela de Setor (Escola + Setor/Parceiro/Status
    de Rede Externa, Rede Interna e Mapa Calor), mais uma coluna por Campo
    personalizado aplicavel (descoberta a cada exportacao)."""
    return _resposta_csv_setores_escolas("exportacao_setores_escolas", incluir_linhas=True)


@user_passes_test(grupo_Administrador_required)
@login_required
def exportar_setores_escolas_modelo(request):
    """RN-050/PO-071: mesmo CSV da exportacao de dados, so com a linha de
    cabecalho (colunas fixas + Campos personalizados atuais) — sem
    nenhuma linha de Escola."""
    return _resposta_csv_setores_escolas("modelo_setores_escolas", incluir_linhas=False)


def download_template(request):
    response = HttpResponse(
        services.montar_template_leads_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=modelo_importacao_leads.xlsx"
    return response


@user_passes_test(permissao_automacao("desativar_atendimentos_ixc"))
@login_required
def download_template_desativacao_atendimento(request):
    response = HttpResponse(
        services.montar_template_desativacao_atendimento_bytes(request.user),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Desativacao_Atendimentos_IXC.xlsx"
    return response


@user_passes_test(permissao_automacao("editar_logins_ixc"))
@login_required
def download_template_edicao_login_ixc(request):
    response = HttpResponse(
        services.montar_template_edicao_login_ixc_bytes(request.user),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Edicao_Logins_IXC.xlsx"
    return response


@user_passes_test(permissao_automacao("editar_atendimentos_ixc"))
@login_required
def download_template_edicao_atendimento_ixc(request):
    response = HttpResponse(
        services.montar_template_edicao_atendimento_ixc_bytes(request.user),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Edicao_Atendimentos_IXC.xlsx"
    return response


@user_passes_test(permissao_automacao("resolver_os_atendimento_ixc"))
@login_required
def download_template_resolucao_os_atendimento(request):
    response = HttpResponse(
        services.montar_template_resolucao_os_atendimento_bytes(request.user),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = "attachment; filename=Modelo_Resolucao_OS_Atendimentos_IXC.xlsx"
    return response


@user_passes_test(permissao_automacao("desativar_atendimentos_ixc"))
@login_required
def desativar_atendimentos_ixc(request):
    if request.method != "POST":
        return _redirect_pagina_automacao("desativar_atendimentos_ixc")

    arquivo = request.FILES.get("arquivo_desativacao_atendimento")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar a desativacao dos atendimentos.")
        return _redirect_pagina_automacao("desativar_atendimentos_ixc")

    try:
        conteudo = services.processar_desativacao_atendimentos(arquivo, request.user)
        response = HttpResponse(
            conteudo,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Desativacao_Atendimentos_IXC.xlsx"
        return response
    except Exception as exc:
        logger.exception("Falha ao processar a desativacao dos atendimentos.")
        messages.error(request, f"Falha ao processar a desativacao dos atendimentos: {exc}")
        return _redirect_pagina_automacao("desativar_atendimentos_ixc")


@user_passes_test(permissao_automacao("editar_atendimentos_ixc"))
@login_required
def editar_atendimentos_ixc(request):
    if request.method != "POST":
        return _redirect_pagina_automacao("editar_atendimentos_ixc")

    arquivo = request.FILES.get("arquivo_edicao_atendimento_ixc")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar a edicao dos atendimentos no IXC.")
        return _redirect_pagina_automacao("editar_atendimentos_ixc")

    try:
        conteudo = services.processar_edicao_atendimentos_ixc(arquivo, request.user)
        response = HttpResponse(
            conteudo,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Edicao_Atendimentos_IXC.xlsx"
        return response
    except Exception as exc:
        logger.exception("Falha ao processar a edicao dos atendimentos.")
        messages.error(request, f"Falha ao processar a edicao dos atendimentos: {exc}")
        return _redirect_pagina_automacao("editar_atendimentos_ixc")


@user_passes_test(permissao_automacao("resolver_os_atendimento_ixc"))
@login_required
def resolver_os_atendimento_ixc(request):
    if request.method != "POST":
        return _redirect_pagina_automacao("resolver_os_atendimento_ixc")

    planilha = request.FILES.get("arquivo_planilha_resolucao_os")
    zip_upload = request.FILES.get("arquivo_zip_resolucao_os")
    if not planilha:
        messages.error(
            request,
            "Selecione uma planilha com os atendimentos para processar a resolucao das O.S.",
        )
        return _redirect_pagina_automacao("resolver_os_atendimento_ixc")

    zip_arquivos = None
    if zip_upload:
        try:
            zip_arquivos = zipfile.ZipFile(zip_upload)
        except zipfile.BadZipFile:
            messages.error(
                request,
                "O arquivo enviado como ZIP de anexos nao e um arquivo ZIP valido.",
            )
            return _redirect_pagina_automacao("resolver_os_atendimento_ixc")

    execucao_id = (request.POST.get("execucao_id") or "").strip()[:64] or None

    try:
        conteudo = services.processar_resolucao_os_atendimentos(
            planilha, zip_arquivos, request.user, execucao_id=execucao_id
        )
        response = HttpResponse(
            conteudo,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Resolucao_OS_Atendimentos_IXC.xlsx"
        return response
    except Exception as exc:
        logger.exception("Falha ao processar a resolucao das O.S. dos atendimentos.")
        messages.error(request, f"Falha ao processar a resolucao das O.S. dos atendimentos: {exc}")
        return _redirect_pagina_automacao("resolver_os_atendimento_ixc")


@user_passes_test(permissao_automacao("resolver_os_atendimento_ixc"))
@login_required
def progresso_resolucao_os_atendimento(request):
    execucao_id = (request.GET.get("execucao_id") or "").strip()[:64]
    progresso = services.obter_progresso_resolucao_os_atendimento(execucao_id)
    return JsonResponse(progresso)


@user_passes_test(permissao_automacao("editar_logins_ixc"))
@login_required
def editar_logins_ixc(request):
    if request.method != "POST":
        return _redirect_pagina_automacao("editar_logins_ixc")

    arquivo = request.FILES.get("arquivo_edicao_login_ixc")
    if not arquivo:
        messages.error(request, "Selecione uma planilha para processar a edicao de logins no IXC.")
        return _redirect_pagina_automacao("editar_logins_ixc")

    try:
        conteudo = services.processar_edicao_logins_ixc(arquivo, request.user)
        response = HttpResponse(
            conteudo,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = "attachment; filename=Relatorio_Edicao_Logins_IXC.xlsx"
        return response
    except Exception as exc:
        logger.exception("Falha ao processar a edicao dos logins.")
        messages.error(request, f"Falha ao processar a edicao dos logins: {exc}")
        return _redirect_pagina_automacao("editar_logins_ixc")


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
            remetente_validado = services.validar_lista_emails(remetente, "Remetente", required=True)[0]
            destinatarios = services.validar_lista_emails(form.cleaned_data["to_email"], "Destinatario", required=True)
            copia = services.validar_lista_emails(form.cleaned_data.get("cc_email"), "Cc", required=False)

            quantidade = services.enviar_email_teste(
                remetente=remetente_validado,
                destinatarios=destinatarios,
                copia=copia,
                subject=form.cleaned_data["subject"],
                body=form.cleaned_data["body"],
            )
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
            logger.exception("Falha no teste de envio SMTP.")
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


def testar_api_ixc(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "erro": "Sessao expirada. Recarregue a pagina."}, status=401)
    if not usuario_pode_acessar_automacao(request.user, "testar_api_ixc"):
        return JsonResponse({"ok": False, "erro": "Permissao insuficiente."}, status=403)
    if request.method != "POST":
        return JsonResponse({"ok": False, "erro": "Metodo nao permitido."}, status=405)

    try:
        return JsonResponse(services.consultar_status_ixc())
    except Exception as exc:
        logger.exception("Falha ao testar a API do IXC.")
        return JsonResponse({"ok": False, "erro": str(exc)})


@user_passes_test(grupo_Administrador_required)
@login_required
def processos_list(request):
    """PO-050/ADR-014: catalogo de Processos (Setor/Status) vinculavel a
    RedeExterna/RedeInterna/MapaCalor (RN-043). Nesta versao, so listar e
    criar."""
    form = ProcessoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        processo = form.save()
        messages.success(request, f"Processo '{processo.nome}' criado com sucesso.")
        return redirect('processo_detail', pk=processo.pk)

    processos = Processo.objects.annotate(total_setores=Count('setores')).order_by('nome')

    return render(request, "core_admin/processos_list.html", {
        "form": form,
        "processos": processos,
    })


@user_passes_test(grupo_Administrador_required)
@login_required
def processo_detail(request, pk):
    processo = get_object_or_404(Processo, pk=pk)
    form = SetorForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        setor = form.save(commit=False)
        setor.processo = processo
        try:
            setor.full_clean()
        except ValidationError:
            messages.error(request, f"O setor '{setor.nome}' ja existe neste processo.")
            return redirect('processo_detail', pk=processo.pk)
        setor.save()
        messages.success(request, f"Setor '{setor.nome}' adicionado ao processo.")
        return redirect('processo_detail', pk=processo.pk)

    setores = processo.setores.prefetch_related('status_opcoes').order_by('nome')

    return render(request, "core_admin/processo_detail.html", {
        "processo": processo,
        "form": form,
        "setores": setores,
        "status_form": SetorStatusForm(),
    })


@user_passes_test(grupo_Administrador_required)
@login_required
def processo_setor_status_criar(request, processo_pk, setor_pk):
    processo = get_object_or_404(Processo, pk=processo_pk)
    setor = get_object_or_404(Setor, pk=setor_pk, processo=processo)

    if request.method == "POST":
        form = SetorStatusForm(request.POST)
        if form.is_valid():
            status_novo = form.save(commit=False)
            status_novo.setor = setor
            try:
                status_novo.full_clean()
            except ValidationError:
                messages.error(request, f"O status '{status_novo.nome}' ja existe neste setor.")
            else:
                status_novo.save()
                messages.success(request, f"Status '{status_novo.nome}' adicionado ao setor '{setor.nome}'.")
        else:
            messages.error(request, "Informe um nome valido para o status.")

    return redirect('processo_detail', pk=processo.pk)


@user_passes_test(grupo_Administrador_required)
@login_required
def processo_setor_status_excluir(request, processo_pk, setor_pk, status_pk):
    """PO-059/ADR-020: exclusao de Status do catalogo de Processos, por
    Setor (RN-034). Setor e Processo continuam sem exclusao. RedeExterna/
    RedeInterna/MapaCalor (RN-043) que referenciavam o Status excluido
    ficam com o campo `status` em branco (on_delete=SET_NULL, RN-026) —
    nenhum RE/RI/MC e apagado."""
    processo = get_object_or_404(Processo, pk=processo_pk)
    setor = get_object_or_404(Setor, pk=setor_pk, processo=processo)
    status = get_object_or_404(SetorStatus, pk=status_pk, setor=setor)

    if request.method == "POST":
        nome_status = status.nome
        status.delete()
        messages.success(request, f"Status '{nome_status}' excluido do setor '{setor.nome}'.")

    return redirect('processo_detail', pk=processo.pk)


@user_passes_test(grupo_Administrador_required)
@login_required
def campos_list(request):
    """PO-057/ADR-019: cadastro de Campos personalizados por Setor
    (RN-031). PO-061/ADR-021 acrescentou editar e excluir (RN-036)."""
    form = CampoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        campo = form.save()
        messages.success(request, f"Campo '{campo.nome}' criado com sucesso.")
        return redirect('campos_list')

    campos = Campo.objects.annotate(total_valores=Count('valores')).order_by('setor_nome', 'nome')

    return render(request, "core_admin/campos_list.html", {
        "form": form,
        "campos": campos,
    })


@user_passes_test(grupo_Administrador_required)
@login_required
def campo_editar(request, pk):
    """PO-061/ADR-021: edicao de um Campo (RN-036). Reaproveita o mesmo
    form da criacao (PO-057/RN-031). Troca de tipo e permitida mesmo com
    CampoValor ja gravados para o Campo, sem limpeza automatica dos
    valores existentes."""
    campo = get_object_or_404(Campo, pk=pk)
    form = CampoForm(request.POST or None, instance=campo)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Campo '{campo.nome}' atualizado com sucesso.")
        return redirect('campos_list')

    campos = Campo.objects.annotate(total_valores=Count('valores')).order_by('setor_nome', 'nome')

    return render(request, "core_admin/campos_list.html", {
        "form": form,
        "campos": campos,
        "campo_em_edicao": campo,
    })


@user_passes_test(grupo_Administrador_required)
@login_required
def campo_excluir(request, pk):
    """PO-061/ADR-021: exclusao de um Campo (RN-036), com confirmacao
    explicita no template informando quantos CampoValor serao perdidos.
    CampoValor.campo ja e on_delete=CASCADE (apps/escolas/models.py), entao
    os valores vinculados sao apagados junto, sem migracao nova.
    PO-063/RN-039/ADR-024: Campo usado como base de algum Campo tipo
    Calculado e protegido (`on_delete=PROTECT`) — a exclusao e bloqueada
    para o valor calculado nao sumir silenciosamente."""
    campo = get_object_or_404(Campo, pk=pk)

    if request.method == "POST":
        dependentes = list(campo.campos_calculados.values_list('nome', flat=True))
        if dependentes:
            messages.error(
                request,
                f"Campo '{campo.nome}' não pode ser excluído: é usado como Campo base de "
                f"{', '.join(dependentes)}. Altere ou exclua esse(s) campo(s) calculado(s) primeiro.",
            )
        else:
            nome_campo = campo.nome
            total_valores = campo.valores.count()
            campo.delete()
            if total_valores:
                messages.success(
                    request,
                    f"Campo '{nome_campo}' excluído, junto com {total_valores} valor(es) preenchido(s).",
                )
            else:
                messages.success(request, f"Campo '{nome_campo}' excluído com sucesso.")

    return redirect('campos_list')


def _setores_com_escopo():
    """PO-062/ADR-022: nomes de Setor do catalogo (RN-025) com o escopo
    atual de cada um (RN-037), ou `None` quando ainda nao configurado."""
    escopos_por_nome = {escopo.setor_nome: escopo for escopo in SetorEscopo.objects.all()}
    nomes_setor = Setor.objects.order_by('nome').values_list('nome', flat=True)
    return [
        {"nome": nome, "escopo": escopos_por_nome.get(nome)}
        for nome in dict.fromkeys(nomes_setor)
    ]


@user_passes_test(grupo_Administrador_required)
@login_required
def setor_escopo_list(request):
    """PO-062/ADR-022: tela "Setor" da Administracao — escolhe se as
    informacoes (Campos, RN-031) de cada Setor (RN-025) aparecem na
    Atividade principal (Escola) ou nas Sub-atividades (RE/RI) (RN-037)."""
    form = SetorEscopoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        escopo = form.save()
        messages.success(request, f"Escopo do Setor '{escopo.setor_nome}' salvo com sucesso.")
        return redirect('setor_escopo_list')

    return render(request, "core_admin/setor_escopo_list.html", {
        "form": form,
        "setores": _setores_com_escopo(),
    })


@user_passes_test(grupo_Administrador_required)
@login_required
def setor_escopo_editar(request, pk):
    """PO-062/ADR-022: edicao do escopo ja configurado de um Setor."""
    escopo = get_object_or_404(SetorEscopo, pk=pk)
    form = SetorEscopoForm(request.POST or None, instance=escopo)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Escopo do Setor '{escopo.setor_nome}' atualizado com sucesso.")
        return redirect('setor_escopo_list')

    return render(request, "core_admin/setor_escopo_list.html", {
        "form": form,
        "setores": _setores_com_escopo(),
        "escopo_em_edicao": escopo,
    })
