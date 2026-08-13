"""Camada de servicos do app partners.

Cobre o grupo de telas de Parceiro, o grupo de Relatorios de Gestao
(movidos de apps.core na PO-032) e, no grupo Proposta, as 3 sub-fatias:
"CRUD e navegacao", "Lote" e "Fechamento de O.S. e edicao financeira"
(risco alto — RN-017/RN-018, IXCGateway, fila da ADR-006, calculo
financeiro).

Views ficam responsaveis apenas por HTTP: parametros da requisicao,
mensagens e renderizacao (PO-011, ADR-005).
"""
from html import unescape

from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import strip_tags

from apps.clientes.models import Endereco
from apps.core.models import CotacaoStatusAuditoria, RegistroHistorico
# Utilitarios genericos de status/ordenacao, reaproveitados do app core
# (camada 0) — mesmo padrao ja usado em views.py.
from apps.core.views import (
    _report_status_key,
    _report_status_display,
    _report_totais_vazios,
    _sortable_value,
)
from scripts.integracoes.ixc_finalizacao_service import finalizar_os_existente, resumir_erro_finalizacao
from scripts.integracoes.ixc_ticket_arquivo_service import anexar_arquivo_atendimento_por_os

from .models import Partner, Proposal, ProposalMotivoInviavel

STATUS_PARTNER_CONVERTIDO = ['aguardando_contratacao', 'contratado', 'declinado']
STATUS_PARTNER_VALIDOS_TRANSICAO = ['ativo', 'aguardando_contratacao', 'contratado', 'declinado', 'inativo']


def listar_partners_convertidos():
    return (
        Partner.objects.filter(proposals__status__in=STATUS_PARTNER_CONVERTIDO)
        .distinct()
        .order_by('-id')
    )


def agrupar_propostas_convertidas_por_parceiro(partner_ids):
    """Retorna {partner_id: [Proposal, ...]}, com no maximo uma proposta por
    codigo_proposta (evita repetir o mesmo lote de logins vinculados)."""
    propostas_convertidas = (
        Proposal.objects.filter(partner_id__in=partner_ids, status__in=STATUS_PARTNER_CONVERTIDO)
        .order_by('-id')
    )

    propostas_por_parceiro = {}
    propostas_vistas = set()
    for proposta in propostas_convertidas:
        chave = (proposta.partner_id, proposta.codigo_proposta or f"proposal-{proposta.pk}")
        if chave in propostas_vistas:
            continue
        propostas_vistas.add(chave)
        propostas_por_parceiro.setdefault(proposta.partner_id, []).append(proposta)

    return propostas_por_parceiro


def listar_partners_inativos():
    return Partner.objects.exclude(
        status__in=['ativo', 'aguardando_contratacao', 'contratado']
    ).order_by('-data_cadastro')


def agrupar_propostas_do_partner(partner):
    """Retorna (proposals, proposal_groups): as propostas em aberto do
    parceiro e essas mesmas propostas agrupadas por cliente e depois por lote
    (codigo_proposta), para exibicao aninhada na tela de detalhe."""
    proposals = partner.proposals.exclude(
        status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']
    ).order_by('-id')

    proposal_groups = []
    grouped_map = {}

    for proposal in proposals:
        cliente_obj = proposal.cliente
        group_key = cliente_obj.pk if cliente_obj else f"sem-cliente-{proposal.pk}"

        if group_key not in grouped_map:
            grouped_map[group_key] = {
                'key': group_key,
                'cliente': cliente_obj,
                'cliente_nome': str(cliente_obj) if cliente_obj else 'Sem cliente vinculado',
                'proposal_batches': [],
                'proposal_batches_map': {},
                'total_logins': 0,
            }
            proposal_groups.append(grouped_map[group_key])

        batch_key = proposal.codigo_proposta or f"proposal-{proposal.pk}"
        group = grouped_map[group_key]

        if batch_key not in group['proposal_batches_map']:
            group['proposal_batches_map'][batch_key] = {
                'key': batch_key,
                'proposal': proposal,
                'codigo_exibicao': proposal.codigo_exibicao,
                'nome_proposta': proposal.nome_proposta or 'Proposta sem nome',
                'logins': [],
            }
            group['proposal_batches'].append(group['proposal_batches_map'][batch_key])

        group['proposal_batches_map'][batch_key]['logins'].append(proposal)
        group['total_logins'] += 1

    for group in proposal_groups:
        group.pop('proposal_batches_map', None)

    return proposals, proposal_groups


def listar_historico_partner(partner, incluir_arquivados=False):
    partner_type = ContentType.objects.get_for_model(Partner)
    queryset = RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id)
    if not incluir_arquivados:
        queryset = queryset.filter(arquivado=False)
    return queryset.order_by('-id')


def contar_historico_arquivado_partner(partner):
    partner_type = ContentType.objects.get_for_model(Partner)
    return RegistroHistorico.objects.filter(
        content_type=partner_type, object_id=partner.id, arquivado=True,
    ).count()


def listar_planos_partner(partner):
    return partner.planos.all().order_by('-data_cadastro', '-id')


def listar_clientes_do_partner(partner):
    """Retorna (proposals, clientes_agrupados): as propostas em aberto do
    parceiro e o mapa cliente -> lista de enderecos distintos vinculados."""
    proposals = Proposal.objects.filter(partner=partner).exclude(
        status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']
    ).select_related('cliente', 'client_address')

    clientes_agrupados = {}
    for prop in proposals:
        cliente = prop.cliente
        enderecos = clientes_agrupados.setdefault(cliente, [])
        if prop.client_address not in enderecos:
            enderecos.append(prop.client_address)

    return proposals, clientes_agrupados


def aplicar_transicao_status_partner(partner, novo_status, usuario, observacao='', arquivo=None):
    """Aplica a transicao de status do parceiro na esteira de Ativos e
    registra o historico correspondente.

    Retorna (estado, mensagem), com estado em:
    - 'bloqueado': transicao invalida a partir de aguardando_contratacao;
    - 'aplicado': status valido, aplicado (registra historico so quando o
      status de fato mudou, mas a mensagem de sucesso sempre e devolvida);
    - 'ignorado': novo_status fora da lista de status validos.
    """
    if partner.status == 'aguardando_contratacao' and novo_status not in ['contratado', 'declinado']:
        return 'bloqueado', (
            "Parceiros em aguardando contratação só podem avançar para Contratado ou Declinado."
        )

    if novo_status not in STATUS_PARTNER_VALIDOS_TRANSICAO:
        return 'ignorado', ''

    status_antigo = partner.status
    partner.status = novo_status
    partner.save()

    if status_antigo != novo_status:
        if novo_status == 'inativo':
            tipo_hist = 'anexo' if arquivo else 'sistema'
            texto_historico = (
                f"PARCEIRO INATIVADO\n\nMotivo / Observação:\n{observacao}" if observacao
                else "PARCEIRO INATIVADO"
            )
        elif novo_status == 'declinado':
            tipo_hist = 'anexo' if arquivo else 'sistema'
            texto_historico = (
                f"PARCEIRO DECLINADO\n\nMotivo / Observação:\n{observacao}" if observacao
                else "PARCEIRO DECLINADO"
            )
        elif novo_status == 'contratado':
            tipo_hist = 'sistema'
            texto_historico = "PARCEIRO CONTRATADO\n\nStatus operacional alterado para [CONTRATADO]."
        elif novo_status == 'aguardando_contratacao':
            tipo_hist = 'sistema'
            texto_historico = (
                "PARCEIRO EM AGUARDANDO CONTRATAÇÃO\n\n"
                "A proposta viável foi encaminhada para negociação contratual."
            )
        else:
            tipo_hist = 'sistema'
            texto_historico = "PARCEIRO REATIVADO\n\nStatus operacional alterado para [ATIVO]."

        RegistroHistorico.objects.create(
            tipo=tipo_hist,
            acao=texto_historico,
            arquivo=arquivo,
            usuario=usuario,
            content_type=ContentType.objects.get_for_model(Partner),
            object_id=partner.id,
        )

    nome_partner = partner.nome_fantasia or partner.razao_social
    return 'aplicado', f"O status da {nome_partner} foi atualizado para {novo_status.upper()}."


def aplicar_reativacao_winback(partner, novo_status, usuario, observacao=''):
    """Avanca o estagio do parceiro na esteira de reativacao (win-back).

    Retorna (estado, mensagem), com estado em:
    - 'reativado': parceiro reativado (`andamento`) — historico antigo
      arquivado e TODAS as propostas do parceiro apagadas, para o novo ciclo;
    - 'atualizado': estagio de negociacao/inviavel registrado;
    - 'ignorado': novo_status fora dos valores tratados.
    """
    partner_type = ContentType.objects.get_for_model(Partner)

    if novo_status == 'andamento':
        for historico_antigo in RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id):
            historico_antigo.arquivado = True
            historico_antigo.save()

        for proposta in partner.proposals.all():
            proposta.delete()

        partner.status = 'ativo'
        partner.save()

        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                "NOVO CICLO DE PARCERIA!\nO parceiro foi reativado na esteira win-back. "
                "O histórico antigo foi arquivado e o perfil foi limpo para a inclusão de novas OS."
            ),
            usuario=usuario,
            content_type=partner_type,
            object_id=partner.id,
            arquivado=False,
        )
        nome_partner = partner.nome_fantasia or partner.razao_social
        return 'reativado', f"Show! {nome_partner} reativado e histórico arquivado com sucesso!"

    if novo_status in ('negociacao', 'inviavel'):
        partner.status = novo_status
        partner.save()

        texto = (
            "Negociação de reativação iniciada." if novo_status == 'negociacao'
            else f"Tentativa de reativação recusada/inviável.\nMotivo: {observacao}"
        )
        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=texto,
            usuario=usuario,
            content_type=partner_type,
            object_id=partner.id,
            arquivado=False,
        )
        return 'atualizado', f"Estágio atualizado para: {partner.get_status_display()}"

    return 'ignorado', ''


