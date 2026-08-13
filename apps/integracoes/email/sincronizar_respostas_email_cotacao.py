import re
import sys
from datetime import timedelta, timezone as dt_timezone
from urllib.parse import quote

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.clientes.sync_utils import (
    descrever_rotina_em_execucao,
    iniciar_historico_com_trava,
)
from apps.core import email_tracking
from apps.core.models import (
    EmailCotacaoRespostaImportacao,
    EmailCotacaoRespostaSync,
    EmailEscolaRespostaImportacao,
    RegistroHistorico,
)
from apps.core_admin.models import ConfiguracaoEmailEnvio
from apps.escolas.models import Escola, MapaCalor, RedeExterna, RedeInterna
from apps.partners.models import Proposal


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
QUOTE_CODE_PATTERNS = [
    re.compile(r"#(\d{6,20})"),
    re.compile(r"cotac[aã]o\s*#?\s*(\d{6,20})", re.IGNORECASE),
]
# PO-066/RN-042: codigos de rastreio de Escola/RE/RI/Mapa Calor (RN-043)
# usam o prefixo "ESC-" (apps.core.email_tracking) — nunca colidem com o
# codigo puramente numerico da cotacao acima, mesma caixa compartilhada
# sem confundir os dois dominios.
_MODELO_REDE_POR_NIVEL = {
    email_tracking.NIVEL_RE: RedeExterna,
    email_tracking.NIVEL_RI: RedeInterna,
    email_tracking.NIVEL_MC: MapaCalor,
}


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


def _find_escola_alvo_by_subject(subject):
    """PO-066/RN-042: localiza, a partir do primeiro codigo de rastreio de
    Escola/RE/RI reconhecido no assunto, o alvo (content_type/object_id)
    onde a resposta deve ser registrada. Devolve
    `(content_type, object_id, codigo, nivel, escola)` ou `None` quando
    nenhum codigo do assunto corresponde a uma Escola (ou a um RE/RI ainda
    nao criado) cadastrada."""
    for codigo in email_tracking.extrair_codigos_rastreio(subject):
        decomposto = email_tracking.decompor_codigo_rastreio(codigo)
        if not decomposto:
            continue
        inep, nivel = decomposto

        escola = Escola.objects.filter(inep=inep).order_by("id").first()
        if not escola:
            continue

        if nivel == email_tracking.NIVEL_GLOBAL:
            return ContentType.objects.get_for_model(Escola), escola.id, codigo, nivel, escola

        modelo = _MODELO_REDE_POR_NIVEL[nivel]
        rede = modelo.objects.filter(escola=escola).first()
        if not rede:
            continue
        return ContentType.objects.get_for_model(modelo), rede.id, codigo, nivel, escola

    return None


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


