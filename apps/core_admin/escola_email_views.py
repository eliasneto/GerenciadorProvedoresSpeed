"""PO-066/RN-042: envio de e-mail a partir da tela da Escola (nivel
"Global", RN-023) ou de um RE/RI/Mapa Calor (RN-029/RN-043), com o log
caindo no historico do nivel correto — mesma regra de visibilidade
individual/combinada ja usada por comentario/anexo/log automatico
(RN-029).

Vive em `apps.core_admin` (camada de aplicacao) porque precisa de
`ConfiguracaoEmailEnvio` (dono: apps.core_admin) — mesmo motivo registrado
em `apps/core_admin/quotes_views.py` (PO-032): esta camada pode importar de
`apps.escolas`/`apps.leads` (dominio) e do proprio modelo, mas o inverso
quebraria a ordem de camada da ADR-007. Reaproveita os validadores de
e-mail e o limite de anexo ja definidos em `quotes_views.py` (mesma opcao
de e-mail do sistema, RN-042) e devolve os mesmos partials de modal de
historico do RE/RI/Mapa Calor/Escola (`apps.leads`, RN-029), sem duplicar
layout."""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, get_connection
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core import email_tracking
from apps.core.models import RegistroHistorico
from apps.escolas.models import Escola, MapaCalor, RedeExterna, RedeInterna
from apps.leads import services as leads_services
from apps.leads.views import grupo_LastMile_required

from .quotes_views import (
    _configured_from_email,
    _validate_email_attachments,
    _validate_email_values,
)

logger = logging.getLogger(__name__)

_MODELO_REDE_POR_TIPO = {"re": RedeExterna, "ri": RedeInterna, "mc": MapaCalor}
_ROTULO_NIVEL = {
    email_tracking.NIVEL_RE: "Rede Externa (RE)",
    email_tracking.NIVEL_RI: "Rede Interna (RI)",
    email_tracking.NIVEL_MC: "Mapa Calor (MC)",
    email_tracking.NIVEL_GLOBAL: "Escola",
}


def _alvo_historico(escola, nivel, rede):
    if nivel == email_tracking.NIVEL_GLOBAL:
        return ContentType.objects.get_for_model(Escola), escola.id
    return ContentType.objects.get_for_model(type(rede)), rede.id