# ==============================================================================
# RELATORIOS DE GESTAO (movidos de apps.core.views na PO-032 - liam ao dono do
# dado: Proposal e do app partners, nao de core)
# ==============================================================================

def _ultima_interacao_subquery():
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    return RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]


def _proposal_cliente_nome(proposal):
    try:
        cliente = getattr(proposal, 'cliente', None)
    except Exception:
        cliente = None

    if cliente is None:
        return '--'

    try:
        return cliente.nome_fantasia or cliente.razao_social or '--'
    except Exception:
        return str(cliente or '--')


def _proposal_partner_nome(proposal):
    try:
        partner = getattr(proposal, 'partner', None)
    except Exception:
        partner = None

    if partner is None:
        return '--'

    try:
        return partner.nome_fantasia or partner.razao_social or '--'
    except Exception:
        return str(partner or '--')


def _proposal_endereco_nome(proposal):
    try:
        client_address = getattr(proposal, 'client_address', None)
    except Exception:
        client_address = None

    if client_address is None:
        return '--'

    try:
        return client_address.login_ixc or '--'
    except Exception:
        return '--'


def _proposal_endereco_complemento(proposal):
    try:
        client_address = getattr(proposal, 'client_address', None)
    except Exception:
        client_address = None

    if client_address is None:
        return '--'

    try:
        return str(client_address)
    except Exception:
        return '--'


def _proposal_responsavel_nome(proposal):
    try:
        responsavel = getattr(proposal, 'responsavel', None)
    except Exception:
        responsavel = None

    if responsavel is None:
        return '-'

    try:
        return responsavel.get_full_name() or responsavel.username or '-'
    except Exception:
        return '-'


def _proposal_status_display(proposal):
    try:
        return proposal.get_status_display()
    except Exception:
        return proposal.status or '--'


def montar_relatorio_login_status(busca='', status='', cliente='', endereco='', sort_by='empresa', direction='asc'):
    """Retorna (rows, totais_por_status, status_filtrado) para o relatorio
    Status por Endereco (uma linha por login/proposta)."""
    queryset = Proposal.objects.select_related(
        'partner', 'cliente', 'client_address', 'responsavel',
    ).annotate(ultima_interacao=Subquery(_ultima_interacao_subquery()))

    if busca:
        queryset = queryset.filter(
            Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
        )

    if cliente:
        queryset = queryset.filter(
            Q(cliente__nome_fantasia__icontains=cliente)
            | Q(cliente__razao_social__icontains=cliente)
        )

    if endereco:
        queryset = queryset.filter(
            Q(client_address__login_ixc__icontains=endereco)
            | Q(client_address__logradouro__icontains=endereco)
        )

    status_filtrado = _report_status_key(status)
    if status_filtrado == 'analise':
        queryset = queryset.filter(status__in=['analise', 'ativa'])
    elif status_filtrado:
        queryset = queryset.filter(status=status_filtrado)

    order_map = {
        'empresa': ['partner__nome_fantasia', 'partner__razao_social', 'id'],
        'cotacao': ['codigo_proposta', 'nome_proposta', 'id'],
        'cliente': ['cliente__nome_fantasia', 'cliente__razao_social', 'id'],
        'login': ['client_address__login_ixc', 'id'],
        'status': ['status', 'id'],
        'responsavel': ['responsavel__username', 'id'],
        'ultima_interacao': ['ultima_interacao', 'id'],
    }
    ordering = order_map[sort_by]
    if direction == 'desc':
        ordering = [f"-{field}" for field in ordering]
    queryset = queryset.order_by(*ordering)

    totais_por_status = _report_totais_vazios()
    totais_por_status['analise'] = queryset.filter(status__in=['analise', 'ativa']).count()
    totais_por_status['aguardando_contratacao'] = queryset.filter(status='aguardando_contratacao').count()
    totais_por_status['contratado'] = queryset.filter(status='contratado').count()
    totais_por_status['declinado'] = queryset.filter(status='declinado').count()
    totais_por_status['encerrada'] = queryset.filter(status='encerrada').count()

    rows = []
    for item in queryset:
        rows.append({
            'pk': item.pk,
            'partner_nome': _proposal_partner_nome(item),
            'codigo_exibicao': item.codigo_exibicao,
            'nome_proposta': item.nome_proposta or 'Cotação sem nome',
            'cliente_nome': _proposal_cliente_nome(item),
            'login_nome': _proposal_endereco_nome(item),
            'status': _report_status_key(item.status),
            'status_display': _report_status_display(item),
            'responsavel_nome': _proposal_responsavel_nome(item),
            'ultima_interacao': item.ultima_interacao,
        })

    return rows, totais_por_status, status_filtrado


def montar_relatorio_proposta_status(busca='', status='', sort_by='empresa', direction='asc'):
    """Retorna (proposals_rows, totais_por_status, status_filtrado) para o
    relatorio Status por Cotacao (uma linha por lote/codigo_proposta)."""
    queryset = Proposal.objects.select_related(
        'partner', 'cliente', 'client_address', 'responsavel',
    ).annotate(ultima_interacao=Subquery(_ultima_interacao_subquery())).order_by('-id')

    if busca:
        queryset = queryset.filter(
            Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
        )

    status_filtrado = _report_status_key(status)
    if status_filtrado == 'analise':
        queryset = queryset.filter(status__in=['analise', 'ativa'])
    elif status_filtrado:
        queryset = queryset.filter(status=status_filtrado)

    proposals_rows = []
    grouped_rows = {}
    totais_por_status = _report_totais_vazios()

    for item in queryset:
        group_key = (
            item.partner_id or 0,
            item.cliente_id or 0,
            item.codigo_proposta or f"proposal-{item.pk}",
        )
        if group_key not in grouped_rows:
            grouped_rows[group_key] = {
                'proposal': item,
                'proposal_pk': item.pk,
                'codigo_exibicao': item.codigo_exibicao,
                'nome_proposta': item.nome_proposta or 'Cotação sem nome',
                'partner_nome': _proposal_partner_nome(item),
                'cliente_nome': _proposal_cliente_nome(item),
                'status': _report_status_key(item.status),
                'status_display': _report_status_display(item),
                'responsavel_nome': _proposal_responsavel_nome(item),
                'total_logins': 0,
                'ultima_interacao': item.ultima_interacao,
            }
            proposals_rows.append(grouped_rows[group_key])
            status_key = _report_status_key(item.status)
            if status_key in totais_por_status:
                totais_por_status[status_key] += 1

        grouped_rows[group_key]['total_logins'] += 1

        if item.ultima_interacao and (
            not grouped_rows[group_key]['ultima_interacao']
            or item.ultima_interacao > grouped_rows[group_key]['ultima_interacao']
        ):
            grouped_rows[group_key]['ultima_interacao'] = item.ultima_interacao

    proposals_rows = sorted(
        proposals_rows,
        key=lambda item: _sortable_value({
            'empresa': item['partner_nome'],
            'cotacao': item['codigo_exibicao'],
            'cliente': item['cliente_nome'],
            'qtd_logins': item['total_logins'],
            'status': item['status_display'],
        }[sort_by]),
        reverse=(direction == 'desc'),
    )

    return proposals_rows, totais_por_status, status_filtrado


