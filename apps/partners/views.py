from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, time
from urllib.parse import urlparse, urlencode

# Importações do próprio App
from .models import Partner, Proposal, ProposalMotivoInviavel
from .forms import PartnerForm, ProposalForm
from clientes.models import Endereco 

# --- IMPORTAÇÃO DO HISTÓRICO SPEED ---
from core.models import RegistroHistorico

# 1. Cria a regra de verificação
def grupo_Parceiro_required(user):
    if not user.is_authenticated:
        return False
    # O Superuser (você) sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='Parceiro').exists() or user.is_superuser:
        return True
    # Se não for do grupo, joga um Erro 403 (Acesso Negado)
    raise PermissionDenied


def _registrar_historico_proposta(proposal, usuario, acao, tipo='sistema', arquivo=None):
    RegistroHistorico.objects.create(
        tipo=tipo,
        acao=acao,
        arquivo=arquivo,
        usuario=usuario,
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id=proposal.id
    )


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
# VIEWS DE PARCEIROS (DADOS MESTRE E ESTEIRAS)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_list(request):
    """Lista APENAS os parceiros ATIVOS (A operação real)."""
    proposal_statuses_partner_list = ['aguardando_contratacao', 'contratado', 'declinado']
    partners_queryset = (
        Partner.objects.filter(proposals__status__in=proposal_statuses_partner_list)
        .distinct()
        .order_by('-id')
    )
    
    paginator = Paginator(partners_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    partner_ids = [partner.id for partner in page_obj.object_list]
    propostas_convertidas = (
        Proposal.objects.filter(partner_id__in=partner_ids, status__in=proposal_statuses_partner_list)
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
    """Esteira de Reativação (Win-back) para parceiros inativos."""
    # Traz todo mundo que NÃO está ativo (inativo, negociacao, inviavel)
    partners_inativos = Partner.objects.exclude(status__in=['ativo', 'aguardando_contratacao', 'contratado']).order_by('-data_cadastro')
    
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
    """Exibe o perfil do parceiro, propostas e o HISTÓRICO (Timeline)."""
    partner = get_object_or_404(Partner, pk=pk)
    back_url, next_param = _resolver_back_url(request, reverse('partner_list'))
    proposals = partner.proposals.exclude(status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']).order_by('-id')
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
    
    partner_type = ContentType.objects.get_for_model(Partner)
    
    # MÁGICA SPEED: Leitura de Histórico "Ativo" x "Arquivado"
    ver_antigos = request.GET.get('ver_antigos') == 'true'
    
    if ver_antigos:
        # Traz tudo, ordenado do mais novo pro mais velho
        historico = RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id).order_by('-id')
    else:
        # Traz só os do ciclo atual
        historico = RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id, arquivado=False).order_by('-id')
        
    # Conta quantos são antigos para exibir o botão
    qtd_antigo = RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id, arquivado=True).count()
    
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
def partner_add_historico(request, pk):
    """Mini-view que recebe o POST do comentário/anexo na tela do Parceiro"""
    partner = get_object_or_404(Partner, pk=pk)
    
    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')
        
        if descricao or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            RegistroHistorico.objects.create(
                tipo=tipo,
                acao=descricao,         # CORRIGIDO
                arquivo=arquivo,
                usuario=request.user,   # CORRIGIDO
                content_type=ContentType.objects.get_for_model(Partner),
                object_id=partner.id
            )
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
        
        if partner.status == 'aguardando_contratacao' and novo_status not in ['contratado', 'declinado']:
            messages.error(request, "Parceiros em aguardando contratação só podem avançar para Contratado ou Declinado.")
            return redirect('partner_list')

        if novo_status in ['ativo', 'aguardando_contratacao', 'contratado', 'declinado', 'inativo']:
            status_antigo = partner.status
            partner.status = novo_status
            partner.save()
            
            if status_antigo != novo_status:
                if novo_status == 'inativo':
                    tipo_hist = 'anexo' if arquivo else 'sistema'
                    texto_historico = f"🚫 PARCEIRO INATIVADO\n\nMotivo / Observação:\n{observacao}" if observacao else "🚫 PARCEIRO INATIVADO"
                elif novo_status == 'declinado':
                    tipo_hist = 'anexo' if arquivo else 'sistema'
                    texto_historico = f"❌ PARCEIRO DECLINADO\n\nMotivo / Observação:\n{observacao}" if observacao else "❌ PARCEIRO DECLINADO"
                elif novo_status == 'contratado':
                    tipo_hist = 'sistema'
                    texto_historico = "✅ PARCEIRO CONTRATADO\n\nStatus operacional alterado para [CONTRATADO]."
                elif novo_status == 'aguardando_contratacao':
                    tipo_hist = 'sistema'
                    texto_historico = "📝 PARCEIRO EM AGUARDANDO CONTRATAÇÃO\n\nA proposta viável foi encaminhada para negociação contratual."
                else:
                    tipo_hist = 'sistema'
                    texto_historico = f"✅ PARCEIRO REATIVADO\n\nStatus operacional alterado para [ATIVO]."

                RegistroHistorico.objects.create(
                    tipo=tipo_hist, 
                    acao=texto_historico,   # CORRIGIDO
                    arquivo=arquivo,
                    usuario=request.user,   # CORRIGIDO
                    content_type=ContentType.objects.get_for_model(Partner), 
                    object_id=partner.id
                )
            messages.success(request, f"O status da {partner.nome_fantasia or partner.razao_social} foi atualizado para {novo_status.upper()}.")
            
    return redirect('partner_list')
