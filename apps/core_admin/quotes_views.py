"""Tela "Minhas Cotacoes" e envio de e-mail de cotacao.

Movido de apps.core.views na PO-032 (quebra de ciclos de importacao). Esta
funcionalidade precisa tanto de Proposal (dono: apps.partners, camada 1)
quanto de ConfiguracaoEmailEnvio (dono: apps.core_admin, camada 2), por isso
vive aqui: core_admin pode importar de partners (camada 1) e do proprio
modelo (camada 2), mas partners nao pode importar de core_admin.
"""

import logging
from email.utils import parseaddr

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage, get_connection
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from urllib.parse import urlencode

from apps.core.models import RegistroHistorico
from apps.core.views import (
    _build_sort_links,
    _csv_response,
    _report_totais_vazios,
    _resolve_sort,
    grupo_Operacao_required,
)
from apps.partners.models import Proposal
from apps.partners.services import _proposal_cliente_nome, _proposal_endereco_nome, _proposal_partner_nome

from .models import ConfiguracaoEmailEnvio

logger = logging.getLogger(__name__)

EMAIL_ATTACHMENT_TOTAL_LIMIT_BYTES = 10 * 1024 * 1024
EMAIL_ATTACHMENT_TOTAL_LIMIT_MB = EMAIL_ATTACHMENT_TOTAL_LIMIT_BYTES // (1024 * 1024)


def _split_email_values(raw_value):
    return [
        item.strip()
        for bloco in str(raw_value or '').replace(';', ',').split(',')
        for item in [bloco.strip()]
        if item
    ]


def _validate_email_values(raw_value, field_label, required=False):
    values = _split_email_values(raw_value)

    if required and not values:
        raise ValueError(f"Informe ao menos um destinatario em {field_label}.")

    for value in values:
        _, email = parseaddr(value)
        validate_email(email or value)

    return values


def _configured_from_email():
    configuracao_email = ConfiguracaoEmailEnvio.objects.order_by('id').first()
    remetente = (
        configuracao_email.email_remetente_padrao
        if configuracao_email and configuracao_email.email_remetente_padrao
        else settings.DEFAULT_FROM_EMAIL
    )
    remetente = str(remetente or '').strip()
    if not remetente:
        raise ValueError('Nao ha um remetente padrao configurado para envio.')
    validate_email(remetente)
    return remetente


def _build_quote_email_subject(codigo_exibicao, subject):
    codigo = str(codigo_exibicao or '').strip()
    assunto = str(subject or '').strip()

    if not codigo:
        return assunto

    prefixo_direto = f"#{codigo}"
    prefixo_cotacao = f"Cotacao #{codigo}"

    if assunto.startswith(prefixo_direto) or assunto.lower().startswith(prefixo_cotacao.lower()):
        return assunto

    return f"{prefixo_direto} - {assunto}" if assunto else prefixo_direto


def _validate_email_attachments(files):
    anexos = list(files or [])
    total_size = sum(int(getattr(arquivo, 'size', 0) or 0) for arquivo in anexos)

    if total_size > EMAIL_ATTACHMENT_TOTAL_LIMIT_BYTES:
        raise ValueError(
            f"O tamanho total dos anexos excede o limite permitido de {EMAIL_ATTACHMENT_TOTAL_LIMIT_MB} MB."
        )

    return anexos


@user_passes_test(grupo_Operacao_required)
@login_required
def minhas_cotacoes(request):
    page_size = 20
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'empresa', 'cotacao', 'cliente', 'endereco', 'ultimo_comentario'},
        'empresa',
    )
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    ultima_interacao_subquery = RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]

    queryset = Proposal.objects.filter(responsavel=request.user, status='analise').select_related(
        'partner',
        'cliente',
        'client_address',
        'responsavel',
    ).annotate(
        ultima_interacao=Subquery(ultima_interacao_subquery)
    )

    if busca:
        queryset = queryset.filter(
            Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
            | Q(client_address__login_ixc__icontains=busca)
        )

    order_map = {
        'empresa': ['partner__nome_fantasia', 'partner__razao_social', 'id'],
        'cotacao': ['codigo_proposta', 'nome_proposta', 'id'],
        'cliente': ['cliente__nome_fantasia', 'cliente__razao_social', 'id'],
        'endereco': ['client_address__login_ixc', 'id'],
        'ultimo_comentario': ['ultima_interacao', 'id'],
    }
    ordering = order_map[sort_by]
    if direction == 'desc':
        ordering = [f"-{field}" for field in ordering]
    queryset = queryset.order_by(*ordering)

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'minhas_cotacoes.csv',
            ['Parceiro', 'Cotação', 'Cliente', 'Endereço', 'Último comentário'],
            [
                [
                    _proposal_partner_nome(item),
                    item.codigo_exibicao,
                    _proposal_cliente_nome(item),
                    _proposal_endereco_nome(item),
                    item.ultima_interacao.strftime('%d/%m/%Y %H:%M') if item.ultima_interacao else '-',
                ]
                for item in queryset
            ],
        )

    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    email_remetente_padrao = _configured_from_email()
    total_resultados = paginator.count
    totais_por_status = _report_totais_vazios()
    totais_por_status['analise'] = total_resultados
    pagina_atual = page_obj.number
    primeira_pagina = max(1, pagina_atual - 2)
    ultima_pagina = min(paginator.num_pages, pagina_atual + 2)
    paginas_visiveis = list(range(primeira_pagina, ultima_pagina + 1))

    return render(request, 'core/minhas_cotacoes.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'endereco', 'ultimo_comentario'],
        ),
        'totais_por_status': totais_por_status,
        'total_resultados': total_resultados,
        'page_size': page_size,
        'page_start': ((pagina_atual - 1) * page_size) + 1 if total_resultados else 0,
        'page_end': min(pagina_atual * page_size, total_resultados) if total_resultados else 0,
        'paginas_visiveis': paginas_visiveis,
        'email_remetente_padrao': email_remetente_padrao,
        'email_attachment_limit_mb': EMAIL_ATTACHMENT_TOTAL_LIMIT_MB,
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
    })


