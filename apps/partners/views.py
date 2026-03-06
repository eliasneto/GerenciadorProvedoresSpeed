from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
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

# --- VIEWS DE PARCEIROS (DADOS MESTRE) ---

@login_required
def partner_list(request):
    """Lista todos os parceiros cadastrados com paginação."""
    partners_queryset = Partner.objects.all().order_by('-id')
    
    paginator = Paginator(partners_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'partners/partner_list.html', {
        'page_obj': page_obj,
        'total_partners': Partner.objects.count()
    })

@login_required
def partner_detail(request, pk):
    """Exibe o perfil do parceiro, propostas e o HISTÓRICO (Timeline)."""
    partner = get_object_or_404(Partner, pk=pk)
    proposals = partner.proposals.all().order_by('-id')
    
    # --- MÁGICA SPEED: Busca o histórico que veio do Lead + novos registros ---
    partner_type = ContentType.objects.get_for_model(Partner)
    historico = RegistroHistorico.objects.filter(content_type=partner_type, object_id=partner.id)
    
    return render(request, 'partners/partner_detail.html', {
        'partner': partner,
        'proposals': proposals,
        'historico': historico # Injeta o histórico na tela
    })

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
                descricao=descricao,
                arquivo=arquivo,
                criado_por=request.user,
                content_type=ContentType.objects.get_for_model(Partner),
                object_id=partner.id
            )
            messages.success(request, "Anotação salva no histórico do parceiro!")
            
    return redirect('partner_detail', pk=pk)

# --- VIEWS DE PROPOSTAS / ORDEM DE SERVIÇO ---

@login_required
def proposal_create(request, partner_pk):
    """Inicia uma nova proposta técnica vinculada a um parceiro e auto-preenche a unidade."""
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

@login_required
@login_required
def proposal_update(request, pk):
    """Tela técnica para edição da OS e Geração em Lote."""
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner
    
    # Captura o link (endereço) atual antes de qualquer alteração
    endereco_atual = proposal.client_address

    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            
            # =================================================================
            # MÁGICA SPEED: RASTREAMENTO SPLIT DIFF (ATUALIZADO x ANTES)
            # =================================================================
            valores_novos = []
            valores_antigos = []

            if form.has_changed():
                for campo in form.changed_data:
                    if campo not in ['enderecos_selecionados', 'partner', 'cliente', 'client_address']:
                        valor_antigo = form.initial.get(campo)
                        valor_novo = form.cleaned_data.get(campo)
                        
                        nome_campo = campo.replace('_', ' ').title()
                        
                        # Formatação de dinheiro e meses
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

            # =================================================================
            # LÓGICA DE SALVAMENTO E IDENTIFICAÇÃO DE NOVOS LINKS
            # =================================================================
            mudou_unidade = False
            novas_unidades = []

            if enderecos_ids:
                lista_ids_historico = list(enderecos_ids)
                proposta_base = form.save(commit=False)
                
                # A primeira caixinha atualiza a OS atual
                primeiro_endereco_id = enderecos_ids.pop(0) 
                primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)
                
                # Se o usuário trocou a unidade principal
                if endereco_atual != primeiro_endereco:
                    mudou_unidade = True
                    valores_antigos.append(f"• Unidade Base: {endereco_atual}")
                    valores_novos.append(f"• Unidade Base: {primeiro_endereco}")
                
                proposta_base.client_address = primeiro_endereco
                proposta_base.save() 
                
                # O resto das caixinhas gera CLONES (novos links)
                for end_id in enderecos_ids:
                    endereco_extra = get_object_or_404(Endereco, pk=end_id)
                    clone = Proposal.objects.get(pk=proposta_base.pk)
                    clone.pk = None
                    clone.client_address = endereco_extra 
                    clone.save()
                    novas_unidades.append(f"• {endereco_extra}")
                    
            else:
                form.save()

            # =================================================================
            # GRAVAÇÃO DO RELATÓRIO NO HISTÓRICO NO FORMATO SPLIT DIFF
            # =================================================================
            if valores_novos or valores_antigos or novas_unidades:
                from django.contrib.contenttypes.models import ContentType
                from core.models import RegistroHistorico
                
                texto_snapshot = f"✏️ Edição de Proposta/OS realizada.\n\n"
                
                # 1. MOSTRA SE O USUÁRIO CLONOU NOVOS LINKS NA EDIÇÃO
                if novas_unidades:
                    texto_snapshot += f"➕ {len(novas_unidades)} NOVO(S) LINK(S) ADICIONADO(S):\n"
                    texto_snapshot += "\n".join(novas_unidades) + "\n\n"
                
                # 2. MOSTRA O DIFF DOS DADOS TÉCNICOS/FINANCEIROS
                if valores_novos or mudou_unidade:
                    if not mudou_unidade and endereco_atual:
                        # Se não trocou de unidade, diz exatamente em qual link mexeu
                        texto_snapshot += f"🔗 REFERÊNCIA: {endereco_atual}\n\n"
                         
                    texto_snapshot += "✅ Atualizado:\n"
                    texto_snapshot += "\n".join(valores_novos) + "\n\n"
                    texto_snapshot += "--------------------------------------\n\n"
                    texto_snapshot += "⏳ Antes:\n"
                    texto_snapshot += "\n".join(valores_antigos)

                RegistroHistorico.objects.create(
                    tipo='sistema',
                    descricao=texto_snapshot.strip(),
                    criado_por=request.user,
                    content_type=ContentType.objects.get_for_model(Partner),
                    object_id=partner.id
                )

            messages.success(request, f"Sucesso! Atualizações salvas para a Speed.")
            return redirect('partner_detail', pk=partner.pk)
            
    else:
        form = ProposalForm(instance=proposal)

    return render(request, 'partners/proposal_form.html', {
        'form': form,
        'proposal': proposal,
        'partner': partner
    })

