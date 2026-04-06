from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlparse, urlencode

from leads.models import Lead
from partners.models import Proposal

from .models import IntegrationAudit, RegistroHistorico


def _resolve_sort(request, allowed_fields, default_field):
    sort_by = (request.GET.get('sort') or '').strip()
    direction = (request.GET.get('direction') or 'asc').strip().lower()

    if sort_by not in allowed_fields:
        sort_by = default_field

    if direction not in ('asc', 'desc'):
        direction = 'asc'

    return sort_by, direction


def _build_sort_links(base_params, current_sort, current_direction, sortable_fields):
    links = {}
    for field in sortable_fields:
        next_direction = 'desc' if current_sort == field and current_direction == 'asc' else 'asc'
        params = {k: v for k, v in base_params.items() if v not in (None, '')}
        params['sort'] = field
        params['direction'] = next_direction
        links[field] = urlencode(params)
    return links


def _sortable_value(value):
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value
    if isinstance(value, str):
        return value.lower()
    return value


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


def grupo_Administrador_required(user):
    if not user.is_authenticated:
        return False
    if user.groups.filter(name='Administrador').exists() or user.is_superuser:
        return True
    raise PermissionDenied


def grupo_Operacao_required(user):
    if not user.is_authenticated:
        return False
    grupos_permitidos = ['Administrador', 'LastMile', 'Parceiro', 'Backoffice']
    if user.groups.filter(name__in=grupos_permitidos).exists() or user.is_superuser:
        return True
    raise PermissionDenied


