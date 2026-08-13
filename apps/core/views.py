import csv
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from urllib.parse import urlparse, urlencode

from . import services
from .models import IntegrationAudit

logger = logging.getLogger(__name__)


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


def _report_status_key(status):
    if status in {'analise', 'ativa'}:
        return 'analise'
    return status


def _report_status_display_from_key(status_key):
    labels = {
        'analise': 'Em negociação',
        'aguardando_contratacao': 'Aguardando contratação',
        'contratado': 'Contratado',
        'declinado': 'Declinado',
        'encerrada': 'Inviavel',
    }
    return labels.get(status_key, status_key or '-')


def _report_status_display(proposal):
    return _report_status_display_from_key(_report_status_key(getattr(proposal, 'status', '')))


def _report_status_choices():
    return [
        ('analise', 'Em negociação'),
        ('aguardando_contratacao', 'Aguardando contratação'),
        ('contratado', 'Contratado'),
        ('declinado', 'Declinado'),
        ('encerrada', 'Inviavel'),
    ]


def _report_totais_vazios():
    return {
        'analise': 0,
        'aguardando_contratacao': 0,
        'contratado': 0,
        'declinado': 0,
        'encerrada': 0,
    }


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('﻿')
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


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
    if user.is_superuser or user.is_gestor or user.groups.filter(name__in=['Administrador', 'Gestao', 'Gestão']).exists():
        return True
    raise PermissionDenied


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


def system_health(request):
    db_ok, error_message = services.verificar_saude_sistema()
    payload = {
        'ok': db_ok,
        'app': 'online',
        'db': 'online' if db_ok else 'offline',
        'checked_at': timezone.now().isoformat(),
    }
    if error_message:
        payload['error'] = error_message
    return JsonResponse(payload, status=200 if db_ok else 503)


def docs_index(request):
    return render(request, 'core/docs_index.html', {
        'documentos': services.listar_documentos_diagramas(),
    })


def docs_documento(request, nome_arquivo):
    conteudo = services.obter_conteudo_documento_diagrama(nome_arquivo)
    if conteudo is None:
        raise Http404("Documento nao encontrado.")

    return HttpResponse(conteudo, content_type='text/html; charset=utf-8')


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_home(request):
    return redirect('gestao_relatorios')


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorios(request):
    sort_by, direction = _resolve_sort(request, {'nome'}, 'nome')
    busca_relatorio = (request.GET.get('relatorio') or '').strip()
    relatorios_catalogo = services.montar_catalogo_relatorios_gestao(busca_relatorio)

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

    queryset = services.filtrar_logs_integracao(
        busca=busca,
        integracao=integracao,
        acao=acao,
        usuario_id=usuario_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

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


@user_passes_test(grupo_Operacao_required)
@login_required
def timeline_global(request, app_label, model_name, object_id):
    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    periodo = services.resolver_periodo_historico(
        request.GET.get('data_inicio'),
        request.GET.get('data_fim'),
    )
    back_url, next_param = _resolver_back_url(request, '/')

    obj_class = content_type.model_class()
    obj = get_object_or_404(obj_class, pk=object_id)
    nome_objeto = getattr(obj, 'nome_fantasia', getattr(obj, 'razao_social', str(obj)))

    historico = services.listar_historico_periodo(
        content_type, object_id, periodo['inicio_dt'], periodo['fim_dt'],
    )

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        registro = services.registrar_historico_generico(
            content_type, object_id, request.user, descricao=descricao, arquivo=arquivo,
        )
        if registro is not None:
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