@login_required
def proposal_delete(request, pk):
    """Remove uma OS do sistema."""
    proposal = get_object_or_404(Proposal, pk=pk)
    partner_pk = proposal.partner.pk
    proposal.delete()
    messages.warning(request, "Proposta removida do sistema.")
    return redirect('partner_detail', pk=partner_pk)

@login_required
def proposal_global_list(request):
    """A Central de Comando: Lista todas as OS e calcula a receita total."""
    proposals = Proposal.objects.all().select_related('partner', 'cliente').order_by('-id')
    total_receita = proposals.aggregate(Sum('valor_mensal'))['valor_mensal__sum'] or 0
    return render(request, 'partners/proposal_global_list.html', {
        'proposals': proposals,
        'total_receita': total_receita
    })

# --- VIEWS DE RASTREABILIDADE (UNIDADES) ---

@login_required
def address_proposals_list(request, address_id):
    """Rastreabilidade: Filtra as propostas técnicas de uma unidade específica."""
    endereco = get_object_or_404(Endereco, pk=address_id)
    proposals = Proposal.objects.filter(client_address=endereco).select_related('partner', 'cliente')
    partners = Partner.objects.all().order_by('nome_fantasia')

    return render(request, 'partners/address_proposals_list.html', {
        'endereco': endereco,
        'proposals': proposals,
        'partners': partners
    })

@login_required
def partner_clients_list(request, pk):
    """Exibe todos os clientes e unidades atendidas por um parceiro específico."""
    partner = get_object_or_404(Partner, pk=pk)
    
    # Busca todas as propostas desse parceiro (trazendo cliente e endereço junto para ficar rápido)
    proposals = Proposal.objects.filter(partner=partner).select_related('cliente', 'client_address')
    
    # Agrupa os endereços por cliente
    clientes_agrupados = {}
    for prop in proposals:
        cliente = prop.cliente
        if cliente not in clientes_agrupados:
            clientes_agrupados[cliente] = []
            
        # Adiciona a unidade à lista do cliente (evitando duplicidade caso tenha 2 OS no mesmo endereço)
        if prop.client_address not in clientes_agrupados[cliente]:
            clientes_agrupados[cliente].append(prop.client_address)

    return render(request, 'partners/partner_clients_list.html', {
        'partner': partner,
        'clientes_agrupados': clientes_agrupados,
        'total_links': proposals.count()
    })