def _enviar_email_nivel(request, escola, nivel, rede):
    """POST comum aos tres niveis (RE/RI/Global): valida, envia via SMTP e
    grava o `RegistroHistorico` (sucesso ou falha) no nivel certo. Devolve
    a mensagem de erro (ou `None` quando o envio deu certo)."""
    if not settings.EMAIL_HOST:
        return (
            "O SMTP ainda nao foi configurado no backend. "
            "Preencha as variaveis de e-mail no ambiente do sistema."
        )

    to_raw = (request.POST.get("to") or "").strip()
    cc_raw = (request.POST.get("cc") or "").strip()
    subject_raw = (request.POST.get("subject") or "").strip()
    body = request.POST.get("body") or ""
    rotulo_nivel = _ROTULO_NIVEL[nivel]
    content_type, object_id = _alvo_historico(escola, nivel, rede)

    try:
        remetente = _configured_from_email()
        destinatarios = _validate_email_values(to_raw, "Para", required=True)
        copia = _validate_email_values(cc_raw, "Cc", required=False)
        anexos = _validate_email_attachments(request.FILES.getlist("attachments"))
    except Exception as exc:
        return str(exc)

    codigo = email_tracking.montar_codigo_rastreio(escola.inep, nivel)
    assunto_final = email_tracking.montar_assunto_com_codigo(codigo, subject_raw)

    try:
        connection = get_connection(fail_silently=False)
        email = EmailMessage(
            subject=assunto_final,
            body=body,
            from_email=remetente,
            to=destinatarios,
            cc=copia,
            reply_to=[remetente],
            connection=connection,
        )
        for arquivo in anexos:
            email.attach(arquivo.name, arquivo.read(), arquivo.content_type or "application/octet-stream")

        quantidade_enviada = email.send(fail_silently=False)
        email_eml = email.message().as_bytes()

        historico = RegistroHistorico(
            tipo="sistema",
            acao=(
                f"E-mail enviado pela tela de {rotulo_nivel}.\n\n"
                f"Escola: {escola.nome or escola.jira_key}\n"
                f"De: {remetente}\n"
                f"Para: {', '.join(destinatarios)}\n"
                f"Cc: {', '.join(copia) if copia else '--'}\n"
                f"Assunto: {assunto_final}\n"
                f"Codigo de rastreio: {codigo}\n"
                f"Anexos no e-mail: {len(anexos)}\n"
                f"Status de envio: {'Sucesso' if quantidade_enviada else 'Sem confirmacao do backend'}"
            ),
            usuario=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        nome_arquivo = f"escola_{escola.pk}_{nivel}_email_{timezone.now().strftime('%Y%m%d_%H%M%S')}.eml"
        historico.arquivo.save(nome_arquivo, ContentFile(email_eml), save=False)
        historico.save()
        return None
    except Exception as exc:
        logger.exception(
            "Falha ao enviar e-mail (%s) da escola #%s",
            rotulo_nivel, escola.pk,
        )
        RegistroHistorico.objects.create(
            tipo="sistema",
            acao=(
                f"Falha no envio de e-mail pela tela de {rotulo_nivel}.\n\n"
                f"Escola: {escola.nome or escola.jira_key}\n"
                f"De: {remetente if 'remetente' in locals() else '--'}\n"
                f"Para: {to_raw or '--'}\n"
                f"Cc: {cc_raw or '--'}\n"
                f"Assunto informado: {subject_raw or '--'}\n"
                f"Codigo de rastreio: {codigo}\n"
                f"Erro: {exc}"
            ),
            usuario=request.user,
            content_type=content_type,
            object_id=object_id,
        )
        return f"Nao foi possivel enviar o e-mail: {exc}"


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_rede_enviar_email(request, escola_pk, tipo):
    """PO-066/RN-042/RN-043: envia e-mail a partir do RE, do RI ou do Mapa
    Calor — o envio (e a resposta correspondente, importada por
    `apps/integracoes/email/sincronizar_respostas_email_cotacao.py`) fica
    somente no historico individual daquele processo."""
    modelo = _MODELO_REDE_POR_TIPO.get(tipo)
    if modelo is None:
        raise Http404("Tipo de rede invalido.")

    escola = get_object_or_404(Escola, pk=escola_pk)
    rede = get_object_or_404(modelo, escola=escola)
    erro = None
    sucesso = None

    if request.method == "POST":
        erro = _enviar_email_nivel(request, escola, tipo, rede)
        sucesso = "E-mail enviado." if erro is None else None

    return render(request, "leads/partials/escola_rede_historico_modal.html", {
        "escola": escola,
        "tipo": tipo,
        "rede": rede,
        "historico": leads_services.historico_rede(rede),
        "erro": erro,
        "sucesso": sucesso,
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def escola_enviar_email(request, escola_pk):
    """PO-066/RN-042: envia e-mail a partir da Escola (nivel "Global") — o
    envio (e a resposta correspondente) fica no historico da Escola e e
    visivel na visao combinada de RE, RI e Mapa Calor (mesmo modal da
    RN-029, ampliada pela RN-043)."""
    escola = get_object_or_404(Escola, pk=escola_pk)
    erro = None
    sucesso = None

    if request.method == "POST":
        erro = _enviar_email_nivel(request, escola, email_tracking.NIVEL_GLOBAL, None)
        sucesso = "E-mail enviado." if erro is None else None

    return render(request, "leads/partials/escola_historico_modal.html", {
        "escola": escola,
        "historico": leads_services.historico_combinado_escola(escola),
        "erro": erro,
        "sucesso": sucesso,
    })
