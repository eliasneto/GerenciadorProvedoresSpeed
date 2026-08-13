from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, time
from urllib.parse import urlparse, urlencode

from apps.core import services as core_services

# Importações do próprio app
from . import services
from .models import Partner, PartnerPlan, Proposal
from .forms import PartnerForm, PartnerPlanForm, ProposalForm
from apps.clientes.models import Endereco

# Utilitarios genericos de ordenacao/paginacao/CSV e checagem de grupo,
# reaproveitados do app core (camada 0) pelos relatorios de gestao abaixo.
from apps.core.views import (
    _build_sort_links,
    _csv_response,
    _report_status_choices,
    _resolve_sort,
    grupo_Gestao_required,
)

# Checagem de grupo "LastMile" (mesma trava do restante do menu Projeto).
# Reaproveitada de apps.leads.views, mesmo precedente ja usado em
# apps/core_admin/escola_email_views.py (RN-045/PO-069).
from apps.leads.views import grupo_LastMile_required

# 1. Cria a regra de verificação
def grupo_Parceiro_required(user):
    if not user.is_authenticated:
        return False
    # O superuser sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='Parceiro').exists() or user.is_superuser:
        return True
    # Se não for do grupo, gera erro 403 (acesso negado).
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

    if timezone.is_aware(timezone.now()):
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


def _resolver_back_url(request, fallback_url):
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


def _append_next(url, next_param):
    if not next_param:
        return url
    separador = '&' if '?' in url else '?'
    return f"{url}{separador}{urlencode({'next': next_param})}"

# ==============================================================================
# VIEWS DE PROVEDORES (menu Projeto, grupo LastMile - RN-045/PO-069)
# Tela independente da lista de Parceiros abaixo (grupo Parceiro): mesmo
# model Partner, sem edicao/exclusao, sem vinculo com Proposal/cotacao.
# ==============================================================================
@user_passes_test(grupo_LastMile_required)
@login_required
def provedores_list(request):
    """Lista em grid todos os Partner cadastrados (RN-045)."""
    provedores_queryset = Partner.objects.all().order_by('nome_fantasia', 'razao_social')

    paginator = Paginator(provedores_queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'partners/provedores_list.html', {
        'page_obj': page_obj,
        'total_provedores': provedores_queryset.count(),
    })


@user_passes_test(grupo_LastMile_required)
@login_required
def provedores_create(request):
    """Cadastra um novo Partner a partir da tela de Provedores (RN-045)."""
    if request.method == 'POST':
        form = PartnerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Provedor cadastrado com sucesso.")
            return redirect('provedores_list')
    else:
        form = PartnerForm()

    return render(request, 'partners/provedores_form.html', {'form': form})