@user_passes_test(grupo_Parceiro_required)
@login_required
def update_winback_status(request, pk):
    """Avança o estágio na esteira de reativação (Win-back)."""
    if request.method == 'POST':
        partner = get_object_or_404(Partner, pk=pk)
        novo_status = request.POST.get('status')
        observacao = request.POST.get('observacao')

        if novo_status == 'andamento':
            from core.models import RegistroHistorico
            from django.contrib.contenttypes.models import ContentType
            tipo_parceiro = ContentType.objects.get_for_model(Partner)

            # 1. FORÇA BRUTA NO ARQUIVAMENTO (Salva um por um para não falhar)
            historicos_antigos = RegistroHistorico.objects.filter(content_type=tipo_parceiro, object_id=partner.id)
            for hist in historicos_antigos:
                hist.arquivado = True
                hist.save()

            # 2. FORÇA BRUTA NA LIMPEZA (Deleta OS uma por uma)
            for prop in partner.proposals.all():
                prop.delete()

            # 3. REATIVA O PARCEIRO
            partner.status = 'ativo'
            partner.save()
            
            # 4. GERA O LOG INICIAL DO NOVO CICLO (Blindado e Corrigido)
            RegistroHistorico.objects.create(
                tipo='sistema',
                acao="🎉 NOVO CICLO DE PARCERIA!\nO parceiro foi reativado na esteira Win-back. O histórico antigo foi arquivado e o perfil foi limpo para a inclusão de novas OS.", # CORRIGIDO
                usuario=request.user, # CORRIGIDO
                content_type=tipo_parceiro,
                object_id=partner.id,
                arquivado=False
            )
            
            messages.success(request, f"Show! {partner.nome_fantasia or partner.razao_social} reativado e histórico arquivado com sucesso!")
            return redirect('partner_detail', pk=partner.pk)

        elif novo_status in ['negociacao', 'inviavel']:
            partner.status = novo_status
            partner.save()
            
            texto = "🤝 Negociação de reativação iniciada." if novo_status == 'negociacao' else f"❌ Tentativa de reativação recusada/inviável.\nMotivo: {observacao}"
            
            RegistroHistorico.objects.create(
                tipo='sistema', 
                acao=texto,             # CORRIGIDO
                usuario=request.user,   # CORRIGIDO
                content_type=ContentType.objects.get_for_model(Partner), 
                object_id=partner.id, 
                arquivado=False
            )
            messages.info(request, f"Estágio atualizado para: {partner.get_status_display()}")
            
    return redirect('partner_inactive_list')

