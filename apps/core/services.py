"""Camada de servicos do app core: saude do sistema, portal de documentacao,
relatorios de gestao, logs de integracao e historico generico
(RegistroHistorico via GenericForeignKey).

Views ficam responsaveis apenas por HTTP: parametros da requisicao,
mensagens e renderizacao (PO-011, ADR-005).
"""
import os
import time as time_module
from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from .models import IntegrationAudit, RegistroHistorico

HEALTHCHECK_DB_TTL_SECONDS = 30
_HEALTHCHECK_CACHE = {
    'checked_at': 0.0,
    'db_ok': True,
    'error': '',
}

DOCS_DIAGRAMS_DIR = Path(settings.BASE_DIR) / 'docs' / 'diagrams'


def verificar_saude_sistema():
    """Retorna (db_ok, error_message); cacheia o resultado por HEALTHCHECK_DB_TTL_SECONDS
    para nao bater no banco a cada chamada do healthcheck."""
    now = time_module.monotonic()
    last_check = float(_HEALTHCHECK_CACHE.get('checked_at') or 0.0)

    if now - last_check < HEALTHCHECK_DB_TTL_SECONDS:
        return bool(_HEALTHCHECK_CACHE.get('db_ok')), str(_HEALTHCHECK_CACHE.get('error') or '')

    db_ok = True
    error_message = ''
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:
        db_ok = False
        error_message = str(exc)

    _HEALTHCHECK_CACHE.update({
        'checked_at': now,
        'db_ok': db_ok,
        'error': error_message,
    })
    return db_ok, error_message


def listar_documentos_diagramas():
    if not DOCS_DIAGRAMS_DIR.is_dir():
        return []

    documentos = []
    for caminho in sorted(DOCS_DIAGRAMS_DIR.glob('*.html')):
        titulo = caminho.stem.replace('-', ' ').replace('_', ' ').replace('.', ' ').strip().title()
        documentos.append({'nome_arquivo': caminho.name, 'titulo': titulo})
    return documentos


def obter_conteudo_documento_diagrama(nome_arquivo):
    """Valida o nome (sem path traversal, somente .html) e devolve o conteudo do
    documento em docs/diagrams/. Retorna None quando o nome e invalido ou o
    arquivo nao existe."""
    nome_seguro = os.path.basename(nome_arquivo)
    if nome_seguro != nome_arquivo or not nome_seguro.endswith('.html'):
        return None

    caminho = (DOCS_DIAGRAMS_DIR / nome_seguro).resolve()
    if DOCS_DIAGRAMS_DIR.resolve() not in caminho.parents or not caminho.is_file():
        return None

    return caminho.read_text(encoding='utf-8')


def montar_catalogo_relatorios_gestao(busca=''):
    catalogo = [
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

    busca = (busca or '').strip()
    if busca:
        catalogo = [item for item in catalogo if busca.lower() in item['nome'].lower()]

    return catalogo


def filtrar_logs_integracao(busca='', integracao='', acao='', usuario_id='', data_inicio='', data_fim=''):
    queryset = IntegrationAudit.objects.select_related('usuario').all()

    busca = (busca or '').strip()
    if busca:
        queryset = queryset.filter(
            Q(arquivo_nome__icontains=busca)
            | Q(usuario__username__icontains=busca)
            | Q(usuario__first_name__icontains=busca)
            | Q(usuario__last_name__icontains=busca)
        )

    integracao = (integracao or '').strip()
    if integracao:
        queryset = queryset.filter(integration=integracao)

    acao = (acao or '').strip()
    if acao:
        queryset = queryset.filter(action=acao)

    usuario_id = (usuario_id or '').strip()
    if usuario_id:
        queryset = queryset.filter(usuario_id=usuario_id)

    data_inicio = (data_inicio or '').strip()
    data_fim = (data_fim or '').strip()
    try:
        if data_inicio:
            queryset = queryset.filter(criado_em__date__gte=datetime.strptime(data_inicio, '%Y-%m-%d').date())
        if data_fim:
            queryset = queryset.filter(criado_em__date__lte=datetime.strptime(data_fim, '%Y-%m-%d').date())
    except ValueError:
        pass

    return queryset


def resolver_periodo_historico(data_inicio_str='', data_fim_str=''):
    agora = timezone.now()
    hoje = timezone.localdate(agora) if timezone.is_aware(agora) else agora.date()
    data_inicio = hoje
    data_fim = hoje

    data_inicio_str = (data_inicio_str or '').strip()
    data_fim_str = (data_fim_str or '').strip()

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


def listar_historico_periodo(content_type, object_id, inicio_dt, fim_dt):
    return RegistroHistorico.objects.filter(
        content_type=content_type,
        object_id=object_id,
        data__range=(inicio_dt, fim_dt),
    )


def registrar_historico_generico(content_type, object_id, usuario, descricao='', arquivo=None):
    """Cria um RegistroHistorico (comentario ou anexo) para qualquer entidade,
    via GenericForeignKey. Retorna None quando nao ha descricao nem arquivo
    (nada a registrar)."""
    if not (descricao or arquivo):
        return None

    tipo = 'anexo' if arquivo else 'comentario'
    return RegistroHistorico.objects.create(
        tipo=tipo,
        acao=descricao,
        arquivo=arquivo,
        usuario=usuario,
        content_type=content_type,
        object_id=object_id,
    )
