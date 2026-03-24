from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType

# Importações do próprio App
from .models import Partner, Proposal
from .forms import PartnerForm, ProposalForm
from clientes.models import Endereco 

# --- IMPORTAÇÃO DO HISTÓRICO SPEED ---
from core.models import RegistroHistorico

# 1. Cria a regra de verificação
def grupo_Parceiro_required(user):
    # O Superuser (você) sempre passa. Os outros precisam estar no grupo.
    if user.groups.filter(name='Parceiro').exists() or user.is_superuser:
        return True
    # Se não for do grupo, joga um Erro 403 (Acesso Negado)
    raise PermissionDenied

# ==============================================================================
# VIEWS DE PARCEIROS (DADOS MESTRE E ESTEIRAS)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_list(request):
    """Lista APENAS os parceiros ATIVOS (A operação real)."""
    partners_queryset = Partner.objects.filter(status='ativo').order_by('-id')
    
    paginator = Paginator(partners_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'partners/partner_list.html', {
        'page_obj': page_obj,
        'total_partners': partners_queryset.count()
    })
@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_inactive_list(request):
    """Esteira de Reativação (Win-back) para parceiros inativos."""
    # Traz todo mundo que NÃO está ativo (inativo, negociacao, inviavel)
    partners_inativos = Partner.objects.exclude(status='ativo').order_by('-data_cadastro')
    
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
    proposals = partner.proposals.all().order_by('-id')
    
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
        'partner': partner,
        'proposals': proposals,
        'historico': historico,
        'qtd_antigo': qtd_antigo,
        'mostrando_antigos': ver_antigos
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
        
        if novo_status in ['ativo', 'inativo']:
            status_antigo = partner.status
            partner.status = novo_status
            partner.save()
            
            if status_antigo != novo_status:
                if novo_status == 'inativo':
                    tipo_hist = 'anexo' if arquivo else 'sistema'
                    texto_historico = f"🚫 PARCEIRO INATIVADO\n\nMotivo / Observação:\n{observacao}" if observacao else "🚫 PARCEIRO INATIVADO"
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
    messages.success(request, f"Nova OS iniciada para {partner.nome_fantasia or partner.razao_social}")
    return redirect('proposal_update', pk=proposal.pk)
@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_update(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner
    endereco_atual = proposal.client_address

    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
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
                
                for end_id in enderecos_ids:
                    endereco_extra = get_object_or_404(Endereco, pk=end_id)
                    clone = Proposal.objects.get(pk=proposta_base.pk)
                    clone.pk = None
                    clone.client_address = endereco_extra 
                    clone.save()
                    novas_unidades.append(f"• {endereco_extra}")
            else:
                form.save()

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

            messages.success(request, f"Sucesso! Atualizações salvas para a Speed.")
            return redirect('partner_detail', pk=partner.pk)
    else:
        form = ProposalForm(instance=proposal)

    return render(request, 'partners/proposal_form.html', {'form': form, 'proposal': proposal, 'partner': partner})

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_delete(request, pk):
    proposal = get_object_or_404(Proposal, pk=pk)
    partner_pk = proposal.partner.pk
    proposal.delete()
    messages.warning(request, "Proposta removida do sistema.")
    return redirect('partner_detail', pk=partner_pk)

@user_passes_test(grupo_Parceiro_required)
@login_required
def proposal_global_list(request):
    proposals = Proposal.objects.all().select_related('partner', 'cliente').order_by('-id')
    total_receita = proposals.aggregate(Sum('valor_mensal'))['valor_mensal__sum'] or 0
    return render(request, 'partners/proposal_global_list.html', {'proposals': proposals, 'total_receita': total_receita})

# ==============================================================================
# VIEWS DE RASTREABILIDADE (UNIDADES E CLIENTES)
# ==============================================================================
@user_passes_test(grupo_Parceiro_required)
@login_required
def address_proposals_list(request, address_id):
    endereco = get_object_or_404(Endereco, pk=address_id)
    proposals = Proposal.objects.filter(client_address=endereco).select_related('partner', 'cliente')
    partners = Partner.objects.all().order_by('nome_fantasia')
    return render(request, 'partners/address_proposals_list.html', {'endereco': endereco, 'proposals': proposals, 'partners': partners})

@user_passes_test(grupo_Parceiro_required)
@login_required
def partner_clients_list(request, pk):
    partner = get_object_or_404(Partner, pk=pk)
    proposals = Proposal.objects.filter(partner=partner).select_related('cliente', 'client_address')
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