@user_passes_test(grupo_LastMile_required)
@login_required
def provedores_edit(request, pk):
    """Edita um Partner existente a partir da tela de Provedores (RN-046)."""
    provedor = get_object_or_404(Partner, pk=pk)

    if request.method == 'POST':
        form = PartnerForm(request.POST, instance=provedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Provedor atualizado com sucesso.")
            return redirect('provedores_list')
    else:
        form = PartnerForm(instance=provedor)

    return render(request, 'partners/provedores_form.html', {'form': form, 'provedor': provedor})


# ==============================================================================
# VIEWS DE PARCEIROS (DADOS MESTRE E ESTEIRAS)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_list(request):
    """Lista apenas os parceiros ativos."""
    partners_queryset = services.listar_partners_convertidos()

    paginator = Paginator(partners_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    partner_ids = [partner.id for partner in page_obj.object_list]
    propostas_por_parceiro = services.agrupar_propostas_convertidas_por_parceiro(partner_ids)

    for partner in page_obj.object_list:
        propostas_partner = propostas_por_parceiro.get(partner.id, [])
        partner.total_propostas = len(propostas_partner)
        partner.propostas_param = f'propostas_page_{partner.id}'
        proposal_paginator = Paginator(propostas_partner, 10)
        proposal_page_number = request.GET.get(partner.propostas_param)
        partner.propostas_page_obj = proposal_paginator.get_page(proposal_page_number)
        partner.propostas_base = partner.propostas_page_obj.object_list
    
    return render(request, 'partners/partner_list.html', {
        'page_obj': page_obj,
        'total_partners': partners_queryset.count(),
        'expanded_partner_id': str(request.GET.get('expanded') or ''),
    })
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_inactive_list(request):
    """Esteira de reativação (win-back) para parceiros inativos."""
    partners_inativos = services.listar_partners_inativos()

    paginator = Paginator(partners_inativos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'partners/partner_inactive_list.html', {
        'page_obj': page_obj,
        'total_inativos': partners_inativos.count()
    })
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_detail(request, pk):
    """Exibe o perfil do parceiro, propostas e o histórico."""
    partner = get_object_or_404(Partner, pk=pk)
    back_url, next_param = _resolver_back_url(request, reverse('partner_list'))
    proposals, proposal_groups = services.agrupar_propostas_do_partner(partner)

    ver_antigos = request.GET.get('ver_antigos') == 'true'
    historico = services.listar_historico_partner(partner, incluir_arquivados=ver_antigos)
    qtd_antigo = services.contar_historico_arquivado_partner(partner)

    return render(request, 'partners/partner_detail.html', {
        'back_url': back_url,
        'next_param': next_param,
        'partner': partner,
        'proposals': proposals,
        'proposal_groups': proposal_groups,
        'historico': historico,
        'qtd_antigo': qtd_antigo,
        'mostrando_antigos': ver_antigos,
    })


@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_plan_manage(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    back_url, next_param = _resolver_back_url(request, reverse('lead_list'))
    form = PartnerPlanForm()
    planos = services.listar_planos_partner(partner)

    return render(request, 'partners/partner_plan_manage.html', {
        'partner': partner,
        'form': form,
        'planos': planos,
        'back_url': back_url,
        'next_param': next_param,
    })


@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_plan_add(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('lead_list'))

    if request.method == 'POST':
        form = PartnerPlanForm(request.POST)
        if form.is_valid():
            plano = form.save(commit=False)
            plano.partner = partner
            plano.save()
            messages.success(request, "Plano cadastrado com sucesso.")
        else:
            messages.error(request, "N\xe3o foi poss\xedvel salvar o plano. Revise os campos informados.")

    return redirect(_append_next(reverse('partner_plan_manage', args=[partner.pk]), next_param))


@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_plan_delete(request, partner_pk, plan_pk):
    partner = get_object_or_404(Partner, pk=partner_pk)
    _, next_param = _resolver_back_url(request, reverse('lead_list'))

    if request.method == 'POST':
        plano = get_object_or_404(PartnerPlan, pk=plan_pk, partner=partner)
        plano.delete()
        messages.success(request, "Plano removido com sucesso.")

    return redirect(_append_next(reverse('partner_plan_manage', args=[partner.pk]), next_param))
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_add_historico(request, pk):
    """Recebe o POST do comentário/anexo na tela do parceiro."""
    partner = get_object_or_404(Partner, pk=pk)

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        registro = core_services.registrar_historico_generico(
            ContentType.objects.get_for_model(Partner), partner.id, request.user,
            descricao=descricao, arquivo=arquivo,
        )
        if registro is not None:
            messages.success(request, "Anotação salva no histórico do parceiro!")

    return redirect('partner_detail', pk=pk)

# ==============================================================================
# MUDANÇAS DE STATUS (MODAIS)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def update_partner_status(request, pk):
    """Inativa o parceiro a partir da lista de Ativos."""
    if request.method == 'POST':
        partner = get_object_or_404(Partner, pk=pk)
        novo_status = request.POST.get('status')
        observacao = request.POST.get('observacao')
        arquivo = request.FILES.get('arquivo')

        estado, mensagem = services.aplicar_transicao_status_partner(
            partner, novo_status, request.user, observacao=observacao, arquivo=arquivo,
        )
        if estado == 'bloqueado':
            messages.error(request, mensagem)
        elif estado == 'aplicado':
            messages.success(request, mensagem)

    return redirect('partner_list')
@user_passes_test(grupo_Parceiro_required)
@login_required
def update_winback_status(request, pk):
    """Avança o estágio na esteira de reativação (win-back)."""
    if request.method == 'POST':
        partner = get_object_or_404(Partner, pk=pk)
        novo_status = request.POST.get('status')
        observacao = request.POST.get('observacao')

        estado, mensagem = services.aplicar_reativacao_winback(
            partner, novo_status, request.user, observacao=observacao,
        )
        if estado == 'reativado':
            messages.success(request, mensagem)
            return redirect('partner_detail', pk=partner.pk)
        elif estado == 'atualizado':
            messages.info(request, mensagem)

    return redirect('partner_inactive_list')

# ==============================================================================
# VIEWS DE PROPOSTAS / ORDEM DE SERVIÇO
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_create(request, partner_pk):
    partner = get_object_or_404(Partner, pk=partner_pk)
    endereco_id = request.GET.get('endereco')
    endereco_obj = get_object_or_404(Endereco, pk=endereco_id) if endereco_id else None

    proposal = services.criar_proposal(partner, request.user, endereco=endereco_obj)

    messages.success(request, f"Nova OS iniciada para {partner.nome_fantasia or partner.razao_social}")
    return redirect('proposal_update', pk=proposal.pk)

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('partner', 'cliente', 'client_address', 'responsavel'), pk=pk)
    back_url, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))
    periodo = _resolver_periodo_historico(request)
    historico = core_services.listar_historico_periodo(
        ContentType.objects.get_for_model(Proposal), proposal.id, periodo['inicio_dt'], periodo['fim_dt'],
    )

    return render(request, 'partners/proposal_detail.html', {
        'back_url': back_url,
        'next_param': next_param,
        'proposal': proposal,
        'partner': proposal.partner,
        'historico': historico,
        'data_inicio': periodo['data_inicio_str'],
        'data_fim': periodo['data_fim_str'],
        'filtro_personalizado': periodo['filtro_personalizado'],
    })