def grupo_Gestao_required(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_gestor or user.groups.filter(name='Administrador').exists():
        return True
    raise PermissionDenied


def _resolver_periodo_historico(request):
    agora = timezone.now()
    hoje = timezone.localdate(agora) if timezone.is_aware(agora) else agora.date()
    data_inicio = hoje
    data_fim = hoje

    data_inicio_str = (request.GET.get('data_inicio') or '').strip()
    data_fim_str = (request.GET.get('data_fim') or '').strip()

    try:
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d").date()
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
    except ValueError:
        data_inicio = hoje
        data_fim = hoje

    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    inicio_naive = datetime.combine(data_inicio, time.min)
    fim_naive = datetime.combine(data_fim, time.max)

    if timezone.is_aware(agora):
        inicio_dt = timezone.make_aware(inicio_naive)
        fim_dt = timezone.make_aware(fim_naive)
    else:
        inicio_dt = inicio_naive
        fim_dt = fim_naive

    return {
        'inicio_dt': inicio_dt,
        'fim_dt': fim_dt,
        'data_inicio_str': data_inicio.isoformat(),
        'data_fim_str': data_fim.isoformat(),
        'filtro_personalizado': bool(data_inicio_str or data_fim_str),
    }


def _resolver_back_url(request, fallback_url='/'):
    next_param = (request.GET.get('next') or request.POST.get('next') or '').strip()
    if next_param:
        return next_param, next_param

    referer = (request.META.get('HTTP_REFERER') or '').strip()
    if referer:
        parsed = urlparse(referer)
        referer_url = parsed.path
        if parsed.query:
            referer_url = f"{referer_url}?{parsed.query}"
        if referer_url and referer_url != request.get_full_path():
            return referer_url, referer_url

    return fallback_url, ''


@login_required
def home(request):
    context = {
        'total_leads': Lead.objects.count(),
    }
    return render(request, 'core/home.html', context)


@user_passes_test(grupo_Operacao_required)
@login_required
def minhas_cotacoes(request):
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'empresa', 'cotacao', 'cliente', 'endereco', 'ultimo_comentario', 'status'},
        'empresa',
    )
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    ultima_interacao_subquery = RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]

    queryset = Proposal.objects.filter(responsavel=request.user).select_related(
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
        'status': ['status', 'id'],
    }
    ordering = order_map[sort_by]
    if direction == 'desc':
        ordering = [f"-{field}" for field in ordering]
    queryset = queryset.order_by(*ordering)

    totais_por_status = {
        'analise': queryset.filter(status='analise').count(),
        'ativa': queryset.filter(status='ativa').count(),
        'aguardando_contratacao': queryset.filter(status='aguardando_contratacao').count(),
        'contratado': queryset.filter(status='contratado').count(),
        'declinado': queryset.filter(status='declinado').count(),
        'encerrada': queryset.filter(status='encerrada').count(),
    }

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    rows = []
    for item in page_obj:
        rows.append({
            'pk': item.pk,
            'partner_nome': _proposal_partner_nome(item),
            'codigo_exibicao': item.codigo_exibicao,
            'nome_proposta': item.nome_proposta or 'Cotacao sem nome',
            'cliente_nome': _proposal_cliente_nome(item),
            'login_nome': _proposal_endereco_nome(item),
            'responsavel_nome': _proposal_responsavel_nome(item),
            'responsavel_id': item.responsavel_id or '',
            'ultima_interacao': item.ultima_interacao,
        })

    return render(request, 'core/minhas_cotacoes.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'endereco', 'ultimo_comentario', 'status'],
        ),
        'totais_por_status': totais_por_status,
        'total_resultados': queryset.count(),
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_home(request):
    return redirect('gestao_relatorios')


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorios(request):
    sort_by, direction = _resolve_sort(request, {'nome'}, 'nome')
    relatorios_catalogo = [
        {
            'nome': 'Responsáveis por Endereço',
            'url_name': 'gestao_relatorio_login_usuario',
            'descricao': 'Acompanhe os endereços em negociação com e sem responsável definido.',
            'icone': 'users',
            'tag': 'Operação',
        },
        {
            'nome': 'Status por Endereço',
            'url_name': 'gestao_relatorio_login_status',
            'descricao': 'Veja cada endereço distribuído por etapa da cotação.',
            'icone': 'network',
            'tag': 'Pipeline',
        },
        {
            'nome': 'Status por Cotação',
            'url_name': 'gestao_relatorio_proposta_status',
            'descricao': 'Consolidação das cotações por parceiro, cliente e estágio atual.',
            'icone': 'file-text',
            'tag': 'Executivo',
        },
        {
            'nome': 'Cotação por Cliente',
            'url_name': 'gestao_relatorio_status_cliente',
            'descricao': 'Quantidade de cotações por cliente, distribuídas por status.',
            'icone': 'building-2',
            'tag': 'Carteira',
        },
        {
            'nome': 'Cotação por Endereço',
            'url_name': 'gestao_relatorio_cotacao_endereco',
            'descricao': 'Volume de cotações por endereço e visibilidade por etapa.',
            'icone': 'map-pinned',
            'tag': 'Base técnica',
        },
    ]

    busca_relatorio = (request.GET.get('relatorio') or '').strip()
    if busca_relatorio:
        relatorios_catalogo = [
            item for item in relatorios_catalogo
            if busca_relatorio.lower() in item['nome'].lower()
        ]

    relatorios_catalogo = sorted(
        relatorios_catalogo,
        key=lambda item: _sortable_value(item.get('nome')),
        reverse=(direction == 'desc'),
    )

    paginator = Paginator(relatorios_catalogo, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_home.html', {
        'page_obj': page_obj,
        'busca_relatorio': busca_relatorio,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'relatorio': busca_relatorio},
            sort_by,
            direction,
            ['nome'],
        ),
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_logs_integracoes(request):
    User = get_user_model()
    busca = (request.GET.get('busca') or '').strip()
    integracao = (request.GET.get('integracao') or '').strip()
    acao = (request.GET.get('acao') or '').strip()
    usuario_id = (request.GET.get('usuario') or '').strip()
    data_inicio = (request.GET.get('data_inicio') or '').strip()
    data_fim = (request.GET.get('data_fim') or '').strip()

    queryset = IntegrationAudit.objects.select_related('usuario').all()

    if busca:
        queryset = queryset.filter(
            Q(arquivo_nome__icontains=busca)
            | Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
            | Q(usuario__last_name__icontains=busca)
        )

    if integracao:
        queryset = queryset.filter(integration=integracao)

    if acao:
        queryset = queryset.filter(action=acao)

    if usuario_id:
        queryset = queryset.filter(usuario_id=usuario_id)

    try:
        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date())
        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=datetime.strptime(data_fim, '%Y-%m-%d').date())
    except ValueError:
        pass

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_logs_integracoes.html', {
        'page_obj': page_obj,
        'busca': busca,
        'integracao': integracao,
        'acao': acao,
        'usuario_id': usuario_id,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'usuarios': User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        'integration_choices': IntegrationAudit.INTEGRATION_CHOICES,
        'action_choices': IntegrationAudit.ACTION_CHOICES,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_log_integracao_detail(request, pk):
    audit = get_object_or_404(IntegrationAudit.objects.select_related('usuario'), pk=pk)
    itens_list = audit.items.all()
    paginator = Paginator(itens_list, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_log_integracao_detail.html', {
        'audit': audit,
        'page_obj': page_obj,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_login_status(request):
    busca = (request.GET.get('busca') or '').strip()
    status = (request.GET.get('status') or '').strip()
    cliente_param = (request.GET.get('cliente') or '').strip()
    endereco_param = (request.GET.get('endereco') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'empresa', 'cotacao', 'cliente', 'login', 'status', 'responsavel', 'ultima_interacao'},
        'empresa',
    )
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    ultima_interacao_subquery = RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]

    queryset = Proposal.objects.select_related(
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
        )

    if cliente_param:
        queryset = queryset.filter(
            Q(cliente__nome_fantasia__icontains=cliente_param)
            | Q(cliente__razao_social__icontains=cliente_param)
        )

    if endereco_param:
        queryset = queryset.filter(
            Q(client_address__login_ixc__icontains=endereco_param)
            | Q(client_address__logradouro__icontains=endereco_param)
        )

    if status:
        queryset = queryset.filter(status=status)

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

    totais_por_status = {
        'analise': Proposal.objects.filter(status='analise').count(),
        'ativa': Proposal.objects.filter(status='ativa').count(),
        'aguardando_contratacao': Proposal.objects.filter(status='aguardando_contratacao').count(),
        'contratado': Proposal.objects.filter(status='contratado').count(),
        'declinado': Proposal.objects.filter(status='declinado').count(),
        'encerrada': Proposal.objects.filter(status='encerrada').count(),
    }

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    rows = []
    for item in page_obj:
        rows.append({
            'pk': item.pk,
            'partner_nome': _proposal_partner_nome(item),
            'codigo_exibicao': item.codigo_exibicao,
            'nome_proposta': item.nome_proposta or 'Cotacao sem nome',
            'cliente_nome': _proposal_cliente_nome(item),
            'login_nome': _proposal_endereco_nome(item),
            'status': item.status,
            'status_display': _proposal_status_display(item),
            'responsavel_nome': _proposal_responsavel_nome(item),
            'ultima_interacao': item.ultima_interacao,
        })

    return render(request, 'core/gestao_relatorio_proposta_status.html', {
        'page_obj': page_obj,
        'rows': rows,
        'busca': busca,
        'cliente_param': cliente_param,
        'endereco_param': endereco_param,
        'status_filtro': status,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {
                'busca': busca,
                'status': status,
                'cliente': cliente_param,
                'endereco': endereco_param,
            },
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'login', 'status', 'responsavel', 'ultima_interacao'],
        ),
        'totais_por_status': totais_por_status,
        'status_choices': Proposal.STATUS_CHOICES,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_proposta_status(request):
    busca = (request.GET.get('busca') or '').strip()
    status = (request.GET.get('status') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'empresa', 'cotacao', 'cliente', 'qtd_logins', 'status'},
        'empresa',
    )
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    ultima_interacao_subquery = RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]

    queryset = Proposal.objects.select_related(
        'partner',
        'cliente',
        'client_address',
        'responsavel',
    ).annotate(
        ultima_interacao=Subquery(ultima_interacao_subquery)
    ).order_by(
        '-id',
    )

    if busca:
        queryset = queryset.filter(
            Q(codigo_proposta__icontains=busca)
            | Q(nome_proposta__icontains=busca)
            | Q(partner__nome_fantasia__icontains=busca)
            | Q(partner__razao_social__icontains=busca)
            | Q(cliente__nome_fantasia__icontains=busca)
            | Q(cliente__razao_social__icontains=busca)
        )

    if status:
        queryset = queryset.filter(status=status)

    proposals_rows = []
    grouped_rows = {}
    totais_por_status = {
        'analise': 0,
        'ativa': 0,
        'aguardando_contratacao': 0,
        'contratado': 0,
        'declinado': 0,
        'encerrada': 0,
    }

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
                'status': item.status,
                'status_display': _proposal_status_display(item),
                'responsavel_nome': _proposal_responsavel_nome(item),
                'total_logins': 0,
                'ultima_interacao': item.ultima_interacao,
            }
            proposals_rows.append(grouped_rows[group_key])
            if item.status in totais_por_status:
                totais_por_status[item.status] += 1

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

    paginator = Paginator(proposals_rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_relatorio_proposta_status_real.html', {
        'page_obj': page_obj,
        'busca': busca,
        'status_filtro': status,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca, 'status': status},
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'qtd_logins', 'status'],
        ),
        'totais_por_status': totais_por_status,
        'status_choices': Proposal.STATUS_CHOICES,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_status_cliente(request):
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'cliente', 'total_cotacoes', 'em_negociacao', 'viavel', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'},
        'cliente',
    )

    queryset = Proposal.objects.select_related(
        'cliente',
        'partner',
        'client_address',
    ).order_by(
        'cliente__nome_fantasia',
        'cliente__razao_social',
        'codigo_proposta',
        'id',
    )

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

    totais_por_status = {
        'analise': queryset.filter(status='analise').count(),
        'ativa': queryset.filter(status='ativa').count(),
        'aguardando_contratacao': queryset.filter(status='aguardando_contratacao').count(),
        'contratado': queryset.filter(status='contratado').count(),
        'declinado': queryset.filter(status='declinado').count(),
        'encerrada': queryset.filter(status='encerrada').count(),
    }

    grouped_rows = {}
    rows = []

    for item in queryset:
        cliente_nome = '--'
        cliente_key = None
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
                'viavel': 0,
                'aguardando_contratacao': 0,
                'contratado': 0,
                'declinado': 0,
                'inviavel': 0,
                'total_cotacoes': 0,
                '_cotacoes_total': set(),
                '_cotacoes_em_negociacao': set(),
                '_cotacoes_viavel': set(),
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

        if item.status == 'analise':
            if cotacao_key not in row['_cotacoes_em_negociacao']:
                row['_cotacoes_em_negociacao'].add(cotacao_key)
                row['em_negociacao'] += 1
        elif item.status == 'ativa':
            if cotacao_key not in row['_cotacoes_viavel']:
                row['_cotacoes_viavel'].add(cotacao_key)
                row['viavel'] += 1
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
        row.pop('_cotacoes_viavel', None)
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
            'viavel': item['viavel'],
            'aguardando_contratacao': item['aguardando_contratacao'],
            'contratado': item['contratado'],
            'declinado': item['declinado'],
            'inviavel': item['inviavel'],
        }[sort_by]),
        reverse=(direction == 'desc'),
    )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_relatorio_status_cliente.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['cliente', 'total_cotacoes', 'em_negociacao', 'viavel', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'],
        ),
        'totais_por_status': totais_por_status,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_cotacao_endereco(request):
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'endereco', 'cliente', 'total_cotacoes', 'em_negociacao', 'viavel', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'},
        'endereco',
    )

    queryset = Proposal.objects.select_related(
        'cliente',
        'partner',
        'client_address',
    ).order_by(
        'client_address__login_ixc',
        'codigo_proposta',
        'id',
    )

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

    totais_por_status = {
        'analise': queryset.filter(status='analise').count(),
        'ativa': queryset.filter(status='ativa').count(),
        'aguardando_contratacao': queryset.filter(status='aguardando_contratacao').count(),
        'contratado': queryset.filter(status='contratado').count(),
        'declinado': queryset.filter(status='declinado').count(),
        'encerrada': queryset.filter(status='encerrada').count(),
    }

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
                'viavel': 0,
                'aguardando_contratacao': 0,
                'contratado': 0,
                'declinado': 0,
                'inviavel': 0,
                '_cotacoes_total': set(),
                '_cotacoes_em_negociacao': set(),
                '_cotacoes_viavel': set(),
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

        if item.status == 'analise':
            if cotacao_key not in row['_cotacoes_em_negociacao']:
                row['_cotacoes_em_negociacao'].add(cotacao_key)
                row['em_negociacao'] += 1
        elif item.status == 'ativa':
            if cotacao_key not in row['_cotacoes_viavel']:
                row['_cotacoes_viavel'].add(cotacao_key)
                row['viavel'] += 1
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
        row.pop('_cotacoes_viavel', None)
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
            'viavel': item['viavel'],
            'aguardando_contratacao': item['aguardando_contratacao'],
            'contratado': item['contratado'],
            'declinado': item['declinado'],
            'inviavel': item['inviavel'],
        }[sort_by]),
        reverse=(direction == 'desc'),
    )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_relatorio_cotacao_endereco.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['endereco', 'cliente', 'total_cotacoes', 'em_negociacao', 'viavel', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'],
        ),
        'totais_por_status': totais_por_status,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_login_usuario(request):
    User = get_user_model()
    busca = (request.GET.get('busca') or '').strip()
    usuario_filtro = (request.GET.get('usuario') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'empresa', 'cotacao', 'cliente', 'login', 'usuario', 'ultimo_comentario', 'status'},
        'empresa',
    )
    proposal_content_type = ContentType.objects.get_for_model(Proposal)
    ultima_interacao_subquery = RegistroHistorico.objects.filter(
        content_type=proposal_content_type,
        object_id=OuterRef('pk'),
    ).order_by('-data').values('data')[:1]

    queryset = Proposal.objects.filter(status='analise').select_related(
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

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    rows = []
    for item in page_obj:
        rows.append({
            'pk': item.pk,
            'partner_nome': _proposal_partner_nome(item),
            'codigo_exibicao': item.codigo_exibicao,
            'nome_proposta': item.nome_proposta or 'Cotacao sem nome',
            'cliente_nome': _proposal_cliente_nome(item),
            'login_nome': _proposal_endereco_nome(item),
            'responsavel_nome': _proposal_responsavel_nome(item),
            'responsavel_id': item.responsavel_id or '',
            'ultima_interacao': item.ultima_interacao,
        })

    usuarios_disponiveis = User.objects.filter(
        is_active=True,
    ).exclude(
        username__iexact='admin',
    ).order_by('first_name', 'last_name', 'username')

    usuarios_filtro = User.objects.filter(
        is_active=True,
    ).order_by('first_name', 'last_name', 'username')

    return render(request, 'core/gestao_relatorio_login_usuario.html', {
        'page_obj': page_obj,
        'rows': rows,
        'busca': busca,
        'usuario_filtro': usuario_filtro,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca, 'usuario': usuario_filtro},
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'login', 'usuario', 'ultimo_comentario', 'status'],
        ),
        'total_resultados': total_resultados,
        'total_com_responsavel': total_com_responsavel,
        'total_sem_responsavel': total_sem_responsavel,
        'usuarios_disponiveis': usuarios_disponiveis,
        'usuarios_filtro': usuarios_filtro,
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_login_usuario_responsavel(request, pk):
    User = get_user_model()
    proposal = get_object_or_404(Proposal.objects.select_related('client_address', 'responsavel'), pk=pk)

    if request.method == 'POST':
        if proposal.status != 'analise':
            messages.error(request, "So e possivel trocar o responsavel quando a proposta estiver em Em Negociacao.")
            return redirect('gestao_relatorio_login_usuario')

        usuario_id = (request.POST.get('responsavel_id') or '').strip()
        if not usuario_id:
            messages.error(request, "Selecione um usuario para vincular ao login.")
            return redirect('gestao_relatorio_login_usuario')

        novo_responsavel = get_object_or_404(
            User.objects.filter(is_active=True).exclude(username__iexact='admin'),
            pk=usuario_id,
        )

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
                "Responsavel do login atualizado pela area de Gestao.\n\n"
                f"ID da proposta: #{proposal.codigo_exibicao}\n"
                f"Login: {proposal.client_address.login_ixc if proposal.client_address else '--'}\n"
                f"De: {nome_anterior}\n"
                f"Para: {nome_atual}"
            ),
            usuario=request.user,
            content_type=ContentType.objects.get_for_model(Proposal),
            object_id=proposal.id
        )
        messages.success(request, "Responsavel do login atualizado com sucesso.")

    return redirect('gestao_relatorio_login_usuario')