@user_passes_test(grupo_Operacao_required)
@login_required
def minhas_cotacoes_enviar_email(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Metodo nao permitido.'}, status=405)

    if not settings.EMAIL_HOST:
        return JsonResponse({
            'ok': False,
            'message': 'O SMTP ainda nao foi configurado no backend. Preencha as variaveis de e-mail no ambiente do sistema.',
        }, status=400)

    proposal_pk = (request.POST.get('proposal_pk') or '').strip()
    to_raw = (request.POST.get('to') or '').strip()
    cc_raw = (request.POST.get('cc') or '').strip()
    subject = (request.POST.get('subject') or '').strip()
    body = request.POST.get('body') or ''

    if not proposal_pk.isdigit():
        return JsonResponse({'ok': False, 'message': 'Cotacao invalida para envio.'}, status=400)

    proposal = get_object_or_404(
        Proposal.objects.select_related('partner', 'cliente', 'client_address', 'responsavel'),
        pk=int(proposal_pk),
    )

    if not (
        request.user.is_superuser
        or proposal.responsavel_id == request.user.id
        or request.user.groups.filter(name__in=['Administrador', 'Gestao', 'Gestão']).exists()
    ):
        return JsonResponse({'ok': False, 'message': 'Voce nao tem permissao para enviar e-mail desta cotacao.'}, status=403)

    try:
        remetente = _configured_from_email()
        destinatarios = _validate_email_values(to_raw, 'Para', required=True)
        copia = _validate_email_values(cc_raw, 'Cc', required=False)
        anexos = _validate_email_attachments(request.FILES.getlist('attachments'))
    except Exception as exc:
        return JsonResponse({'ok': False, 'message': str(exc)}, status=400)

    subject_final = _build_quote_email_subject(proposal.codigo_exibicao, subject)

    try:
        connection = get_connection(fail_silently=False)
        email = EmailMessage(
            subject=subject_final,
            body=body,
            from_email=remetente,
            to=destinatarios,
            cc=copia,
            reply_to=[remetente],
            connection=connection,
        )

        for arquivo in anexos:
            email.attach(arquivo.name, arquivo.read(), arquivo.content_type or 'application/octet-stream')

        quantidade_enviada = email.send(fail_silently=False)
        email_eml = email.message().as_bytes()
        historico_email = RegistroHistorico(
            tipo='sistema',
            acao=(
                "E-mail enviado pela tela Minhas Cotacoes.\n\n"
                f"ID da proposta: #{proposal.codigo_exibicao}\n"
                f"De: {remetente}\n"
                f"Para: {', '.join(destinatarios)}\n"
                f"Cc: {', '.join(copia) if copia else '--'}\n"
                f"Assunto: {subject_final}\n"
                f"Anexos no e-mail: {len(anexos)}\n"
                f"Arquivo salvo no historico: sim\n"
                f"Status de envio: {'Sucesso' if quantidade_enviada else 'Sem confirmacao do backend'}"
            ),
            usuario=request.user,
            content_type=ContentType.objects.get_for_model(Proposal),
            object_id=proposal.id,
        )
        nome_arquivo_eml = f"cotacao_{proposal.codigo_exibicao}_email_{timezone.now().strftime('%Y%m%d_%H%M%S')}.eml"
        historico_email.arquivo.save(nome_arquivo_eml, ContentFile(email_eml), save=False)
        historico_email.save()

        return JsonResponse({
            'ok': True,
            'message': 'E-mail enviado com sucesso.',
            'subject': subject_final,
        })
    except Exception as exc:
        logger.exception(
            "Falha ao enviar e-mail da cotacao #%s para %s",
            proposal.codigo_exibicao,
            ", ".join(destinatarios) if 'destinatarios' in locals() else "--",
        )
        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                "Falha no envio de e-mail pela tela Minhas Cotacoes.\n\n"
                f"ID da proposta: #{proposal.codigo_exibicao}\n"
                f"De: {remetente if 'remetente' in locals() else '--'}\n"
                f"Para: {to_raw or '--'}\n"
                f"Cc: {cc_raw or '--'}\n"
                f"Assunto informado: {subject or '--'}\n"
                f"Erro: {exc}"
            ),
            usuario=request.user,
            content_type=ContentType.objects.get_for_model(Proposal),
            object_id=proposal.id,
        )
        return JsonResponse({
            'ok': False,
            'message': f'Nao foi possivel enviar o e-mail: {exc}',
        }, status=500)