@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_assumir_responsavel(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('partner', 'client_address'), pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        estado, mensagem = services.assumir_responsavel_login(proposal, request.user)
        if estado == 'bloqueado':
            messages.error(request, mensagem)
        elif estado == 'ja_responsavel':
            messages.info(request, mensagem)
        else:
            messages.success(request, mensagem)

    return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))


@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('partner', 'cliente', 'client_address'), pk=pk)
    partner = proposal.partner
    back_url, next_param = _resolver_back_url(request, reverse('partner_detail', args=[partner.id]))
    periodo = _resolver_periodo_historico(request)

    contexto_lote = services.montar_contexto_lote(proposal, periodo['inicio_dt'], periodo['fim_dt'])

    return render(request, 'partners/proposal_batch_detail.html', {
        'back_url': back_url,
        'next_param': next_param,
        'proposal': proposal,
        'partner': partner,
        **contexto_lote,
        'proposal_status_choices': [
            choice for choice in Proposal.STATUS_CHOICES
            if choice[0] in ['analise', 'ativa', 'encerrada']
        ],
        'data_inicio': periodo['data_inicio_str'],
        'data_fim': periodo['data_fim_str'],
        'filtro_personalizado': periodo['filtro_personalizado'],
    })


@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_logins(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    proposals_lote = services.listar_propostas_do_lote(proposal)
    return render(request, 'partners/_proposal_batch_logins_list.html', {
        'proposals_lote': proposals_lote,
    })

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_add_historico(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        if services.replicar_historico_lote(proposal, request.user, descricao=descricao, arquivo=arquivo):
            messages.success(request, "Registro adicionado ao lote e replicado para todas as propostas vinculadas.")

    return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_status_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        resultado = services.aplicar_atualizacao_lote_status(
            request, proposal,
            novo_status=request.POST.get('status'),
            observacao_inviavel=(request.POST.get('observacao_inviavel') or '').strip(),
            observacao_contratacao=(request.POST.get('observacao_contratacao') or '').strip(),
            alterar_os_ixc=(request.POST.get('alterar_os_ixc') or 'nao').strip().lower() == 'sim',
            fechar_outras_cotacoes=(request.POST.get('fechar_outras_cotacoes') or 'nao').strip().lower(),
            arquivo_ixc=request.FILES.get('arquivo_ixc'),
            motivo_id=request.POST.get('motivo_inviavel'),
        )
        for nivel, texto in resultado['mensagens']:
            getattr(messages, nivel)(request, texto)
        return redirect(_append_next(resultado['redirect_url'], next_param))

    return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_add_historico(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        registro = core_services.registrar_historico_generico(
            ContentType.objects.get_for_model(Proposal), proposal.id, request.user,
            descricao=descricao, arquivo=arquivo,
        )
        if registro is not None:
            messages.success(request, "Registro adicionado ao histórico da cotação.")

    return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))


def _contexto_proposal_form(form, proposal, partner, is_conversion_completion, status_pendente, propostas_lote, possui_os_lastmile, fechar_outras_cotacoes, outras_cotacoes_abertas, outras_cotacoes_por_endereco, permite_alterar_os_ixc):
    return {
        'form': form,
        'proposal': proposal,
        'partner': partner,
        'is_conversion_completion': is_conversion_completion,
        'status_exibicao_conversao': dict(Proposal.STATUS_CHOICES).get(status_pendente, proposal.get_status_display()),
        'propostas_lote': propostas_lote,
        'possui_os_lastmile': possui_os_lastmile,
        'fechar_outras_cotacoes': fechar_outras_cotacoes,
        'outras_cotacoes_abertas_qtd': len(outras_cotacoes_abertas),
        'outras_cotacoes_por_endereco': outras_cotacoes_por_endereco,
        'permite_alterar_os_ixc': permite_alterar_os_ixc,
    }


@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner
    endereco_atual = proposal.client_address
    is_conversion_completion = request.GET.get('modo') == 'convertida' or request.POST.get('modo') == 'convertida'
    status_pendente = request.GET.get('status_pendente') or request.POST.get('status_pendente')
    fechar_outras_cotacoes = (request.GET.get('fechar_outras_cotacoes') or request.POST.get('fechar_outras_cotacoes') or 'nao').strip().lower()
    propostas_lote = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta).select_related('cliente', 'client_address').order_by('id')
    ) if proposal.codigo_proposta else [proposal]
    possui_os_lastmile = bool(services._propostas_com_os_lastmile(propostas_lote))
    outras_cotacoes_abertas = services._outras_cotacoes_em_negociacao_mesmo_endereco(propostas_lote) if is_conversion_completion else []
    outras_cotacoes_por_endereco = services._montar_resumo_outras_cotacoes_por_endereco(outras_cotacoes_abertas)
    permite_alterar_os_ixc = bool(possui_os_lastmile and not (outras_cotacoes_abertas and fechar_outras_cotacoes != 'sim'))

    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal, lock_relationship_fields=is_conversion_completion)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')
        arquivo_ixc = request.FILES.get('arquivo_ixc')

        if form.is_valid():
            if is_conversion_completion:
                resultado = services.processar_conversao_viavel(
                    request, proposal, partner, form,
                    propostas_lote=propostas_lote,
                    outras_cotacoes_abertas=outras_cotacoes_abertas,
                    fechar_outras_cotacoes=fechar_outras_cotacoes,
                    arquivo_ixc=arquivo_ixc,
                )
                if not resultado['ok']:
                    messages.error(request, resultado['erro'])
                    return render(request, 'partners/proposal_form.html', _contexto_proposal_form(
                        form, proposal, partner, is_conversion_completion, status_pendente, propostas_lote,
                        possui_os_lastmile, fechar_outras_cotacoes, outras_cotacoes_abertas,
                        outras_cotacoes_por_endereco, permite_alterar_os_ixc,
                    ))

                for mensagem_info in resultado['mensagens_info']:
                    messages.info(request, mensagem_info)
                messages.success(request, resultado['mensagem_sucesso'])
                return redirect('partner_list')

            services.processar_edicao_proposta(request, proposal, partner, form, endereco_atual, enderecos_ids)
            messages.success(request, "Sucesso! Atualizações salvas para a Speed.")
            return redirect('partner_detail', pk=partner.pk)
    else:
        form = ProposalForm(instance=proposal, lock_relationship_fields=is_conversion_completion)

    return render(request, 'partners/proposal_form.html', _contexto_proposal_form(
        form, proposal, partner, is_conversion_completion, status_pendente, propostas_lote,
        possui_os_lastmile, fechar_outras_cotacoes, outras_cotacoes_abertas,
        outras_cotacoes_por_endereco, permite_alterar_os_ixc,
    ))

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_status_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner

    if request.method == 'POST':
        estado, _ = services.atualizar_status_proposal_individual(request, proposal)
        if estado == 'invalido':
            messages.error(request, "Status de cotação inválido.")
        elif estado == 'ativa':
            messages.success(request, "Cotação marcada como viável. Complete agora os dados técnicos e financeiros.")
            return redirect(f"{reverse('proposal_update', args=[proposal.pk])}?modo=convertida&status_pendente=ativa")
        elif estado == 'atualizado':
            messages.success(request, "Status da cotação atualizado com sucesso.")

    return redirect('partner_detail', pk=partner.pk)

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_delete(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner_pk = proposal.partner.pk
    proposal.delete()
    messages.warning(request, "Cotação removida do sistema.")
    return redirect('partner_detail', pk=partner_pk)

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_global_list(request):
    proposals, total_receita = services.listar_propostas_globais()
    return render(request, 'partners/proposal_global_list.html', {'proposals': proposals, 'total_receita': total_receita})

# ==============================================================================
# VIEWS DE RASTREABILIDADE (UNIDADES E CLIENTES)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def address_proposals_list(request, address_id):
    endereco = get_object_or_404(Endereco, pk=address_id)
    proposals = services.listar_propostas_do_endereco(endereco)
    partners = Partner.objects.all().order_by('nome_fantasia')
    return render(request, 'partners/address_proposals_list.html', {'endereco': endereco, 'proposals': proposals, 'partners': partners})

@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_clients_list(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    proposals, clientes_agrupados = services.listar_clientes_do_partner(partner)

    return render(request, 'partners/partner_clients_list.html', {
        'partner': partner, 'clientes_agrupados': clientes_agrupados, 'total_links': proposals.count()
    })


# ==============================================================================
# RELATORIOS DE GESTAO (movidos de apps.core.views na PO-032 - liam ao dono do
# dado: Proposal e do app partners, nao de core)
# ==============================================================================

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

    rows, totais_por_status, status_filtrado = services.montar_relatorio_login_status(
        busca=busca, status=status, cliente=cliente_param, endereco=endereco_param,
        sort_by=sort_by, direction=direction,
    )

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'relatorio_login_status.csv',
            ['Parceiro', 'Cotação', 'Cliente', 'Login', 'Status', 'Responsável', 'Última interação'],
            [
                [
                    item['partner_nome'],
                    item['codigo_exibicao'],
                    item['cliente_nome'],
                    item['login_nome'],
                    item['status_display'],
                    item['responsavel_nome'],
                    item['ultima_interacao'].strftime('%d/%m/%Y %H:%M') if item['ultima_interacao'] else '-',
                ]
                for item in rows
            ],
        )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/gestao_relatorio_proposta_status.html', {
        'page_obj': page_obj,
        'rows': rows,
        'busca': busca,
        'cliente_param': cliente_param,
        'endereco_param': endereco_param,
        'status_filtro': status_filtrado,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {
                'busca': busca,
                'status': status_filtrado,
                'cliente': cliente_param,
                'endereco': endereco_param,
            },
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'login', 'status', 'responsavel', 'ultima_interacao'],
        ),
        'totais_por_status': totais_por_status,
        'status_choices': _report_status_choices(),
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'status': status_filtrado,
                'cliente': cliente_param,
                'endereco': endereco_param,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
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

    proposals_rows, totais_por_status, status_filtrado = services.montar_relatorio_proposta_status(
        busca=busca, status=status, sort_by=sort_by, direction=direction,
    )

    paginator = Paginator(proposals_rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'relatorio_status_cotacao.csv',
            ['Parceiro', 'Cotação', 'Cliente', 'Qtd logins', 'Status'],
            [
                [
                    item['partner_nome'],
                    item['codigo_exibicao'],
                    item['cliente_nome'],
                    item['total_logins'],
                    item['status_display'],
                ]
                for item in proposals_rows
            ],
        )

    return render(request, 'core/gestao_relatorio_proposta_status_real.html', {
        'page_obj': page_obj,
        'busca': busca,
        'status_filtro': status_filtrado,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca, 'status': status_filtrado},
            sort_by,
            direction,
            ['empresa', 'cotacao', 'cliente', 'qtd_logins', 'status'],
        ),
        'totais_por_status': totais_por_status,
        'status_choices': _report_status_choices(),
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'status': status_filtrado,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_status_cliente(request):
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'cliente', 'total_cotacoes', 'em_negociacao', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'},
        'cliente',
    )

    rows, totais_por_status = services.montar_relatorio_status_cliente(
        busca=busca, sort_by=sort_by, direction=direction,
    )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'relatorio_status_cliente.csv',
            ['Cliente', 'Total cotações', 'Em negociação', 'Aguardando contratação', 'Contratado', 'Declinado', 'Inviável'],
            [
                [
                    item['cliente_nome'],
                    item['total_cotacoes'],
                    item['em_negociacao'],
                    item['aguardando_contratacao'],
                    item['contratado'],
                    item['declinado'],
                    item['inviavel'],
                ]
                for item in rows
            ],
        )

    return render(request, 'core/gestao_relatorio_status_cliente.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['cliente', 'total_cotacoes', 'em_negociacao', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'],
        ),
        'totais_por_status': totais_por_status,
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_cotacao_endereco(request):
    busca = (request.GET.get('busca') or '').strip()
    sort_by, direction = _resolve_sort(
        request,
        {'endereco', 'cliente', 'total_cotacoes', 'em_negociacao', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'},
        'endereco',
    )

    rows, totais_por_status = services.montar_relatorio_cotacao_endereco(
        busca=busca, sort_by=sort_by, direction=direction,
    )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'relatorio_cotacao_endereco.csv',
            ['Endereço', 'Complemento', 'Cliente', 'Total cotações', 'Em negociação', 'Aguardando contratação', 'Contratado', 'Declinado', 'Inviável'],
            [
                [
                    item['endereco_nome'],
                    item['endereco_complemento'],
                    item['cliente_nome'],
                    item['total_cotacoes'],
                    item['em_negociacao'],
                    item['aguardando_contratacao'],
                    item['contratado'],
                    item['declinado'],
                    item['inviavel'],
                ]
                for item in rows
            ],
        )

    return render(request, 'core/gestao_relatorio_cotacao_endereco.html', {
        'page_obj': page_obj,
        'busca': busca,
        'sort_by': sort_by,
        'direction': direction,
        'sort_links': _build_sort_links(
            {'busca': busca},
            sort_by,
            direction,
            ['endereco', 'cliente', 'total_cotacoes', 'em_negociacao', 'aguardando_contratacao', 'contratado', 'declinado', 'inviavel'],
        ),
        'totais_por_status': totais_por_status,
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
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

    rows, total_resultados, total_com_responsavel, total_sem_responsavel = services.montar_relatorio_login_usuario(
        busca=busca, usuario_filtro=usuario_filtro, sort_by=sort_by, direction=direction,
    )

    if request.GET.get('export') == 'csv':
        return _csv_response(
            'relatorio_login_usuario.csv',
            ['Parceiro', 'Cotação', 'Cliente', 'Endereço', 'Usuário', 'Último comentário', 'Status'],
            [
                [
                    item['partner_nome'],
                    item['codigo_exibicao'],
                    item['cliente_nome'],
                    item['login_nome'],
                    item['responsavel_nome'],
                    item['ultima_interacao'].strftime('%d/%m/%Y %H:%M') if item['ultima_interacao'] else '-',
                    'Vinculado' if item['responsavel_nome'] != '-' else 'Sem responsável',
                ]
                for item in rows
            ],
        )

    paginator = Paginator(rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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
        'csv_query': urlencode({
            **{k: v for k, v in {
                'busca': busca,
                'usuario': usuario_filtro,
                'sort': sort_by,
                'direction': direction,
            }.items() if v not in ('', None)},
            'export': 'csv',
        }),
    })


@user_passes_test(grupo_Gestao_required)
@login_required
def gestao_relatorio_login_usuario_responsavel(request, pk):
    User = get_user_model()
    proposal = get_object_or_404(Proposal.objects.select_related('client_address', 'responsavel'), pk=pk)

    if request.method == 'POST':
        erro = services.validar_transicao_responsavel_login(proposal)
        if erro:
            messages.error(request, erro)
            return redirect('gestao_relatorio_login_usuario')

        usuario_id = (request.POST.get('responsavel_id') or '').strip()
        if not usuario_id:
            messages.error(request, "Selecione um usuario para vincular ao login.")
            return redirect('gestao_relatorio_login_usuario')

        novo_responsavel = get_object_or_404(
            User.objects.filter(is_active=True).exclude(username__iexact='admin'),
            pk=usuario_id,
        )

        services.atualizar_responsavel_login(proposal, novo_responsavel, request.user)
        messages.success(request, "Responsável do login atualizado com sucesso.")

    return redirect('gestao_relatorio_login_usuario')