def montar_relatorio_status_cliente(busca='', sort_by='cliente', direction='asc'):
    """Retorna (rows, totais_por_status) para o relatorio Cotacao por
    Cliente (uma linha por cliente, com contagem de cotacoes por status)."""
    queryset = Proposal.objects.select_related(
        'cliente', 'partner', 'client_address',
    ).order_by('cliente__nome_fantasia', 'cliente__razao_social', 'codigo_proposta', 'id')

    if busca:
        queryset = queryset.filter(
            Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(client_address__login_ixc__icontains=busca)
        )

    totais_por_status = _report_totais_vazios()
    totais_por_status['analise'] = queryset.filter(status__in=['analise', 'ativa']).count()
    totais_por_status['aguardando_contratacao'] = queryset.filter(status='aguardando_contratacao').count()
    totais_por_status['contratado'] = queryset.filter(status='contratado').count()
    totais_por_status['declinado'] = queryset.filter(status='declinado').count()
    totais_por_status['encerrada'] = queryset.filter(status='encerrada').count()

    grouped_rows = {}
    rows = []

    for item in queryset:
        if item.cliente_id:
            cliente_key = f"cliente-{item.cliente_id}"
            cliente_nome = _proposal_cliente_nome(item)
        else:
            cliente_nome = _proposal_cliente_nome(item)
            cliente_key = f"sem-cliente-{cliente_nome}-{item.partner_id}"

        if cliente_key not in grouped_rows:
            grouped_rows[cliente_key] = {
                'cliente_nome': cliente_nome,
                'em_negociacao': 0,
                'aguardando_contratacao': 0,
                'contratado': 0,
                'declinado': 0,
                'inviavel': 0,
                'total_cotacoes': 0,
                '_cotacoes_total': set(),
                '_cotacoes_em_negociacao': set(),
                '_cotacoes_aguardando_contratacao': set(),
                '_cotacoes_contratado': set(),
                '_cotacoes_declinado': set(),
                '_cotacoes_inviavel': set(),
            }
            rows.append(grouped_rows[cliente_key])

        row = grouped_rows[cliente_key]
        cotacao_key = item.codigo_proposta or f"proposal-{item.pk}"

        if cotacao_key not in row['_cotacoes_total']:
            row['_cotacoes_total'].add(cotacao_key)
            row['total_cotacoes'] += 1

        if item.status in {'analise', 'ativa'}:
            if cotacao_key not in row['_cotacoes_em_negociacao']:
                row['_cotacoes_em_negociacao'].add(cotacao_key)
                row['em_negociacao'] += 1
        elif item.status == 'aguardando_contratacao':
            if cotacao_key not in row['_cotacoes_aguardando_contratacao']:
                row['_cotacoes_aguardando_contratacao'].add(cotacao_key)
                row['aguardando_contratacao'] += 1
        elif item.status == 'contratado':
            if cotacao_key not in row['_cotacoes_contratado']:
                row['_cotacoes_contratado'].add(cotacao_key)
                row['contratado'] += 1
        elif item.status == 'declinado':
            if cotacao_key not in row['_cotacoes_declinado']:
                row['_cotacoes_declinado'].add(cotacao_key)
                row['declinado'] += 1
        elif item.status == 'encerrada':
            if cotacao_key not in row['_cotacoes_inviavel']:
                row['_cotacoes_inviavel'].add(cotacao_key)
                row['inviavel'] += 1

    for row in rows:
        row.pop('_cotacoes_total', None)
        row.pop('_cotacoes_em_negociacao', None)
        row.pop('_cotacoes_aguardando_contratacao', None)
        row.pop('_cotacoes_contratado', None)
        row.pop('_cotacoes_declinado', None)
        row.pop('_cotacoes_inviavel', None)

    rows = sorted(
        rows,
        key=lambda item: _sortable_value({
            'cliente': item['cliente_nome'],
            'total_cotacoes': item['total_cotacoes'],
            'em_negociacao': item['em_negociacao'],
            'aguardando_contratacao': item['aguardando_contratacao'],
            'contratado': item['contratado'],
            'declinado': item['declinado'],
            'inviavel': item['inviavel'],
        }[sort_by]),
        reverse=(direction == 'desc'),
    )

    return rows, totais_por_status