# ==============================================================================
# VIEWS DE PROPOSTAS / ORDEM DE SERVIÇO
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_create(request, partner_pk):
    partner = get_object_or_404(Partner, pk=partner_pk)
    proposal = Proposal(partner=partner)
    
    endereco_id = request.GET.get('endereco')
    if endereco_id:
        endereco_obj = get_object_or_404(Endereco, pk=endereco_id)
        proposal.client_address = endereco_obj
        proposal.cliente = endereco_obj.cliente
        
    proposal.save()
    if not proposal.grupo_proposta_id:
        proposal.grupo_proposta_id = proposal.id
    if not proposal.codigo_proposta:
        proposal.codigo_proposta = Proposal.montar_codigo_proposta(proposal.grupo_proposta_id or proposal.id)
    proposal.save(update_fields=['grupo_proposta_id', 'codigo_proposta'])
    _registrar_historico_proposta(
        proposal,
        request.user,
        (
            "Proposta iniciada.\n\n"
            f"ID da proposta: #{proposal.codigo_exibicao}\n"
            f"Cliente: {proposal.cliente or '--'}\n"
            f"Unidade: {proposal.client_address or '--'}"
        ),
    )
    messages.success(request, f"Nova OS iniciada para {partner.nome_fantasia or partner.razao_social}")
    return redirect('proposal_update', pk=proposal.pk)

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('partner', 'cliente', 'client_address', 'responsavel'), pk=pk)
    back_url, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))
    periodo = _resolver_periodo_historico(request)
    historico = RegistroHistorico.objects.filter(
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id=proposal.id,
        data__range=(periodo['inicio_dt'], periodo['fim_dt']),
    ).order_by('-data')

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
        if proposal.status != 'analise':
            messages.error(request, "Só é possível assumir um login quando a proposta estiver em Em Negociação.")
            return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))

        responsavel_anterior = proposal.responsavel
        if responsavel_anterior_id := getattr(responsavel_anterior, 'id', None):
            if responsavel_anterior_id == request.user.id:
                messages.info(request, "Esse login já está com você como responsável.")
                return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))

        proposal.responsavel = request.user
        proposal.save(update_fields=['responsavel'])

        nome_anterior = responsavel_anterior.get_full_name() or responsavel_anterior.username if responsavel_anterior else '--'
        nome_atual = request.user.get_full_name() or request.user.username
        _registrar_historico_proposta(
            proposal,
            request.user,
            (
                "Responsável do login atualizado.\n\n"
                f"ID da proposta: #{proposal.codigo_exibicao}\n"
                f"Login: {proposal.client_address.login_ixc if proposal.client_address else '--'}\n"
                f"De: {nome_anterior}\n"
                f"Para: {nome_atual}"
            ),
        )
        messages.success(request, "Esse login foi atribuído ao seu usuário.")

    return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))