def _build_historico_summary_escola(escola, codigo, message_data, remetente, recebido_em):
    subject = (message_data.get("subject") or "").strip() or "--"

    linhas = [
        "Resposta de e-mail recebida automaticamente pela caixa compartilhada (Escola/RE/RI).",
        "",
        f"Escola: {escola.nome or escola.jira_key}",
        f"Codigo de rastreio: {codigo}",
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
    """Classifica a mensagem pelo codigo no assunto — cotacao (`#123456`)
    ou Escola/RE/RI (`#ESC-...`, PO-066/RN-042, prefixo que nunca colide
    com o codigo da cotacao) — e delega ao importador do dominio
    correspondente. Mensagem sem nenhum codigo reconhecido e ignorada."""
    graph_message_id = (message_data.get("id") or "").strip()
    if not graph_message_id:
        return "ignored_no_id", None

    subject = (message_data.get("subject") or "").strip()

    proposal_list, codigo_cotacao = _find_proposals_by_subject(subject)
    if proposal_list:
        return _import_message_cotacao(mailbox, token, message_data, graph_message_id, subject, proposal_list, codigo_cotacao)

    alvo_escola = _find_escola_alvo_by_subject(subject)
    if alvo_escola:
        return _import_message_escola(mailbox, token, message_data, graph_message_id, subject, alvo_escola)

    return "ignored_no_quote", None


def _import_message_cotacao(mailbox, token, message_data, graph_message_id, subject, proposal_list, codigo):
    if EmailCotacaoRespostaImportacao.objects.filter(graph_message_id=graph_message_id).exists():
        return "ignored_duplicate", None

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


def _import_message_escola(mailbox, token, message_data, graph_message_id, subject, alvo_escola):
    """PO-066/RN-042: contraparte de `_import_message_cotacao` para
    Escola/RE/RI — mesmo fluxo (dedup por `graph_message_id`, ignora
    mensagem da propria caixa monitorada, baixa o `.eml` e grava o
    historico), mas registrando a correlacao em `EmailEscolaRespostaImportacao`
    (nao em `EmailCotacaoRespostaImportacao`) para nao confundir os dois
    dominios na mesma caixa compartilhada."""
    content_type, object_id, codigo, nivel, escola = alvo_escola

    if EmailEscolaRespostaImportacao.objects.filter(graph_message_id=graph_message_id).exists():
        return "ignored_duplicate_escola", None

    remetente = (
        (((message_data.get("from") or {}).get("emailAddress") or {}).get("address") or "").strip().lower()
    )
    if remetente and remetente == mailbox:
        return "ignored_same_mailbox", escola

    mime_content = _fetch_mime_content(mailbox, graph_message_id, token)
    recebido_em = _parse_received_datetime(message_data.get("receivedDateTime"))

    nome_arquivo = (
        f"escola_{codigo}_resposta_email_"
        f"{(recebido_em or timezone.now()).strftime('%Y%m%d_%H%M%S')}.eml"
    )

    historico = RegistroHistorico(
        tipo="sistema",
        acao=_build_historico_summary_escola(escola, codigo, message_data, remetente, recebido_em),
        usuario=None,
        content_type=content_type,
        object_id=object_id,
    )
    historico.arquivo.save(nome_arquivo, ContentFile(mime_content), save=False)
    historico.save()

    EmailEscolaRespostaImportacao.objects.create(
        nivel=nivel,
        content_type=content_type,
        object_id=object_id,
        codigo_rastreio=codigo,
        historico=historico,
        graph_message_id=graph_message_id,
        internet_message_id=(message_data.get("internetMessageId") or "").strip() or None,
        assunto=subject or "(sem assunto)",
        remetente=remetente or None,
        recebido_em=recebido_em,
    )

    return "imported_escola", escola


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
            "imported_escola": 0,
            "ignored_duplicate_escola": 0,
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
    imported_escola = 0
    ignored_duplicate_escola = 0
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

            # PO-066/RN-042: a mesma passagem pela caixa compartilhada
            # classifica cada mensagem como cotacao ou Escola/RE/RI
            # (`_import_message`) — evita uma segunda leitura da API do
            # Graph so para o dominio novo.
            resultado, _alvo = _import_message(mailbox, token, item)
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
            elif resultado == "imported_escola":
                imported_escola += 1
            elif resultado == "ignored_duplicate_escola":
                ignored_duplicate_escola += 1

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
        "imported_escola": imported_escola,
        "ignored_duplicate_escola": ignored_duplicate_escola,
        "ignored_same_mailbox": ignored_same_mailbox,
        "delta_updated": bool(final_delta_link),
    }


def main():
    if not _graph_enabled():
        print("Sincronizacao de respostas de e-mail desabilitada. Defina as credenciais do Graph para ativar.")
        return

    eh_manual = 'manual' in sys.argv
    origem_detectada = 'manual' if eh_manual else 'automatica'

    usuario_executor = None
    if eh_manual:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = sys.argv[2] if len(sys.argv) > 2 else ""
        usuario_executor = User.objects.filter(username=username).first() or User.objects.filter(is_superuser=True).first()

    historico, rotina_ativa = iniciar_historico_com_trava(
        "email_respostas_cotacao",
        origem=origem_detectada,
        executado_por=usuario_executor,
    )
    if rotina_ativa:
        print(descrever_rotina_em_execucao("email_respostas_cotacao", rotina_ativa))
        return

    try:
        resultado = sincronizar_respostas_email_cotacao()
        detalhes = (
            f"Caixa monitorada: {resultado['mailbox'] or '--'}\n"
            f"Mensagens avaliadas: {resultado['processed']}\n"
            f"Importadas no historico (cotacao): {resultado['imported']}\n"
            f"Duplicadas ignoradas (cotacao): {resultado['ignored_duplicate']}\n"
            f"Importadas no historico (Escola/RE/RI): {resultado['imported_escola']}\n"
            f"Duplicadas ignoradas (Escola/RE/RI): {resultado['ignored_duplicate_escola']}\n"
            f"Sem cotacao nem Escola/RE/RI correspondente: {resultado['ignored_no_quote']}\n"
            f"Sem ID de mensagem: {resultado['ignored_no_id']}\n"
            f"Da propria caixa monitorada: {resultado['ignored_same_mailbox']}\n"
            f"Cursor delta atualizado: {'Sim' if resultado['delta_updated'] else 'Nao'}"
        )
        historico.status = "sucesso"
        historico.registros_processados = resultado["imported"] + resultado["imported_escola"]
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