def montar_relatorio_cotacao_endereco(busca='', sort_by='endereco', direction='asc'):
    """Retorna (rows, totais_por_status) para o relatorio Cotacao por
    Endereco (uma linha por endereco, com contagem de cotacoes por status)."""
    queryset = Proposal.objects.select_related(
        'cliente', 'partner', 'client_address',
    ).order_by('client_address__login_ixc', 'codigo_proposta', 'id')

    if busca:
        queryset = queryset.filter(
            Q(client_address__login_ixc__icontains=busca)
            | Q(client_address__logradouro__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
        )

    totais_por_status = _report_totais_vazios()
    totais_por_status['analise'] = queryset.filter(status__in=['analise', 'ativa']).count()
    totais_por_status['aguardando_contratacao'] = queryset.filter(status='aguardando_contratacao').count()
    totais_por_status['contratado'] = queryset.filter(status='contratado').count()
    totais_por_status['declinado'] = queryset.filter(status='declinado').count()
    totais_por_status['encerrada'] = queryset.filter(status='encerrada').count()

    grouped_rows = {}
    rows = []

    for item in queryset:
        endereco_nome = _proposal_endereco_nome(item)
        endereco_complemento = _proposal_endereco_complemento(item)
        endereco_key = item.client_address_id or f"sem-endereco-{item.pk}"
        cotacao_key = item.codigo_proposta or f"proposal-{item.pk}"

        if endereco_key not in grouped_rows:
            grouped_rows[endereco_key] = {
                'endereco_nome': endereco_nome,
                'endereco_complemento': endereco_complemento,
                'cliente_nome': _proposal_cliente_nome(item),
                'total_cotacoes': 0,
                'em_negociacao': 0,
                'aguardando_contratacao': 0,
                'contratado': 0,
                'declinado': 0,
                'inviavel': 0,
                '_cotacoes_total': set(),
                '_cotacoes_em_negociacao': set(),
                '_cotacoes_aguardando_contratacao': set(),
                '_cotacoes_contratado': set(),
                '_cotacoes_declinado': set(),
                '_cotacoes_inviavel': set(),
            }
            rows.append(grouped_rows[endereco_key])

        row = grouped_rows[endereco_key]

        if cotacao_key not in row['_cotacoes_total']:
            row['_cotacoes_total'].add(cotacao_key)
            row['total_cotacoes'] += 1

        if item.status in {'analise', 'ativa'}:
            if cotacao_key not in row['_cotacoes_em_negociacao']:
                row['_cotacoes_em_negociacao'].add(cotacao_key)
                row['em_negociacao'] += 1
        elif item.status == 'aguardando_contratacao':
            if cotacao_key not in row['_cotacoes_aguardando_contratacao']:
                row['_cotacoes_aguardando_contratacao'].add(cotacao_key)
                row['aguardando_contratacao'] += 1
        elif item.status == 'contratado':
            if cotacao_key not in row['_cotacoes_contratado']:
                row['_cotacoes_contratado'].add(cotacao_key)
                row['contratado'] += 1
        elif item.status == 'declinado':
            if cotacao_key not in row['_cotacoes_declinado']:
                row['_cotacoes_declinado'].add(cotacao_key)
                row['declinado'] += 1
        elif item.status == 'encerrada':
            if cotacao_key not in row['_cotacoes_inviavel']:
                row['_cotacoes_inviavel'].add(cotacao_key)
                row['inviavel'] += 1

    for row in rows:
        row.pop('_cotacoes_total', None)
        row.pop('_cotacoes_em_negociacao', None)
        row.pop('_cotacoes_aguardando_contratacao', None)
        row.pop('_cotacoes_contratado', None)
        row.pop('_cotacoes_declinado', None)
        row.pop('_cotacoes_inviavel', None)

    rows = sorted(
        rows,
        key=lambda item: _sortable_value({
            'endereco': item['endereco_nome'],
            'cliente': item['cliente_nome'],
            'total_cotacoes': item['total_cotacoes'],
            'em_negociacao': item['em_negociacao'],
            'aguardando_contratacao': item['aguardando_contratacao'],
            'contratado': item['contratado'],
            'declinado': item['declinado'],
            'inviavel': item['inviavel'],
        }[sort_by]),
        reverse=(direction == 'desc'),
    )

    return rows, totais_por_status


def montar_relatorio_login_usuario(busca='', usuario_filtro='', sort_by='empresa', direction='asc'):
    """Retorna (rows, total_resultados, total_com_responsavel,
    total_sem_responsavel) para o relatorio Responsaveis por Endereco
    (propostas em analise, com ou sem responsavel definido)."""
    queryset = Proposal.objects.filter(status='analise').select_related(
        'partner', 'cliente', 'client_address', 'responsavel',
    ).annotate(ultima_interacao=Subquery(_ultima_interacao_subquery()))

    if busca:
        queryset = queryset.filter(
            Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
            | Q(client_address__login_ixc__icontains=busca)
            | Q(responsavel__username__icontains=busca)
            | Q(responsavel__first_name__icontains=busca)
            | Q(responsavel__last_name__icontains=busca)
        )

    if usuario_filtro == '__sem__':
        queryset = queryset.filter(responsavel__isnull=True)
    elif usuario_filtro:
        queryset = queryset.filter(responsavel_id=usuario_filtro)

    order_map = {
        'empresa': ['partner__nome_fantasia', 'partner__razao_social', 'id'],
        'cotacao': ['codigo_proposta', 'nome_proposta', 'id'],
        'cliente': ['cliente__nome_fantasia', 'cliente__razao_social', 'id'],
        'login': ['client_address__login_ixc', 'id'],
        'usuario': ['responsavel__username', 'id'],
        'ultimo_comentario': ['ultima_interacao', 'id'],
        'status': ['responsavel__isnull', 'id'],
    }
    ordering = order_map[sort_by]
    if direction == 'desc':
        ordering = [f"-{field}" for field in ordering]
    queryset = queryset.order_by(*ordering)

    total_resultados = queryset.count()
    total_com_responsavel = queryset.exclude(responsavel__isnull=True).count()
    total_sem_responsavel = queryset.filter(responsavel__isnull=True).count()

    rows = []
    for item in queryset:
        rows.append({
            'pk': item.pk,
            'partner_nome': _proposal_partner_nome(item),
            'codigo_exibicao': item.codigo_exibicao,
            'nome_proposta': item.nome_proposta or 'Cotação sem nome',
            'cliente_nome': _proposal_cliente_nome(item),
            'login_nome': _proposal_endereco_nome(item),
            'responsavel_nome': _proposal_responsavel_nome(item),
            'responsavel_id': item.responsavel_id or '',
            'ultima_interacao': item.ultima_interacao,
        })

    return rows, total_resultados, total_com_responsavel, total_sem_responsavel


def validar_transicao_responsavel_login(proposal):
    """Retorna None se o responsavel do login pode ser alterado, ou a
    mensagem de erro caso contrario (so e possivel com a proposta em
    'analise')."""
    if proposal.status != 'analise':
        return "Só é possível trocar o responsável quando a proposta estiver em Em Negociação."
    return None


def atualizar_responsavel_login(proposal, novo_responsavel, usuario):
    """Atualiza o responsavel do login e registra o historico da troca."""
    responsavel_anterior = proposal.responsavel
    proposal.responsavel = novo_responsavel
    proposal.save(update_fields=['responsavel'])

    nome_anterior = (
        responsavel_anterior.get_full_name() or responsavel_anterior.username
        if responsavel_anterior else '--'
    )
    nome_atual = novo_responsavel.get_full_name() or novo_responsavel.username

    RegistroHistorico.objects.create(
        tipo='sistema',
        acao=(
            "Responsável do login atualizado pela área de Gestão.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"Login: {proposal.client_address.login_ixc if proposal.client_address else '--'}\n"
            f"De: {nome_anterior}\n"
            f"Para: {nome_atual}"
        ),
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id=proposal.id,
    )


# ==============================================================================
# PROPOSTA — sub-fatia "CRUD e navegacao" (risco baixo). As sub-fatias "Lote"
# e "Fechamento de O.S. e edicao financeira" ainda vivem em views.py.
# ==============================================================================

def _registrar_historico_proposta(proposal, usuario, acao, tipo='sistema', arquivo=None):
    """Relocado de views.py (usado tambem pelas sub-fatias Lote e Fechamento
    de O.S., ainda nao migradas) — mesma assinatura e comportamento."""
    RegistroHistorico.objects.create(
        tipo=tipo,
        acao=acao,
        arquivo=arquivo,
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id=proposal.id,
    )


def _extrair_ip_request(request):
    """Relocado de views.py — mesma assinatura e comportamento."""
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _extrair_user_agent_request(request):
    """Relocado de views.py — mesma assinatura e comportamento."""
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


def _registrar_auditoria_status_cotacao(
    request,
    proposal,
    status_anterior,
    status_novo,
    *,
    origem,
    integrou_ixc=False,
    detalhes='',
):
    """Relocado de views.py (usado tambem pelas sub-fatias Lote e Fechamento
    de O.S., ainda nao migradas) — mesma assinatura e comportamento."""
    if status_anterior == status_novo:
        return

    cliente_nome = str(proposal.cliente or '--')
    endereco_referencia = ''
    if proposal.client_address_id:
        endereco_referencia = str(proposal.client_address)
    elif proposal.lead_endereco_id:
        endereco_referencia = str(proposal.lead_endereco)

    CotacaoStatusAuditoria.objects.create(
        usuario=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
        proposal=proposal,
        codigo_cotacao=proposal.codigo_exibicao,
        codigo_lote=proposal.codigo_proposta or '',
        parceiro_nome=proposal.partner.nome_fantasia or proposal.partner.razao_social or '',
        cliente_nome=cliente_nome,
        endereco_referencia=endereco_referencia,
        status_anterior=status_anterior,
        status_novo=status_novo,
        origem=origem,
        integrou_ixc=integrou_ixc,
        endereco_ip=_extrair_ip_request(request),
        user_agent=_extrair_user_agent_request(request),
        detalhes=detalhes,
    )


def criar_proposal(partner, usuario, endereco=None):
    """Cria uma nova Proposal (OS) para o parceiro, opcionalmente vinculada a
    um endereco (client_address/cliente), com grupo_proposta_id e
    codigo_proposta ja resolvidos, e registra o historico de abertura."""
    proposal = Proposal(partner=partner)
    if endereco is not None:
        proposal.client_address = endereco
        proposal.cliente = endereco.cliente

    proposal.save()
    if not proposal.grupo_proposta_id:
        proposal.grupo_proposta_id = proposal.id
    if not proposal.codigo_proposta:
        proposal.codigo_proposta = Proposal.montar_codigo_proposta(proposal.grupo_proposta_id or proposal.id)
    proposal.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

    _registrar_historico_proposta(
        proposal,
        usuario,
        (
            "Proposta iniciada.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"Cliente: {proposal.cliente or '--'}\n"
            f"Unidade: {proposal.client_address or '--'}"
        ),
    )
    return proposal


def assumir_responsavel_login(proposal, usuario):
    """Atribui o usuario como responsavel do login (proposta) e registra o
    historico da troca.

    Retorna (estado, mensagem), com estado em:
    - 'bloqueado': proposta fora de 'analise';
    - 'ja_responsavel': usuario ja e o responsavel atual;
    - 'atualizado': responsavel alterado com sucesso.
    """
    if proposal.status != 'analise':
        return 'bloqueado', "Só é possível assumir um login quando a proposta estiver em Em Negociação."

    responsavel_anterior = proposal.responsavel
    if responsavel_anterior and responsavel_anterior.id == usuario.id:
        return 'ja_responsavel', "Esse login já está com você como responsável."

    proposal.responsavel = usuario
    proposal.save(update_fields=['responsavel'])

    nome_anterior = (responsavel_anterior.get_full_name() or responsavel_anterior.username) if responsavel_anterior else '--'
    nome_atual = usuario.get_full_name() or usuario.username
    _registrar_historico_proposta(
        proposal,
        usuario,
        (
            "Responsável do login atualizado.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"Login: {proposal.client_address.login_ixc if proposal.client_address else '--'}\n"
            f"De: {nome_anterior}\n"
            f"Para: {nome_atual}"
        ),
    )
    return 'atualizado', "Esse login foi atribuído ao seu usuário."


def atualizar_status_proposal_individual(request, proposal):
    """Aplica a transicao de status individual de uma proposta (fora do
    fluxo 'ativa', tratado direto na view por redirecionar para
    proposal_update). Retorna um dos estados:
    - 'invalido': novo_status nao esta em Proposal.STATUS_CHOICES;
    - 'ativa': redireciona para completar dados tecnicos/financeiros (a
      view decide a URL, esta funcao so identifica o caso);
    - 'sem_mudanca': novo_status == status atual, nada foi alterado;
    - 'atualizado': status mudou, auditoria e historico registrados.
    """
    novo_status = request.POST.get('status')
    status_validos = {choice[0] for choice in Proposal.STATUS_CHOICES}

    if novo_status not in status_validos:
        return 'invalido', None

    if novo_status == 'ativa':
        return 'ativa', None

    status_antigo = proposal.status
    if status_antigo == novo_status:
        return 'sem_mudanca', None

    proposal.status = novo_status
    proposal.save(update_fields=['status'])
    _registrar_auditoria_status_cotacao(
        request,
        proposal,
        status_antigo,
        novo_status,
        origem='alteracao_individual',
        integrou_ixc=False,
        detalhes=f"Atualizacao individual da cotacao #{proposal.codigo_exibicao}.",
    )

    RegistroHistorico.objects.create(
        tipo='sistema',
        acao=(
            "Status da proposta atualizado.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"Cliente: {proposal.cliente or '--'}\n"
            f"De: {dict(Proposal.STATUS_CHOICES).get(status_antigo, status_antigo)}\n"
            f"Para: {proposal.get_status_display()}"
        ),
        usuario=request.user,
        content_type=ContentType.objects.get_for_model(Partner),
        object_id=proposal.partner_id,
    )
    return 'atualizado', None


def listar_propostas_globais():
    """Retorna (proposals, total_receita) para a lista global de propostas
    em aberto (fora do funil ja concluido/encerrado)."""
    proposals = Proposal.objects.exclude(
        status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']
    ).select_related('partner', 'cliente').order_by('-id')
    total_receita = proposals.aggregate(Sum('valor_mensal'))['valor_mensal__sum'] or 0
    return proposals, total_receita


def listar_propostas_do_endereco(endereco):
    """Retorna as propostas em aberto vinculadas a um endereco (cliente)."""
    return Proposal.objects.filter(client_address=endereco).exclude(
        status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']
    ).select_related('partner', 'cliente')


# ==============================================================================
# PROPOSTA — sub-fatia "Lote" (risco baixo). A sub-fatia "Fechamento de O.S.
# e edicao financeira" ainda vive em views.py.
# ==============================================================================

def _endereco_possui_os_lastmile(endereco):
    """Relocado de views.py (usado tambem pela sub-fatia Fechamento de O.S.,
    ainda nao migrada) — mesma assinatura e comportamento."""
    if not endereco:
        return False

    setor_nome = (getattr(endereco, 'setor_os_atual_nome', '') or '').strip().lower()
    return bool(
        getattr(endereco, 'ticket_os_atual_ixc', None)
        and getattr(endereco, 'os_atual_aberta', False)
        and (
            getattr(endereco, 'em_os_comercial_lastmile', False)
            or 'lastmile' in setor_nome
        )
    )


def _propostas_com_os_lastmile(propostas_lote):
    """Relocado de views.py (usado tambem pela sub-fatia Fechamento de O.S.,
    ainda nao migrada) — mesma assinatura e comportamento."""
    return [
        item for item in propostas_lote
        if item.client_address_id and _endereco_possui_os_lastmile(item.client_address)
    ]


def _outras_cotacoes_em_negociacao_mesmo_endereco(propostas_lote):
    """Relocado de views.py (usado tambem pela sub-fatia Fechamento de O.S.,
    ainda nao migrada) — mesma assinatura e comportamento."""
    endereco_ids = sorted({item.client_address_id for item in propostas_lote if item.client_address_id})
    if not endereco_ids:
        return []

    proposal_ids = [item.id for item in propostas_lote if item.id]
    codigos_lote = [item.codigo_proposta for item in propostas_lote if item.codigo_proposta]

    queryset = (
        Proposal.objects.filter(client_address_id__in=endereco_ids, status='analise')
        .exclude(id__in=proposal_ids)
        .select_related('partner', 'cliente', 'client_address')
        .order_by('client_address_id', 'id')
    )
    if codigos_lote:
        queryset = queryset.exclude(codigo_proposta__in=codigos_lote)

    return list(queryset)


def _montar_resumo_outras_cotacoes_por_endereco(outras_cotacoes):
    """Relocado de views.py (usado tambem pela sub-fatia Fechamento de O.S.,
    ainda nao migrada) — mesma assinatura e comportamento."""
    grupos = []
    grupos_map = {}

    for item in outras_cotacoes:
        endereco_id = item.client_address_id or f"sem-endereco-{item.id}"
        if endereco_id not in grupos_map:
            grupos_map[endereco_id] = {
                'endereco_id': endereco_id,
                'endereco_nome': str(item.client_address or '--'),
                'cotacoes': [],
            }
            grupos.append(grupos_map[endereco_id])

        grupos_map[endereco_id]['cotacoes'].append({
            'id': item.id,
            'codigo_exibicao': item.codigo_exibicao,
            'parceiro_nome': item.partner.nome_fantasia or item.partner.razao_social,
            'cliente_nome': str(item.cliente or '--'),
        })

    return grupos


def listar_propostas_do_lote(proposal):
    """Retorna as propostas do mesmo lote (codigo_proposta) de `proposal`,
    ordenadas por id."""
    return list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta)
        .select_related('client_address')
        .order_by('id')
    )