@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_detail(request, pk):
    proposal = get_object_or_404(Proposal.objects.select_related('partner', 'cliente', 'client_address'), pk=pk)
    partner = proposal.partner
    back_url, next_param = _resolver_back_url(request, reverse('partner_detail', args=[partner.id]))
    periodo = _resolver_periodo_historico(request)

    proposal_ids = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta)
        .order_by('id')
        .values_list('id', flat=True)
    )
    total_logins_lote = len(proposal_ids)

    historico_qs = RegistroHistorico.objects.filter(
        content_type=ContentType.objects.get_for_model(Proposal),
        object_id__in=proposal_ids,
        data__range=(periodo['inicio_dt'], periodo['fim_dt']),
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

    motivos_inviavel_ativos = ProposalMotivoInviavel.objects.filter(status='ativo').order_by('nome')

    return render(request, 'partners/proposal_batch_detail.html', {
        'back_url': back_url,
        'next_param': next_param,
        'proposal': proposal,
        'partner': partner,
        'total_logins_lote': total_logins_lote,
        'historico_lote': historico_lote,
        'motivos_inviavel_ativos': motivos_inviavel_ativos,
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
    proposals_lote = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta)
        .select_related('client_address')
        .order_by('id')
    )
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

        if descricao or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            acao = descricao or "Anexo registrado no lote da proposta."

            for item in Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta).order_by('id'):
                _registrar_historico_proposta(
                    item,
                    request.user,
                    acao,
                    tipo=tipo,
                    arquivo=arquivo,
                )

            messages.success(request, "Registro adicionado ao lote e replicado para todas as propostas vinculadas.")

    return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_batch_status_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        novo_status = request.POST.get('status')
        status_validos = {choice[0] for choice in Proposal.STATUS_CHOICES}

        if novo_status not in status_validos:
            messages.error(request, "Status de cotação inválido.")
            return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

        propostas_lote = list(Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta).select_related('cliente'))
        status_antigo = proposal.status
        motivo_inviavel = None
        observacao_inviavel = (request.POST.get('observacao_inviavel') or '').strip()

        if novo_status == 'encerrada':
            motivo_id = request.POST.get('motivo_inviavel')
            motivo_inviavel = ProposalMotivoInviavel.objects.filter(pk=motivo_id, status='ativo').first()
            if not motivo_inviavel:
                messages.error(request, "Selecione um motivo ativo para marcar a cotação como inviável.")
                return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))
            if not observacao_inviavel:
                messages.error(request, "Preencha a observação da cotação inviável.")
                return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))
            if len(observacao_inviavel) > 150:
                messages.error(request, "A observação da cotação inviável deve ter no máximo 150 caracteres.")
                return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

        if status_antigo != novo_status:
            for item in propostas_lote:
                item.status = novo_status
                if novo_status == 'encerrada':
                    item.motivo_inviavel = motivo_inviavel
                    item.observacao_inviavel = observacao_inviavel
                    item.save(update_fields=['status', 'motivo_inviavel', 'observacao_inviavel'])
                else:
                    item.motivo_inviavel = None
                    item.observacao_inviavel = None
                    item.save(update_fields=['status', 'motivo_inviavel', 'observacao_inviavel'])

                detalhe_item_inviavel = ""
                if novo_status == 'encerrada':
                    detalhe_item_inviavel = f"\nMotivo: {motivo_inviavel.nome}\nObservação: {observacao_inviavel}"

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
                    ),
                )

            detalhe_lote_inviavel = ""
            if novo_status == 'encerrada':
                detalhe_lote_inviavel = f"Motivo: {motivo_inviavel.nome}\nObservação: {observacao_inviavel}\n"

            RegistroHistorico.objects.create(
                tipo='sistema',
                acao=(
                    "Status do lote da proposta atualizado.\n\n"
                    f"ID da proposta: #{proposal.codigo_exibicao}\n"
                    f"De: {dict(Proposal.STATUS_CHOICES).get(status_antigo, status_antigo)}\n"
                    f"Para: {dict(Proposal.STATUS_CHOICES).get(novo_status, novo_status)}\n"
                    f"{detalhe_lote_inviavel}"
                    f"Quantidade de logins impactados: {len(propostas_lote)}"
                ),
                usuario=request.user,
                content_type=ContentType.objects.get_for_model(Partner),
                object_id=proposal.partner_id
            )
            if novo_status == 'ativa':
                messages.success(request, "Cotação marcada como viável. Complete agora os dados técnicos e financeiros.")
                return redirect(_append_next(f"{reverse('proposal_update', args=[proposal.pk])}?modo=convertida", next_param))

            if novo_status in ['contratado', 'declinado']:
                messages.success(request, "Status da cotação atualizado no lote com sucesso.")
                return redirect(_append_next(reverse('partner_list'), next_param))

            messages.success(request, "Status da cotação atualizado no lote com sucesso.")

    return redirect(_append_next(reverse('proposal_batch_detail', args=[proposal.pk]), next_param))

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_add_historico(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    _, next_param = _resolver_back_url(request, reverse('partner_detail', args=[proposal.partner_id]))

    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')

        if descricao or arquivo:
            _registrar_historico_proposta(
                proposal,
                request.user,
                descricao,
                tipo='anexo' if arquivo else 'comentario',
                arquivo=arquivo,
            )
            messages.success(request, "Registro adicionado ao histórico da cotação.")

    return redirect(_append_next(reverse('proposal_detail', args=[proposal.pk]), next_param))
@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner
    endereco_atual = proposal.client_address
    is_conversion_completion = request.GET.get('modo') == 'convertida' or request.POST.get('modo') == 'convertida'
    propostas_lote = list(
        Proposal.objects.filter(codigo_proposta=proposal.codigo_proposta).select_related('cliente', 'client_address').order_by('id')
    ) if proposal.codigo_proposta else [proposal]

    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal, lock_relationship_fields=is_conversion_completion)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            if is_conversion_completion:
                partner.cnpj_cpf = form.cleaned_data.get('partner_cnpj_cpf') or partner.cnpj_cpf
                partner.save(update_fields=['cnpj_cpf'])

                proposta_base = form.save(commit=False)
                campos_compartilhados = [
                    'nome_proposta', 'velocidade', 'tecnologia', 'disponibilidade', 'mttr',
                    'perda_pacote', 'latencia', 'interfaces', 'ipv4_bloco', 'designador', 'trunk', 'dhcp',
                    'prazo_ativacao', 'contato_suporte', 'telefone_suporte', 'ticket_cliente', 'valor_mensal',
                    'ticket_empresa',
                    'taxa_instalacao', 'valor_parceiro', 'tempo_contrato', 'email_faturamento'
                ]

                for item in propostas_lote:
                    for campo in campos_compartilhados:
                        setattr(item, campo, getattr(proposta_base, campo))
                    item.status = 'aguardando_contratacao'
                    item.save()

                    _registrar_historico_proposta(
                        item,
                        request.user,
                        (
                            "Dados técnicos e financeiros preenchidos após proposta viável.\n\n"
                            f"ID da proposta: #{item.codigo_exibicao}\n"
                            f"Unidade: {item.client_address or '--'}"
                        ),
                    )

                RegistroHistorico.objects.create(
                    tipo='sistema',
                    acao=(
                        "Proposta enviada para aguardando contratação após complementação técnica e financeira.\n\n"
                        f"ID da proposta: #{proposal.codigo_exibicao}\n"
                        f"Quantidade de logins impactados: {len(propostas_lote)}"
                    ),
                    usuario=request.user,
                    content_type=ContentType.objects.get_for_model(Partner),
                    object_id=partner.id
                )

                messages.success(request, "Dados técnicos e financeiros salvos com sucesso. A cotação foi enviada para a aba de parceiros em aguardando contratação.")
                return redirect('partner_list')

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
                lista_ids_historico = list(enderecos_ids)
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
                texto_snapshot = f"✏️ Edição de Proposta/OS realizada.\n\n"
                if novas_unidades:
                    texto_snapshot += f"➕ {len(novas_unidades)} NOVO(S) LINK(S) ADICIONADO(S):\n" + "\n".join(novas_unidades) + "\n\n"
                if valores_novos or mudou_unidade:
                    if not mudou_unidade and endereco_atual:
                        texto_snapshot += f"🔗 REFERÊNCIA: {endereco_atual}\n\n"
                    texto_snapshot += "✅ Atualizado:\n" + "\n".join(valores_novos) + "\n\n--------------------------------------\n\n"
                    texto_snapshot += "⏳ Antes:\n" + "\n".join(valores_antigos)

                RegistroHistorico.objects.create(
                    tipo='sistema', 
                    acao=texto_snapshot.strip(), # CORRIGIDO
                    usuario=request.user,        # CORRIGIDO
                    content_type=ContentType.objects.get_for_model(Partner), 
                    object_id=partner.id
                )

                _registrar_historico_proposta(
                    proposal,
                    request.user,
                    texto_snapshot.strip(),
                )

            messages.success(request, f"Sucesso! Atualizações salvas para a Speed.")
            return redirect('partner_detail', pk=partner.pk)
    else:
        form = ProposalForm(instance=proposal, lock_relationship_fields=is_conversion_completion)

    return render(request, 'partners/proposal_form.html', {
        'form': form,
        'proposal': proposal,
        'partner': partner,
        'is_conversion_completion': is_conversion_completion,
        'propostas_lote': propostas_lote,
    })

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_status_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner

    if request.method == 'POST':
        novo_status = request.POST.get('status')
        status_validos = {choice[0] for choice in Proposal.STATUS_CHOICES}

        if novo_status not in status_validos:
            messages.error(request, "Status de cotação inválido.")
            return redirect('partner_detail', pk=partner.pk)

        status_antigo = proposal.status
        if status_antigo != novo_status:
            proposal.status = novo_status
            proposal.save(update_fields=['status'])

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
                object_id=partner.id
            )
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
    proposals = Proposal.objects.exclude(status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']).select_related('partner', 'cliente').order_by('-id')
    total_receita = proposals.aggregate(Sum('valor_mensal'))['valor_mensal__sum'] or 0
    return render(request, 'partners/proposal_global_list.html', {'proposals': proposals, 'total_receita': total_receita})

# ==============================================================================
# VIEWS DE RASTREABILIDADE (UNIDADES E CLIENTES)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def address_proposals_list(request, address_id):
    endereco = get_object_or_404(Endereco, pk=address_id)
    proposals = Proposal.objects.filter(client_address=endereco).exclude(status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']).select_related('partner', 'cliente')
    partners = Partner.objects.all().order_by('nome_fantasia')
    return render(request, 'partners/address_proposals_list.html', {'endereco': endereco, 'proposals': proposals, 'partners': partners})

@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_clients_list(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    proposals = Proposal.objects.filter(partner=partner).exclude(status__in=['encerrada', 'ativa', 'aguardando_contratacao', 'contratado', 'declinado']).select_related('cliente', 'client_address')
    clientes_agrupados = {}
    for prop in proposals:
        cliente = prop.cliente
        if cliente not in clientes_agrupados:
            clientes_agrupados[cliente] = []
        if prop.client_address not in clientes_agrupados[cliente]:
            clientes_agrupados[cliente].append(prop.client_address)

    return render(request, 'partners/partner_clients_list.html', {
        'partner': partner, 'clientes_agrupados': clientes_agrupados, 'total_links': proposals.count()
    })
