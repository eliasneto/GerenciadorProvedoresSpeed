import os
import re
import sys
from datetime import timedelta, timezone as dt_timezone
from urllib.parse import quote

import requests


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402


django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.dateparse import parse_datetime  # noqa: E402

from clientes.sync_utils import (  # noqa: E402
    descrever_rotina_em_execucao,
    iniciar_historico_com_trava,
)
from core.models import (  # noqa: E402
    EmailCotacaoRespostaImportacao,
    EmailCotacaoRespostaSync,
    RegistroHistorico,
)
from core_admin.models import ConfiguracaoEmailEnvio  # noqa: E402
from partners.models import Proposal  # noqa: E402


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
QUOTE_CODE_PATTERNS = [
    re.compile(r"#(\d{6,20})"),
    re.compile(r"cotac[aã]o\s*#?\s*(\d{6,20})", re.IGNORECASE),
]


class GraphEmailReplySyncError(Exception):
    pass


def _graph_enabled():
    return bool(
        settings.GRAPH_EMAIL_REPLIES_ENABLED
        and settings.GRAPH_EMAIL_REPLIES_CLIENT_ID
        and settings.GRAPH_EMAIL_REPLIES_CLIENT_SECRET
        and settings.GRAPH_EMAIL_REPLIES_TENANT_ID
    )


def _resolve_mailbox():
    mailbox = (settings.GRAPH_EMAIL_REPLIES_MAILBOX or "").strip().lower()
    if mailbox:
        return mailbox

    config = ConfiguracaoEmailEnvio.obter_configuracao()
    mailbox = (config.email_remetente_padrao or "").strip().lower()
    if mailbox:
        return mailbox

    mailbox = (settings.DEFAULT_FROM_EMAIL or "").strip().lower()
    if mailbox:
        return mailbox

    raise GraphEmailReplySyncError(
        "Nao foi possivel determinar a caixa de e-mail monitorada para respostas da cotacao."
    )


def _token_url():
    tenant_id = settings.GRAPH_EMAIL_REPLIES_TENANT_ID.strip()
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _obter_access_token():
    response = requests.post(
        _token_url(),
        data={
            "client_id": settings.GRAPH_EMAIL_REPLIES_CLIENT_ID,
            "client_secret": settings.GRAPH_EMAIL_REPLIES_CLIENT_SECRET,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=settings.GRAPH_EMAIL_REPLIES_TIMEOUT,
    )

    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text}

    if response.status_code >= 400 or "access_token" not in payload:
        raise GraphEmailReplySyncError(
            f"Falha ao autenticar no Microsoft Graph: {payload.get('error_description') or payload.get('error') or payload}"
        )

    return payload["access_token"]


def _graph_request(url, token, params=None, accept="application/json"):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=settings.GRAPH_EMAIL_REPLIES_TIMEOUT,
    )

    if response.status_code >= 400:
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        raise GraphEmailReplySyncError(f"Falha na leitura do Microsoft Graph: {payload}")

    return response


def _build_initial_params():
    received_since = timezone.now() - timedelta(days=settings.GRAPH_EMAIL_REPLIES_INITIAL_LOOKBACK_DAYS)
    received_since_utc = received_since.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "changeType": "created",
        "$select": "id,subject,from,receivedDateTime,internetMessageId,bodyPreview,hasAttachments",
        "$filter": f"receivedDateTime ge {received_since_utc}",
        "$top": "50",
    }


def _extract_quote_codes(subject):
    if not subject:
        return []

    encontrados = []
    for pattern in QUOTE_CODE_PATTERNS:
        for match in pattern.findall(subject):
            codigo = str(match).strip()
            if codigo and codigo not in encontrados:
                encontrados.append(codigo)
    return encontrados


def _find_proposals_by_subject(subject):
    codigos = _extract_quote_codes(subject)
    if not codigos:
        return None, None

    proposals = list(Proposal.objects.filter(codigo_proposta__in=codigos).order_by("id"))
    proposals_by_code = {}
    for proposal in proposals:
        if proposal.codigo_proposta:
            proposals_by_code.setdefault(proposal.codigo_proposta, []).append(proposal)

    for codigo in codigos:
        proposal_list = proposals_by_code.get(codigo)
        if proposal_list:
            return proposal_list, codigo

    return None, None