def montar_historico_do_lote(proposal, inicio_dt, fim_dt):
    """Retorna (total_logins_lote, historico_lote): a quantidade de logins
    do lote e o historico do periodo informado, deduplicando registros
    replicados (mesmo tipo/usuario/texto/arquivo/instante) em uma unica
    linha, com a contagem de quantas propostas do lote foram afetadas."""
    proposal_ids = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta)
        .order_by('id')
        .values_list('id', flat=True)
    )

    historico_qs = RegistroHistorico.objects.filter(
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id__in=proposal_ids,
        data__range=(inicio_dt, fim_dt),
    ).order_by('-data')

    proposal_ids_historico = {registro.object_id for registro in historico_qs}
    proposals_map = {
        item.id: item
        for item in Proposal.objects.filter(id__in=proposal_ids_historico)
        .select_related('cliente', 'client_address', 'partner')
    }

    historico_lote = []
    historico_replicado_map = {}

    for registro in historico_qs:
        arquivo_nome = registro.arquivo.name if registro.arquivo else ''
        chave_replicacao = (
            registro.tipo,
            registro.usuario_id,
            (registro.acao or '').strip(),
            arquivo_nome,
            registro.data.replace(microsecond=0),
        )

        if chave_replicacao in historico_replicado_map:
            item_existente = historico_replicado_map[chave_replicacao]
            item_existente['proposals_afetadas'].append(registro.object_id)
            continue

        item = {
            'registro': registro,
            'proposal': proposals_map.get(registro.object_id),
            'proposals_afetadas': [registro.object_id],
            'replicado_lote': False,
            'quantidade_afetada': 1,
        }
        historico_replicado_map[chave_replicacao] = item
        historico_lote.append(item)

    for item in historico_lote:
        quantidade_afetada = len(set(item['proposals_afetadas']))
        item['quantidade_afetada'] = quantidade_afetada
        item['replicado_lote'] = quantidade_afetada > 1

    return len(proposal_ids), historico_lote


def montar_contexto_lote(proposal, inicio_dt, fim_dt):
    """Monta os dados de negocio da tela de detalhe do lote: contagem de
    logins, historico consolidado, motivos de inviabilidade ativos e o
    alerta de OS LastMile/outras cotacoes em negociacao no mesmo
    endereco."""
    total_logins_lote, historico_lote = montar_historico_do_lote(proposal, inicio_dt, fim_dt)
    motivos_inviavel_ativos = ProposalMotivoInviavel.objects.filter(status='ativo').order_by('nome')
    propostas_lote = listar_propostas_do_lote(proposal)
    possui_os_lastmile = bool(_propostas_com_os_lastmile(propostas_lote))
    outras_cotacoes_abertas = _outras_cotacoes_em_negociacao_mesmo_endereco(propostas_lote)
    outras_cotacoes_por_endereco = _montar_resumo_outras_cotacoes_por_endereco(outras_cotacoes_abertas)

    return {
        'total_logins_lote': total_logins_lote,
        'historico_lote': historico_lote,
        'motivos_inviavel_ativos': motivos_inviavel_ativos,
        'possui_os_lastmile': possui_os_lastmile,
        'outras_cotacoes_abertas_qtd': len(outras_cotacoes_abertas),
        'outras_cotacoes_por_endereco': outras_cotacoes_por_endereco,
    }


def replicar_historico_lote(proposal, usuario, descricao='', arquivo=None):
    """Registra um historico (comentario/anexo) replicado em todas as
    propostas do mesmo lote (codigo_proposta). Retorna False se nao havia
    descricao nem arquivo (nada a registrar), True caso contrario."""
    if not (descricao or arquivo):
        return False

    tipo = 'anexo' if arquivo else 'comentario'
    acao = descricao or "Anexo registrado no lote da proposta."

    for item in Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta).order_by('id'):
        _registrar_historico_proposta(item, usuario, acao, tipo=tipo, arquivo=arquivo)

    return True


# ==============================================================================
# PROPOSTA — sub-fatia "Fechamento de O.S. e edicao financeira" (risco alto:
# RN-017/RN-018, integracao com o IXCGateway e fila de fallback da ADR-006,
# calculo financeiro). Ultima sub-fatia do grupo Proposta.
# ==============================================================================

def _status_os_ixc_para_operador(alterar_os_ixc, resultado_ixc=None):
    """Relocado de views.py — mesma assinatura e comportamento."""
    if not alterar_os_ixc:
        return "Não alterada"
    if isinstance(resultado_ixc, dict) and resultado_ixc.get('already_closed'):
        return "Já estava finalizada"
    return "Finalizada agora"


def _detalhe_os_ixc_para_historico(alterar_os_ixc, observacao_contratacao='', resultado_ixc=None):
    """Relocado de views.py — mesma assinatura e comportamento."""
    detalhe = f"O.S. no IXC: {_status_os_ixc_para_operador(alterar_os_ixc, resultado_ixc)}"
    if alterar_os_ixc and observacao_contratacao:
        detalhe += f"\nObservação enviada ao IXC: {observacao_contratacao}"
    return detalhe


def _detalhe_os_ixc_para_auditoria(alterar_os_ixc, observacao_contratacao='', resultado_ixc=None):
    """Relocado de views.py — mesma assinatura e comportamento."""
    detalhe = f"Status da O.S. no IXC: {_status_os_ixc_para_operador(alterar_os_ixc, resultado_ixc)}."
    if alterar_os_ixc and observacao_contratacao:
        detalhe += f" Observacao enviada ao IXC: {observacao_contratacao}."
    return detalhe.strip()


def _mensagem_os_ixc_ja_finalizada(propostas):
    """Relocado de views.py — mesma assinatura e comportamento."""
    if not propostas:
        return ""
    if len(propostas) == 1:
        return f"A O.S. da cotação #{propostas[0].codigo_exibicao} já estava finalizada no IXC e o sistema tratou isso como sucesso."
    return f"{len(propostas)} O.S. já estavam finalizadas no IXC e o sistema tratou esses casos como sucesso."


def _baixar_endereco_da_fila_lastmile(endereco):
    """Relocado de views.py — mesma assinatura e comportamento."""
    if not endereco:
        return

    update_fields = []

    if endereco.os_atual_aberta:
        endereco.os_atual_aberta = False
        update_fields.append('os_atual_aberta')

    if endereco.em_os_comercial_lastmile:
        endereco.em_os_comercial_lastmile = False
        update_fields.append('em_os_comercial_lastmile')

    if endereco.status_os_atual_nome != 'Finalizada':
        endereco.status_os_atual_nome = 'Finalizada'
        update_fields.append('status_os_atual_nome')

    if update_fields:
        endereco.save(update_fields=update_fields)


