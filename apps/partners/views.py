from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Sum

# Importações do próprio App
from .models import Partner, Proposal
from .forms import PartnerForm, ProposalForm

# AJUSTE CRÍTICO: Importando o nome correto da classe conforme seu models.py
from clientes.models import Endereco 

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
    """Exibe o perfil do parceiro e o grid de propostas vinculadas."""
    partner = get_object_or_404(Partner, pk=pk)
    # Busca propostas otimizando a query
    proposals = partner.proposals.all().order_by('-id')
    
    return render(request, 'partners/partner_detail.html', {
        'partner': partner,
        'proposals': proposals
    })

# --- VIEWS DE PROPOSTAS / ORDEM DE SERVIÇO ---

@login_required
def proposal_create(request, partner_pk):
    """Inicia uma nova proposta técnica vinculada a um parceiro e auto-preenche a unidade."""
    partner = get_object_or_404(Partner, pk=partner_pk)
    
    # Inicia a proposta em memória
    proposal = Proposal(partner=partner)
    
    # LÓGICA SPEED: Se a URL contiver '?endereco=ID', preenchemos automaticamente
    endereco_id = request.GET.get('endereco')
    if endereco_id:
        endereco_obj = get_object_or_404(Endereco, pk=endereco_id)
        proposal.client_address = endereco_obj
        proposal.cliente = endereco_obj.cliente # Auto-vincula o cliente também
        
    proposal.save() # Salva no banco
    
    messages.success(request, f"Nova OS iniciada para {partner.nome_fantasia or partner.razao_social}")
    return redirect('proposal_update', pk=proposal.pk)

@login_required
def proposal_update(request, pk):
    """Tela técnica para edição da OS e Geração em Lote (Speed Bulk Create)."""
    proposal = get_object_or_404(Proposal, pk=pk)
    partner = proposal.partner

    if request.method == 'POST':
        form = ProposalForm(request.POST, instance=proposal)
        
        # 1. Capturamos a lista de IDs das caixinhas marcadas no frontend
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            if not enderecos_ids:
                # Se não marcou nenhuma caixinha, salva o formulário normalmente sem endereço
                form.save()
                messages.warning(request, "Configurações salvas, mas nenhuma unidade foi vinculada!")
                return redirect('partner_detail', pk=partner.pk)

            # Salva os dados do formulário na instância atual, mas não commita no banco ainda
            proposta_base = form.save(commit=False)
            
            # 2. Pega o PRIMEIRO ID da lista para atualizar o contrato atual
            primeiro_endereco_id = enderecos_ids.pop(0) # Remove e guarda o primeiro item
            primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)
            proposta_base.client_address = primeiro_endereco
            proposta_base.save() # Salva a proposta original com o primeiro endereço
            
            # 3. O LOOP MÁGICO: Clona a proposta para o resto das caixinhas (se houver)
            for end_id in enderecos_ids:
                endereco_extra = get_object_or_404(Endereco, pk=end_id)
                
                # Truque de clonagem do Django: Pega do banco, limpa a Primary Key e salva de novo!
                clone = Proposal.objects.get(pk=proposta_base.pk)
                clone.pk = None # Ao definir PK como None, o Django entende que é um novo registro (INSERT)
                clone.client_address = endereco_extra # Troca só o endereço
                clone.save()

            # Conta total = o original (1) + os clones (tamanho da lista restante)
            total_gerado = 1 + len(enderecos_ids)
            messages.success(request, f"Sucesso! {total_gerado} links técnicos configurados em lote para a Speed.")
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
    # select_related evita o problema N+1 ao buscar nomes de parceiros e clientes
    proposals = Proposal.objects.all().select_related('partner', 'cliente').order_by('-id')
    
    # Soma de todos os valores mensais ativos
    total_receita = proposals.aggregate(Sum('valor_mensal'))['valor_mensal__sum'] or 0
    
    return render(request, 'partners/proposal_global_list.html', {
        'proposals': proposals,
        'total_receita': total_receita
    })

# --- VIEWS DE RASTREABILIDADE (UNIDADES) ---

@login_required
def address_proposals_list(request, address_id):
    """
    Rastreabilidade: Filtra as propostas técnicas de uma unidade específica.
    """
    endereco = get_object_or_404(Endereco, pk=address_id)
    proposals = Proposal.objects.filter(client_address=endereco).select_related('partner', 'cliente')

    # NOVO: Busca os provedores para o modal
    partners = Partner.objects.all().order_by('nome_fantasia')

    return render(request, 'partners/address_proposals_list.html', {
        'endereco': endereco,
        'proposals': proposals,
        'partners': partners
    })