def _parse_received_datetime(value):
    recebido_em = parse_datetime(value) if value else None
    if not recebido_em:
        return None
    if timezone.is_naive(recebido_em):
        recebido_em = timezone.make_aware(recebido_em, dt_timezone.utc)

    recebido_em = timezone.localtime(recebido_em)
    if not settings.USE_TZ and timezone.is_aware(recebido_em):
        return timezone.make_naive(recebido_em)
    return recebido_em


def _build_historico_summary(proposal, message_data, remetente, recebido_em):
    subject = (message_data.get("subject") or "").strip() or "--"

    linhas = [
        "Resposta de e-mail recebida automaticamente pela caixa da cotacao.",
        "",
        f"ID da proposta: #{proposal.codigo_exibicao}",
        f"De: {remetente or '--'}",
        f"Assunto: {subject}",
        f"Recebido em: {recebido_em.strftime('%d/%m/%Y %H:%M') if recebido_em else '--'}",
        f"Possui anexos no e-mail: {'Sim' if message_data.get('hasAttachments') else 'Nao'}",
    ]

    return "\n".join(linhas)


def _fetch_mime_content(mailbox, graph_message_id, token):
    url = f"{GRAPH_BASE_URL}/users/{quote(mailbox, safe='')}/messages/{quote(graph_message_id, safe='')}/$value"
    response = _graph_request(url, token, accept="message/rfc822")
    return response.content


def _import_message(mailbox, token, message_data):
    graph_message_id = (message_data.get("id") or "").strip()
    if not graph_message_id:
        return "ignored_no_id", None

    if EmailCotacaoRespostaImportacao.objects.filter(graph_message_id=graph_message_id).exists():
        return "ignored_duplicate", None

    subject = (message_data.get("subject") or "").strip()
    proposal_list, codigo = _find_proposals_by_subject(subject)
    if not proposal_list:
        return "ignored_no_quote", None

    remetente = (
        (((message_data.get("from") or {}).get("emailAddress") or {}).get("address") or "").strip().lower()
    )
    if remetente and remetente == mailbox:
        return "ignored_same_mailbox", proposal_list[0]

    mime_content = _fetch_mime_content(mailbox, graph_message_id, token)
    recebido_em = _parse_received_datetime(message_data.get("receivedDateTime"))

    nome_arquivo = (
        f"cotacao_{codigo}_resposta_email_"
        f"{(recebido_em or timezone.now()).strftime('%Y%m%d_%H%M%S')}.eml"
    )
    historico_referencia = None
    proposal_content_type = ContentType.objects.get_for_model(Proposal)

    for proposal in proposal_list:
        historico = RegistroHistorico(
            tipo="sistema",
            acao=_build_historico_summary(proposal, message_data, remetente, recebido_em),
            usuario=None,
            content_type=proposal_content_type,
            object_id=proposal.id,
        )
        historico.arquivo.save(nome_arquivo, ContentFile(mime_content), save=False)
        historico.save()
        if historico_referencia is None:
            historico_referencia = historico

    EmailCotacaoRespostaImportacao.objects.create(
        proposal=proposal_list[0],
        historico=historico_referencia,
        graph_message_id=graph_message_id,
        internet_message_id=(message_data.get("internetMessageId") or "").strip() or None,
        assunto=subject or "(sem assunto)",
        remetente=remetente or None,
        recebido_em=recebido_em,
    )

    return "imported", proposal_list[0]