def _resumir_erro_anexo_ixc(resultado):
    """Relocado de views.py — mesma assinatura e comportamento."""
    if not isinstance(resultado, dict):
        return "Falha desconhecida ao enviar anexo ao atendimento no IXC."

    if resultado.get('message'):
        mensagem = strip_tags(unescape(str(resultado['message']))).strip()
        return mensagem or "Falha ao enviar anexo ao atendimento no IXC."

    body = resultado.get('body') or {}
    detalhes_os = resultado.get('detalhes_os') or {}
    os_id = detalhes_os.get('id') or '--'
    ticket_id = resultado.get('ticket_id') or detalhes_os.get('id_ticket') or '--'
    arquivo_nome = resultado.get('arquivo_nome') or '--'
    mensagem = ''
    if isinstance(body, dict):
        mensagem = body.get('message') or body.get('raw') or ''

    if mensagem:
        mensagem_limpa = strip_tags(unescape(str(mensagem))).strip()
        if 'sessão foi finalizada' in mensagem_limpa.lower() or 'sessao foi finalizada' in mensagem_limpa.lower():
            return (
                f"O.S. {os_id} / atendimento {ticket_id} / arquivo {arquivo_nome}: "
                "o IXC recusou o anexo porque a sessão do painel não ficou autenticada. "
                "Use o e-mail de login do IXC e a senha desse usuário, não um e-mail pessoal."
            )
        return f"O.S. {os_id} / atendimento {ticket_id} / arquivo {arquivo_nome}: {mensagem_limpa}"

    return f"O.S. {os_id} / atendimento {ticket_id} / arquivo {arquivo_nome}: falha ao enviar anexo ao IXC."


def _encerrar_outras_cotacoes_automaticamente(outras_cotacoes, proposal_referencia, usuario, request=None):
    """Relocado de views.py — mesma assinatura e comportamento."""
    if not outras_cotacoes:
        return 0

    observacao_padrao = (
        f"Fechada automaticamente porque foi decidido seguir com a cotação #{proposal_referencia.codigo_exibicao}."
    )[:150]

    for item in outras_cotacoes:
        status_antigo = item.status
        item.status = 'encerrada'
        item.motivo_inviavel = None
        item.observacao_inviavel = observacao_padrao
        item.save(update_fields=['status', 'motivo_inviavel', 'observacao_inviavel'])

        _registrar_historico_proposta(
            item,
            usuario,
            (
                "Cotação fechada automaticamente.\n\n"
                f"ID da proposta: #{item.codigo_exibicao}\n"
                f"De: {dict(Proposal.STATUS_CHOICES).get(status_antigo, status_antigo)}\n"
                f"Para: {dict(Proposal.STATUS_CHOICES).get('encerrada', 'encerrada')}\n"
                f"Observação: {observacao_padrao}"
            ),
        )
        if request is not None:
            _registrar_auditoria_status_cotacao(
                request,
                item,
                status_antigo,
                'encerrada',
                origem='fechamento_automatico',
                integrou_ixc=False,
                detalhes=observacao_padrao,
            )

    return len(outras_cotacoes)


def _mensagem_bloqueio_ixc_por_outras_cotacoes(outras_cotacoes):
    """Relocado de views.py — mesma assinatura e comportamento."""
    quantidade = len(outras_cotacoes)
    if quantidade <= 0:
        return ""
    return (
        f"Não é possível finalizar a O.S. no IXC porque este endereço ainda possui "
        f"{quantidade} outra(s) cotação(ões) em negociação. Feche essas cotações primeiro "
        f"ou escolha a opção de encerrá-las automaticamente ao seguir com a cotação viável."
    )


def _fechar_os_ixc_para_lote(propostas_com_os_lastmile, observacao_contratacao, arquivo_ixc, usuario):
    """Executa o fechamento de O.S. no IXC (anexo opcional + finalizacao)
    para cada proposta com O.S. LastMile aberta — logica compartilhada,
    antes duplicada entre `proposal_batch_status_update` e
    `proposal_update`. Retorna (falhas_ixc, resultados_ixc_por_proposta,
    propostas_com_os_ja_finalizada)."""
    falhas_ixc = []
    resultados_ixc_por_proposta = {}
    propostas_com_os_ja_finalizada = []

    for item in propostas_com_os_lastmile:
        if arquivo_ixc:
            resultado_anexo = anexar_arquivo_atendimento_por_os(
                os_id=item.client_address.ticket_os_atual_ixc,
                uploaded_file=arquivo_ixc,
                descricao=observacao_contratacao or f"Anexo enviado na mudança da cotação #{item.codigo_exibicao} para aguardando contratação.",
            )
            if not resultado_anexo.get('ok'):
                falhas_ixc.append({'proposal': item, 'resultado': resultado_anexo, 'tipo': 'anexo'})
                continue

        resultado_ixc = finalizar_os_existente(
            os_id=item.client_address.ticket_os_atual_ixc,
            mensagem=observacao_contratacao,
            finaliza_atendimento=False,
            usuario_sistema=usuario,
        )
        if not resultado_ixc.get('ok'):
            falhas_ixc.append({'proposal': item, 'resultado': resultado_ixc, 'tipo': 'finalizacao'})
            continue

        resultados_ixc_por_proposta[item.id] = resultado_ixc
        if resultado_ixc.get('already_closed'):
            propostas_com_os_ja_finalizada.append(item)
        _baixar_endereco_da_fila_lastmile(item.client_address)

    return falhas_ixc, resultados_ixc_por_proposta, propostas_com_os_ja_finalizada


def _mensagem_falha_ixc(falha):
    """Traduz a primeira falha do fechamento de O.S. no IXC (anexo ou
    finalizacao) para a mensagem de erro exibida ao usuario — logica
    compartilhada, antes duplicada entre `proposal_batch_status_update` e
    `proposal_update`."""
    if falha.get('tipo') == 'anexo':
        return (
            f"Não foi possível enviar o anexo ao atendimento no IXC para a cotação "
            f"#{falha['proposal'].codigo_exibicao}. {_resumir_erro_anexo_ixc(falha['resultado'])}"
        )
    return (
        f"Não foi possível finalizar a O.S. no IXC para a cotação "
        f"#{falha['proposal'].codigo_exibicao}. {resumir_erro_finalizacao(falha['resultado'])}"
    )


