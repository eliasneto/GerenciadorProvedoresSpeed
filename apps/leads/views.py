from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Lead
from .forms import LeadForm
from partners.models import Partner, Proposal  # IMPORTANTE: Adicionado Proposal aqui
from django.contrib import messages

@login_required
def lead_list(request):
    """Lista todos os leads com paginação"""
    leads_list = Lead.objects.all().order_by('-id')
    paginator = Paginator(leads_list, 10)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'leads/lead_list.html', {'page_obj': page_obj})

@login_required
def lead_create(request):
    """Criação de novos leads de prospecção"""
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Novo lead cadastrado com sucesso!")
            return redirect('lead_list')
    else:
        form = LeadForm()
    return render(request, 'leads/lead_form.html', {'form': form})

@login_required
def lead_update(request, pk):
    """Edição de dados básicos do lead"""
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados do lead atualizados!")
            return redirect('lead_list')
    else:
        form = LeadForm(instance=lead)
        
    return render(request, 'leads/lead_form.html', {
        'form': form,
        'title': 'Editar Lead'
    })

@login_required
def lead_delete(request, pk):
    """Remoção de lead da base"""
    lead = get_object_or_404(Lead, pk=pk)
    if request.method == 'POST':
        lead.delete()
        messages.warning(request, "Lead removido da base de prospecção.")
        return redirect('lead_list')
    return redirect('lead_list')

# Adicione a importação do ProposalForm no topo do arquivo se não tiver:
from partners.forms import ProposalForm

@login_required
def update_lead_status(request, pk):
    """Valida a intenção e redireciona para a conversão segura (Lazy Commit)"""
    if request.method == 'POST':
        lead = get_object_or_404(Lead, pk=pk)
        novo_status = request.POST.get('status')
        
        if novo_status == 'andamento':
            # 1. Validação de campos obrigatórios
            campos_faltantes = []
            if not lead.cnpj_cpf: campos_faltantes.append("CNPJ/CPF")
            if not lead.email: campos_faltantes.append("E-mail")
            if not lead.telefone: campos_faltantes.append("Telefone")

            if campos_faltantes:
                msg = ", ".join(campos_faltantes)
                messages.error(request, f"Não é possível converter: Os campos [{msg}] são obrigatórios.")
                return redirect('lead_list')

            # 2. Evita duplicidade
            if Partner.objects.filter(cnpj_cpf=lead.cnpj_cpf).exists():
                messages.error(request, f"O CNPJ {lead.cnpj_cpf} já é um parceiro ativo.")
                return redirect('lead_list')

            # REDIRECIONA PARA A TELA DE CONVERSÃO SEM SALVAR NADA AINDA
            return redirect('lead_convert', pk=lead.pk)
            
        # Atualização simples de status (Ex: Negociação -> Perdido)
        if novo_status:
            lead.status = novo_status
            lead.save()
            messages.info(request, f"Status atualizado para: {novo_status}")
        
    return redirect('lead_list')


@login_required
def lead_convert(request, pk):
    """Tela Oficial de Conversão: Salva Parceiro e Proposta de uma vez só"""
    lead = get_object_or_404(Lead, pk=pk)
    
    # Cria um Parceiro "Fantasma" apenas na memória para o HTML não quebrar
    partner_draft = Partner(
        nome_fantasia=lead.nome_fantasia or lead.razao_social,
        razao_social=lead.razao_social or lead.nome_fantasia,
        cnpj_cpf=lead.cnpj_cpf,
        telefone=lead.telefone
    )

    if request.method == 'POST':
        form = ProposalForm(request.POST)
        enderecos_ids = request.POST.getlist('enderecos_selecionados')

        if form.is_valid():
            if not enderecos_ids:
                messages.error(request, "Selecione pelo menos uma unidade de instalação.")
                return render(request, 'partners/proposal_form.html', {'form': form, 'partner': partner_draft, 'is_lead_conversion': True})

            # AGORA SIM! O usuário confirmou. Salvamos tudo em cascata.
            partner_draft.save() # Cria o Parceiro no banco

            proposta_base = form.save(commit=False)
            primeiro_endereco_id = enderecos_ids.pop(0)
            
            # Import dinâmico
            from clientes.models import Endereco 
            primeiro_endereco = get_object_or_404(Endereco, pk=primeiro_endereco_id)
            
            proposta_base.partner = partner_draft
            proposta_base.client_address = primeiro_endereco
            proposta_base.cliente = primeiro_endereco.cliente
            proposta_base.save() # Cria a Proposta 1

            # Clona as outras propostas
            for end_id in enderecos_ids:
                endereco_extra = get_object_or_404(Endereco, pk=end_id)
                clone = Proposal.objects.get(pk=proposta_base.pk)
                clone.pk = None
                clone.client_address = endereco_extra
                clone.save()

            # A MÁGICA FINAL: Deleta o Lead apenas após o sucesso!
            lead.delete() 
            
            total_gerado = 1 + len(enderecos_ids)
            messages.success(request, f"Conversão Concluída! {total_gerado} links gerados para {partner_draft.nome_fantasia}.")
            return redirect('partner_detail', pk=partner_draft.pk)
    else:
        form = ProposalForm()

    return render(request, 'partners/proposal_form.html', {
        'form': form,
        'partner': partner_draft, 
        'is_lead_conversion': True # Avisa o HTML que estamos convertendo
    })