def sincronizar_respostas_email_cotacao():
    if not _graph_enabled():
        return {
            "enabled": False,
            "mailbox": None,
            "processed": 0,
            "imported": 0,
            "ignored_duplicate": 0,
            "ignored_no_quote": 0,
            "ignored_no_id": 0,
            "ignored_same_mailbox": 0,
            "delta_updated": False,
        }

    mailbox = _resolve_mailbox()
    token = _obter_access_token()
    state = EmailCotacaoRespostaSync.obter_configuracao(mailbox)

    url = state.inbox_delta_link or f"{GRAPH_BASE_URL}/users/{quote(mailbox, safe='')}/mailFolders/inbox/messages/delta"
    params = None if state.inbox_delta_link else _build_initial_params()

    processed = 0
    imported = 0
    ignored_duplicate = 0
    ignored_no_quote = 0
    ignored_no_id = 0
    ignored_same_mailbox = 0
    final_delta_link = None
    pages = 0

    while url:
        pages += 1
        if pages > settings.GRAPH_EMAIL_REPLIES_MAX_PAGES_PER_RUN:
            raise GraphEmailReplySyncError(
                "A sincronizacao de respostas por e-mail excedeu o limite de paginas desta execucao."
            )

        response = _graph_request(url, token, params=params)
        data = response.json()
        params = None

        for item in data.get("value", []):
            if "@removed" in item:
                continue

            resultado, _proposal = _import_message(mailbox, token, item)
            processed += 1
            if resultado == "imported":
                imported += 1
            elif resultado == "ignored_duplicate":
                ignored_duplicate += 1
            elif resultado == "ignored_no_quote":
                ignored_no_quote += 1
            elif resultado == "ignored_no_id":
                ignored_no_id += 1
            elif resultado == "ignored_same_mailbox":
                ignored_same_mailbox += 1

        next_link = data.get("@odata.nextLink")
        final_delta_link = data.get("@odata.deltaLink") or final_delta_link
        url = next_link

    if final_delta_link:
        state.inbox_delta_link = final_delta_link
    state.ultima_sincronizacao_em = timezone.now()
    state.ultimo_erro = ""
    state.save()

    return {
        "enabled": True,
        "mailbox": mailbox,
        "processed": processed,
        "imported": imported,
        "ignored_duplicate": ignored_duplicate,
        "ignored_no_quote": ignored_no_quote,
        "ignored_no_id": ignored_no_id,
        "ignored_same_mailbox": ignored_same_mailbox,
        "delta_updated": bool(final_delta_link),
    }


def main():
    if not _graph_enabled():
        print("Sincronizacao de respostas de e-mail desabilitada. Defina as credenciais do Graph para ativar.")
        return

    historico, rotina_ativa = iniciar_historico_com_trava("email_respostas_cotacao", origem="automatica")
    if rotina_ativa:
        print(descrever_rotina_em_execucao("email_respostas_cotacao", rotina_ativa))
        return

    try:
        resultado = sincronizar_respostas_email_cotacao()
        detalhes = (
            f"Caixa monitorada: {resultado['mailbox'] or '--'}\n"
            f"Mensagens avaliadas: {resultado['processed']}\n"
            f"Importadas no historico: {resultado['imported']}\n"
            f"Duplicadas ignoradas: {resultado['ignored_duplicate']}\n"
            f"Sem cotacao correspondente: {resultado['ignored_no_quote']}\n"
            f"Sem ID de mensagem: {resultado['ignored_no_id']}\n"
            f"Da propria caixa monitorada: {resultado['ignored_same_mailbox']}\n"
            f"Cursor delta atualizado: {'Sim' if resultado['delta_updated'] else 'Nao'}"
        )
        historico.status = "sucesso"
        historico.registros_processados = resultado["imported"]
        historico.detalhes = detalhes
        historico.data_fim = timezone.now()
        historico.save(update_fields=["status", "registros_processados", "detalhes", "data_fim"])
        print(detalhes)
    except Exception as exc:
        mailbox = None
        try:
            mailbox = _resolve_mailbox()
            state = EmailCotacaoRespostaSync.obter_configuracao(mailbox)
            state.ultimo_erro = str(exc)
            state.save(update_fields=["ultimo_erro", "atualizado_em"])
        except Exception:
            pass

        historico.status = "erro"
        historico.detalhes = f"Caixa monitorada: {mailbox or '--'}\nErro: {exc}"
        historico.data_fim = timezone.now()
        historico.save(update_fields=["status", "detalhes", "data_fim"])
        print(f"Erro ao sincronizar respostas de e-mail da cotacao: {exc}")
        return


if __name__ == "__main__":
    main()