def aplicar_atualizacao_lote_status(
    request, proposal, *, novo_status, observacao_inviavel='', observacao_contratacao='',
    alterar_os_ixc=False, fechar_outras_cotacoes='nao', arquivo_ixc=None, motivo_id=None,
):
    """Aplica a atualizacao de status em lote (todas as propostas do mesmo
    codigo_proposta), incluindo o fechamento de O.S. no IXC quando
    novo_status='aguardando_contratacao' e alterar_os_ixc=True.

    Retorna {'mensagens': [(nivel, texto), ...], 'redirect_url': str} — o
    chamador aplica _append_next(redirect_url, next_param) e dispara cada
    mensagem na ordem com django.contrib.messages (nivel em
    'error'/'info'/'success').
    """
    status_validos = {choice[0] for choice in Proposal.STATUS_CHOICES}
    redirect_batch_detail = reverse('proposal_batch_detail', args=[proposal.pk])

    if novo_status not in status_validos:
        return {'mensagens': [('error', "Status de cotação inválido.")], 'redirect_url': redirect_batch_detail}

    propostas_lote = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta)
        .select_related('cliente', 'client_address')
    )
    status_antigo = proposal.status
    motivo_inviavel = None

    if novo_status == 'encerrada':
        motivo_inviavel = ProposalMotivoInviavel.objects.filter(pk=motivo_id, status='ativo').first()
        if not motivo_inviavel:
            return {'mensagens': [('error', "Selecione um motivo ativo para marcar a cotação como inviável.")], 'redirect_url': redirect_batch_detail}
        if not observacao_inviavel:
            return {'mensagens': [('error', "Preencha a observação da cotação inviável.")], 'redirect_url': redirect_batch_detail}
        if len(observacao_inviavel) > 150:
            return {'mensagens': [('error', "A observação da cotação inviável deve ter no máximo 150 caracteres.")], 'redirect_url': redirect_batch_detail}

    propostas_com_os_lastmile = []
    resultados_ixc_por_proposta = {}
    mensagens_extra = []

    if novo_status == 'aguardando_contratacao':
        propostas_com_os_lastmile = _propostas_com_os_lastmile(propostas_lote)

        if alterar_os_ixc:
            if not observacao_contratacao:
                return {
                    'mensagens': [('error', "Preencha a observação para alterar a O.S. no IXC antes de enviar a cotação para aguardando contratação.")],
                    'redirect_url': redirect_batch_detail,
                }

            falhas_ixc, resultados_ixc_por_proposta, propostas_com_os_ja_finalizada = _fechar_os_ixc_para_lote(
                propostas_com_os_lastmile, observacao_contratacao, arquivo_ixc, request.user,
            )
            if falhas_ixc:
                return {'mensagens': [('error', _mensagem_falha_ixc(falhas_ixc[0]))], 'redirect_url': redirect_batch_detail}

            if propostas_com_os_ja_finalizada:
                mensagens_extra.append(('info', _mensagem_os_ixc_ja_finalizada(propostas_com_os_ja_finalizada)))

    if novo_status == 'ativa':
        return {
            'mensagens': [('success', "Cotação marcada como viável. Complete agora os dados técnicos e financeiros.")],
            'redirect_url': f"{reverse('proposal_update', args=[proposal.pk])}?modo=convertida&status_pendente=ativa&fechar_outras_cotacoes={fechar_outras_cotacoes}",
        }

    if status_antigo == novo_status:
        return {'mensagens': mensagens_extra, 'redirect_url': redirect_batch_detail}

    for item in propostas_lote:
        item.status = novo_status
        if novo_status == 'encerrada':
            item.motivo_inviavel = motivo_inviavel
            item.observacao_inviavel = observacao_inviavel
        else:
            item.motivo_inviavel = None
            item.observacao_inviavel = None
        item.save(update_fields=['status', 'motivo_inviavel', 'observacao_inviavel'])

        detalhe_item_inviavel = ""
        detalhe_item_contratacao = ""
        if novo_status == 'encerrada':
            detalhe_item_inviavel = f"\nMotivo: {motivo_inviavel.nome}\nObservação: {observacao_inviavel}"
        elif novo_status == 'aguardando_contratacao':
            detalhe_item_contratacao = (
                "\n"
                + _detalhe_os_ixc_para_historico(
                    alterar_os_ixc,
                    observacao_contratacao,
                    resultados_ixc_por_proposta.get(item.id),
                )
            )

        _registrar_historico_proposta(
            item,
            request.user,
            (
                "Status da proposta atualizado no lote.\n\n"
                f"ID da proposta: #{item.codigo_exibicao}\n"
                f"Cliente: {item.cliente or '--'}\n"
                f"De: {dict(Proposal.STATUS_CHOICES).get(status_antigo, status_antigo)}\n"
                f"Para: {item.get_status_display()}"
                f"{detalhe_item_inviavel}"
                f"{detalhe_item_contratacao}"
            ),
        )
        _registrar_auditoria_status_cotacao(
            request,
            item,
            status_antigo,
            novo_status,
            origem='alteracao_lote',
            integrou_ixc=bool(novo_status == 'aguardando_contratacao' and alterar_os_ixc),
            detalhes=(
                f"Atualizacao em lote da cotacao #{item.codigo_exibicao}."
                f"{f' Motivo inviavel: {motivo_inviavel.nome}.' if novo_status == 'encerrada' and motivo_inviavel else ''}"
                f"{f' Observacao inviavel: {observacao_inviavel}.' if novo_status == 'encerrada' and observacao_inviavel else ''}"
                f"{f' {_detalhe_os_ixc_para_auditoria(alterar_os_ixc, observacao_contratacao, resultados_ixc_por_proposta.get(item.id))}' if novo_status == 'aguardando_contratacao' else ''}"
            ).strip(),
        )

    detalhe_lote_inviavel = ""
    detalhe_lote_contratacao = ""
    if novo_status == 'encerrada':
        detalhe_lote_inviavel = f"Motivo: {motivo_inviavel.nome}\nObservação: {observacao_inviavel}\n"
    elif novo_status == 'aguardando_contratacao':
        if propostas_com_os_lastmile:
            detalhes_os_lote = [
                f"Cotação #{item.codigo_exibicao}: {_status_os_ixc_para_operador(alterar_os_ixc, resultados_ixc_por_proposta.get(item.id))}"
                for item in propostas_com_os_lastmile
            ]
            detalhe_lote_contratacao = "Status das O.S. no IXC:\n" + "\n".join(detalhes_os_lote) + "\n"
            if alterar_os_ixc and observacao_contratacao:
                detalhe_lote_contratacao += f"Observação enviada ao IXC: {observacao_contratacao}\n"
        else:
            detalhe_lote_contratacao = f"{_detalhe_os_ixc_para_historico(alterar_os_ixc, observacao_contratacao)}\n"

    RegistroHistorico.objects.create(
        tipo='sistema',
        acao=(
            "Status do lote da proposta atualizado.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"De: {dict(Proposal.STATUS_CHOICES).get(status_antigo, status_antigo)}\n"
            f"Para: {dict(Proposal.STATUS_CHOICES).get(novo_status, novo_status)}\n"
            f"{detalhe_lote_inviavel}"
            f"{detalhe_lote_contratacao}"
            f"Quantidade de logins impactados: {len(propostas_lote)}"
        ),
        usuario=request.user,
        content_type=ContentType.objects.get_for_model(Partner),
        object_id=proposal.partner_id,
    )

    if novo_status == 'ativa':
        # Inalcancavel: novo_status == 'ativa' ja retorna mais acima; ramo
        # mantido por fidelidade ao comportamento original (tambem
        # inalcancavel la).
        mensagens_extra.append(('success', "Cotação marcada como viável. Complete agora os dados técnicos e financeiros."))
        return {
            'mensagens': mensagens_extra,
            'redirect_url': f"{reverse('proposal_update', args=[proposal.pk])}?modo=convertida",
        }

    if novo_status in ['contratado', 'declinado']:
        mensagens_extra.append(('success', "Status da cotação atualizado no lote com sucesso."))
        return {'mensagens': mensagens_extra, 'redirect_url': reverse('partner_list')}

    mensagens_extra.append(('success', "Status da cotação atualizado no lote com sucesso."))
    return {'mensagens': mensagens_extra, 'redirect_url': redirect_batch_detail}