@user_passes_test(grupo_Operacao_required)
@login_required
def timeline_global(request, app_label, model_name, object_id):
    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    periodo = _resolver_periodo_historico(request)
    back_url, next_param = _resolver_back_url(request, '/')

    obj_class = content_type.model_class()
    obj = get_object_or_404(obj_class, pk=object_id)
    nome_objeto = getattr(obj, 'nome_fantasia', getattr(obj, 'razao_social', str(obj)))

    historico = RegistroHistorico.objects.filter(
        content_type=content_type,
        object_id=object_id,
        data__range=(periodo['inicio_dt'], periodo['fim_dt']),
    )

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        if descricao or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            RegistroHistorico.objects.create(
                tipo=tipo,
                acao=descricao,
                arquivo=arquivo,
                usuario=request.user,
                content_type=content_type,
                object_id=object_id,
            )
            messages.success(request, "Registro salvo com sucesso!")
            redirect_url = reverse('timeline_global', args=[app_label, model_name, object_id])
            if next_param:
                redirect_url = f"{redirect_url}?{urlencode({'next': next_param})}"
            return redirect(redirect_url)

    return render(request, 'core/timeline_global.html', {
        'back_url': back_url,
        'next_param': next_param,
        'content_type': content_type,
        'object_id': object_id,
        'historico': historico,
        'nome_objeto': nome_objeto,
        'modulo_origem': model_name.upper(),
        'data_inicio': periodo['data_inicio_str'],
        'data_fim': periodo['data_fim_str'],
        'filtro_personalizado': periodo['filtro_personalizado'],
    })