def processar_conversao_viavel(
    request, proposal, partner, form, *, propostas_lote, outras_cotacoes_abertas,
    fechar_outras_cotacoes, arquivo_ixc,
):
    """Aplica a conclusao dos dados tecnicos/financeiros apos a cotacao ser
    marcada como viavel (modo=convertida): fecha a O.S. no IXC quando
    solicitado, propaga os campos compartilhados do formulario para todas
    as propostas do lote e seus enderecos, registra historico/auditoria, e
    fecha automaticamente outras cotacoes do mesmo endereco quando
    solicitado.

    Retorna {'ok': True, 'mensagens_info': [...], 'mensagem_sucesso': str}
    em sucesso (sempre redireciona para 'partner_list'), ou
    {'ok': False, 'erro': str} quando bloqueado por uma validacao (outras
    cotacoes abertas sem decisao, observacao obrigatoria, ou falha ao
    fechar a O.S. no IXC) — nesses casos nada foi alterado no banco.
    """
    observacao_contratacao = (request.POST.get('observacao_contratacao') or '').strip()
    alterar_os_ixc = (request.POST.get('alterar_os_ixc') or 'nao').strip().lower() == 'sim'

    if outras_cotacoes_abertas and fechar_outras_cotacoes != 'sim':
        if alterar_os_ixc:
            return {'ok': False, 'erro': _mensagem_bloqueio_ixc_por_outras_cotacoes(outras_cotacoes_abertas)}
        alterar_os_ixc = False

    propostas_com_os_lastmile = _propostas_com_os_lastmile(propostas_lote)

    resultados_ixc_por_proposta = {}
    mensagens_info = []
    if alterar_os_ixc:
        if not observacao_contratacao:
            return {'ok': False, 'erro': "Preencha a observação para alterar a O.S. no IXC antes de enviar a cotação para aguardando contratação."}

        falhas_ixc, resultados_ixc_por_proposta, propostas_com_os_ja_finalizada = _fechar_os_ixc_para_lote(
            propostas_com_os_lastmile, observacao_contratacao, arquivo_ixc, request.user,
        )
        if falhas_ixc:
            return {'ok': False, 'erro': _mensagem_falha_ixc(falhas_ixc[0])}

        if propostas_com_os_ja_finalizada:
            mensagens_info.append(_mensagem_os_ixc_ja_finalizada(propostas_com_os_ja_finalizada))

    partner.cnpj_cpf = form.cleaned_data.get('partner_cnpj_cpf') or partner.cnpj_cpf
    partner.save(update_fields=['cnpj_cpf'])

    proposta_base = form.save(commit=False)
    campos_compartilhados = [
        'nome_proposta', 'velocidade', 'tecnologia', 'disponibilidade', 'mttr',
        'perda_pacote', 'latencia', 'interfaces', 'tipo_acesso', 'ipv4_bloco',
        'dupla_abordagem', 'entrega_rb', 'designador', 'trunk', 'dhcp',
        'prazo_ativacao', 'contato_suporte', 'telefone_suporte', 'ticket_cliente', 'valor_mensal',
        'ticket_empresa',
        'taxa_instalacao', 'valor_parceiro', 'tempo_contrato', 'email_faturamento'
    ]

    for item in propostas_lote:
        status_item_anterior = item.status
        for campo in campos_compartilhados:
            setattr(item, campo, getattr(proposta_base, campo))
        item.status = 'aguardando_contratacao'
        item.save()

        if item.client_address_id:
            endereco = item.client_address
            endereco.velocidade = proposta_base.velocidade
            endereco.tecnologia = proposta_base.tecnologia
            endereco.disponibilidade = proposta_base.disponibilidade
            endereco.mttr = proposta_base.mttr
            endereco.perda_pacote = proposta_base.perda_pacote
            endereco.latencia = proposta_base.latencia
            endereco.interfaces = proposta_base.interfaces
            endereco.tipo_acesso = proposta_base.tipo_acesso
            endereco.ipv4_bloco = proposta_base.ipv4_bloco
            endereco.dupla_abordagem = proposta_base.dupla_abordagem
            endereco.entrega_rb = proposta_base.entrega_rb
            endereco.designador = proposta_base.designador
            endereco.trunk = proposta_base.trunk
            endereco.dhcp = proposta_base.dhcp
            endereco.prazo_ativacao = proposta_base.prazo_ativacao
            endereco.contato_suporte = proposta_base.contato_suporte
            endereco.telefone_suporte = proposta_base.telefone_suporte
            endereco.save(update_fields=[
                'velocidade', 'tecnologia', 'disponibilidade', 'mttr', 'perda_pacote',
                'latencia', 'interfaces', 'tipo_acesso', 'ipv4_bloco', 'dupla_abordagem',
                'entrega_rb', 'designador', 'trunk', 'dhcp', 'prazo_ativacao',
                'contato_suporte', 'telefone_suporte',
            ])

        _registrar_historico_proposta(
            item,
            request.user,
            (
                "Dados técnicos e financeiros preenchidos após proposta viável.\n\n"
                f"ID da proposta: #{item.codigo_exibicao}\n"
                f"Unidade: {item.client_address or '--'}\n"
                f"{_detalhe_os_ixc_para_historico(alterar_os_ixc, observacao_contratacao, resultados_ixc_por_proposta.get(item.id))}"
            ),
        )
        _registrar_auditoria_status_cotacao(
            request,
            item,
            status_item_anterior,
            'aguardando_contratacao',
            origem='conversao_viavel',
            integrou_ixc=alterar_os_ixc,
            detalhes=(
                f"Conversao de cotacao viavel concluida para a proposta #{item.codigo_exibicao}."
                f" {_detalhe_os_ixc_para_auditoria(alterar_os_ixc, observacao_contratacao, resultados_ixc_por_proposta.get(item.id))}"
            ).strip(),
        )

    if propostas_com_os_lastmile:
        detalhes_os_lote = [
            f"Cotação #{item.codigo_exibicao}: {_status_os_ixc_para_operador(alterar_os_ixc, resultados_ixc_por_proposta.get(item.id))}"
            for item in propostas_com_os_lastmile
        ]
        detalhe_lote_os_ixc = "Status das O.S. no IXC:\n" + "\n".join(detalhes_os_lote) + "\n"
        if alterar_os_ixc and observacao_contratacao:
            detalhe_lote_os_ixc += f"Observação enviada ao IXC: {observacao_contratacao}\n"
    else:
        detalhe_lote_os_ixc = f"{_detalhe_os_ixc_para_historico(alterar_os_ixc, observacao_contratacao)}\n"

    RegistroHistorico.objects.create(
        tipo='sistema',
        acao=(
            "Proposta enviada para aguardando contratação após complementação técnica e financeira.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"{detalhe_lote_os_ixc}"
            f"Quantidade de logins impactados: {len(propostas_lote)}"
        ),
        usuario=request.user,
        content_type=ContentType.objects.get_for_model(Partner),
        object_id=partner.id,
    )

    qtd_fechadas_automaticamente = 0
    if fechar_outras_cotacoes == 'sim' and outras_cotacoes_abertas:
        qtd_fechadas_automaticamente = _encerrar_outras_cotacoes_automaticamente(
            outras_cotacoes_abertas, proposal, request.user, request=request,
        )
        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=(
                "Outras cotações do mesmo endereço foram fechadas automaticamente.\n\n"
                f"Cotação escolhida: #{proposal.codigo_exibicao}\n"
                f"Quantidade de cotações fechadas: {qtd_fechadas_automaticamente}"
            ),
            usuario=request.user,
            content_type=ContentType.objects.get_for_model(Partner),
            object_id=partner.id,
        )

    if qtd_fechadas_automaticamente:
        mensagem_sucesso = (
            f"Dados salvos com sucesso. A cotação foi enviada para aguardando contratação e "
            f"{qtd_fechadas_automaticamente} outra(s) cotação(ões) do mesmo endereço foram fechadas automaticamente."
        )
    else:
        mensagem_sucesso = "Dados técnicos e financeiros salvos com sucesso. A cotação foi enviada para a aba de parceiros em aguardando contratação."

    return {'ok': True, 'mensagens_info': mensagens_info, 'mensagem_sucesso': mensagem_sucesso}


def processar_edicao_proposta(request, proposal, partner, form, endereco_atual, enderecos_ids):
    """Aplica a edicao normal da proposta (fora do fluxo de conversao
    viavel): registra o antes/depois dos campos alterados no historico, e
    cria links (clones da proposta) para cada endereco adicional
    selecionado em `enderecos_ids`. O form ja deve ter sido validado
    (`form.is_valid()`) pelo chamador."""
    valores_novos, valores_antigos = [], []
    if form.has_changed():
        for campo in form.changed_data:
            if campo not in ['enderecos_selecionados', 'partner', 'cliente', 'client_address']:
                valor_antigo = form.initial.get(campo)
                valor_novo = form.cleaned_data.get(campo)
                nome_campo = campo.replace('_', ' ').title()

                if any(p in campo for p in ['valor', 'taxa', 'custo', 'pago']):
                    str_antigo = f"R$ {valor_antigo}" if valor_antigo else 'Vazio'
                    str_novo = f"R$ {valor_novo}" if valor_novo else 'Vazio'
                elif campo in ['vigencia', 'tempo_contrato']:
                    str_antigo = f"{valor_antigo} Meses" if valor_antigo else 'Vazio'
                    str_novo = f"{valor_novo} Meses" if valor_novo else 'Vazio'
                else:
                    str_antigo = str(valor_antigo) if valor_antigo else 'Vazio'
                    str_novo = str(valor_novo) if valor_novo else 'Vazio'

                valores_novos.append(f"• {nome_campo}: {str_novo}")
                valores_antigos.append(f"• {nome_campo}: {str_antigo}")

    mudou_unidade, novas_unidades = False, []
    if enderecos_ids:
        enderecos_ids = list(enderecos_ids)
        proposta_base = form.save(commit=False)

        primeiro_endereco_id = enderecos_ids.pop(0)
        primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)

        if endereco_atual != primeiro_endereco:
            mudou_unidade = True
            valores_antigos.append(f"• Unidade Base: {endereco_atual}")
            valores_novos.append(f"• Unidade Base: {primeiro_endereco}")

        proposta_base.client_address = primeiro_endereco
        proposta_base.save()
        if not proposta_base.grupo_proposta_id:
            proposta_base.grupo_proposta_id = proposta_base.id
        if not proposta_base.codigo_proposta:
            proposta_base.codigo_proposta = Proposal.montar_codigo_proposta(proposta_base.grupo_proposta_id or proposta_base.id)
        proposta_base.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

        for end_id in enderecos_ids:
            endereco_extra = get_object_or_404(Endereco, pk=end_id)
            clone = Proposal.objects.get(pk=proposta_base.pk)
            clone.pk = None
            clone.grupo_proposta_id = proposta_base.grupo_proposta_id
            clone.codigo_proposta = proposta_base.codigo_proposta
            clone.nome_proposta = proposta_base.nome_proposta
            clone.client_address = endereco_extra
            clone.cliente = endereco_extra.cliente
            clone.save()
            _registrar_historico_proposta(
                clone,
                request.user,
                (
                    "Link criado a partir da proposta principal.\n\n"
                    f"ID da proposta: #{clone.codigo_exibicao}\n"
                    f"Unidade: {clone.client_address or '--'}"
                ),
            )
            novas_unidades.append(f"- {endereco_extra}")
    else:
        proposta_salva = form.save()
        if not proposta_salva.grupo_proposta_id:
            proposta_salva.grupo_proposta_id = proposta_salva.id
        if not proposta_salva.codigo_proposta:
            proposta_salva.codigo_proposta = Proposal.montar_codigo_proposta(proposta_salva.grupo_proposta_id or proposta_salva.id)
        proposta_salva.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])

    if valores_novos or valores_antigos or novas_unidades:
        texto_snapshot = "Edição de Proposta/OS realizada.\n\n"
        if novas_unidades:
            texto_snapshot += f"+ {len(novas_unidades)} NOVO(S) LINK(S) ADICIONADO(S):\n" + "\n".join(novas_unidades) + "\n\n"
        if valores_novos or mudou_unidade:
            if not mudou_unidade and endereco_atual:
                texto_snapshot += f"REFERÊNCIA: {endereco_atual}\n\n"
            texto_snapshot += "Atualizado:\n" + "\n".join(valores_novos) + "\n\n--------------------------------------\n\n"
            texto_snapshot += "Antes:\n" + "\n".join(valores_antigos)

        RegistroHistorico.objects.create(
            tipo='sistema',
            acao=texto_snapshot.strip(),
            usuario=request.user,
            content_type=ContentType.objects.get_for_model(Partner),
            object_id=partner.id,
        )

        _registrar_historico_proposta(proposal, request.user, texto_snapshot.strip())
