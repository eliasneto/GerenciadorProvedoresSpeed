from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse_lazy 
from django.views.generic import UpdateView 
from django.contrib.auth.mixins import LoginRequiredMixin 
from .models import Cliente, Endereco 
from .forms import ClienteForm, EnderecoForm
from django.http import JsonResponse
from django.db.models import Q, Count
import json
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied

# ==========================================
# 🛡️ REGRA DE ACESSO: SGP_LastMile
# ==========================================
def check_lastmile_group(user):
    """
    Libera acesso apenas para Superusuários ou 
    quem estiver na pasta SGP_LastMile do AD.
    """
    if user.is_superuser or user.groups.filter(name='SGP_LastMile').exists():
        return True
    raise PermissionDenied

# ==========================================
# LISTAGEM DE CLIENTES
# ==========================================

@login_required
@user_passes_test(check_lastmile_group)
def cliente_list(request):
    # Pega os parâmetros da URL
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', '')
    status_filtro = request.GET.get('status', '') # 🚀 NOVO: Captura o status escolhido no filtro

    # 1. Traz os clientes já contando as unidades (num_pontos) para podermos ordenar
    clientes_queryset = Cliente.objects.annotate(num_pontos=Count('enderecos')).prefetch_related('enderecos')
    
    # 2. Filtro de Pesquisa (Busca por Razão, Fantasia, CNPJ ou ID do IXC)
    if q:
        clientes_queryset = clientes_queryset.filter(
            Q(razao_social__icontains=q) | 
            Q(nome_fantasia__icontains=q) |
            Q(cnpj_cpf__icontains=q) |
            Q(id_ixc__icontains=q)
        )

    # 3. 🚀 NOVO: Filtro por Status das Unidades (IXC)
    if status_filtro in ['ativo', 'inativo', 'cancelado', 'pendente']:
        # Usamos enderecos__status para "entrar" na tabela de endereços.
        # O .distinct() é obrigatório para não duplicar o cliente se ele tiver 2 unidades ativas!
        clientes_queryset = clientes_queryset.filter(enderecos__status=status_filtro).distinct()

    # 4. Ordenação (Do menor pro maior, ou maior pro menor)
    if sort == 'pontos_asc':
        clientes_queryset = clientes_queryset.order_by('num_pontos', '-criado_em')
    elif sort == 'pontos_desc':
        clientes_queryset = clientes_queryset.order_by('-num_pontos', '-criado_em')
    else:
        # Padrão: mais recentes primeiro
        clientes_queryset = clientes_queryset.order_by('-criado_em')
    
    # Paginação: 10 por página
    paginator = Paginator(clientes_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clientes/cliente_list.html', {
        'page_obj': page_obj,
        'total_clientes': clientes_queryset.count(),
        'q': q,               
        'sort': sort,         
        'status_atual': status_filtro  # 🚀 NOVO: Passamos para o HTML saber qual filtro pintar
    })

@login_required
@user_passes_test(check_lastmile_group)
def cliente_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cliente_list')
    else:
        form = ClienteForm()
    
    return render(request, 'clientes/cliente_form.html', {'form': form})

@login_required 
@user_passes_test(check_lastmile_group)
def cliente_detail(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    proposals = cliente.proposals.all().order_by('-id')
    return render(request, 'clientes/cliente_detail.html', {
        'cliente': cliente,
        'proposals': proposals
    })

# ==========================================
# EDIÇÃO DE CLIENTE (CLASS BASED VIEW)
# ==========================================
class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    
    def get_success_url(self):
        return reverse_lazy('cliente_list')

# ==========================================
# GESTÃO DE UNIDADES (ENDEREÇOS / LOGINS)
# ==========================================
# No arquivo views.py

@login_required
@user_passes_test(check_lastmile_group)
def endereco_list(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    # 1. Parâmetros de Filtro e Pesquisa
    status_filtro = request.GET.get('status', '')
    sort = request.GET.get('sort', 'id')
    q = request.GET.get('q', '').strip()
    
    # 2. Pega todos os endereços do cliente
    enderecos = cliente.enderecos.all()
    
    # Conta os ativos antes de aplicar os filtros
    total_ativas = enderecos.filter(status='ativo').count()
    
    # 3. Filtro de Pesquisa Textual
    if q:
        enderecos = enderecos.filter(
            Q(login_ixc__icontains=q) | 
            Q(filial_ixc__icontains=q) |
            Q(cidade__icontains=q) |
            Q(agent_circuit_id__icontains=q)
        )

    # 4. Filtro de Status
    if status_filtro in ['ativo', 'inativo', 'cancelado', 'pendente']:
        enderecos = enderecos.filter(status=status_filtro)
        
    # 5. Ordenação
    if sort == 'filial':
        enderecos = enderecos.order_by('filial_ixc', 'id')
    elif sort == 'status':
        enderecos = enderecos.order_by('status', 'id')
    else:
        enderecos = enderecos.order_by('id')
    
    # 6. Paginação (10 itens por página)
    paginator = Paginator(enderecos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clientes/endereco_list.html', {
        'cliente': cliente,
        'page_obj': page_obj,          # <- Mandamos o page_obj agora
        'total_ativas': total_ativas,
        'enderecos': enderecos,        # <- Necessário para o .count() no topo da tela
        'status_atual': status_filtro,
        'sort': sort,
        'q': q
    })

@login_required
@user_passes_test(check_lastmile_group)
def endereco_create(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        form = EnderecoForm(request.POST)
        if form.is_valid():
            endereco = form.save(commit=False)
            endereco.cliente = cliente  
            endereco.save()
            return redirect('endereco_list', pk=cliente.pk)
    else:
        form = EnderecoForm()
    
    return render(request, 'clientes/endereco_form.html', {
        'form': form, 
        'cliente': cliente
    })

class EnderecoUpdateView(LoginRequiredMixin, UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'clientes/endereco_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.object.cliente
        return context

    def get_success_url(self):
        return reverse_lazy('endereco_list', kwargs={'pk': self.object.cliente.pk})

# ==========================================
# APIS DE BUSCA E ATUALIZAÇÃO
# ==========================================
@login_required
@user_passes_test(check_lastmile_group)
def api_cliente_search(request):
    """API para busca rápida: agora busca também pelo ID do IXC"""
    q = request.GET.get('q', '')
    
    clientes = Cliente.objects.filter(
        Q(razao_social__icontains=q) | 
        Q(nome_fantasia__icontains=q) |
        Q(id_ixc__icontains=q) 
    )[:10] 
    
    data = [{
        'id': c.id, 
        'nome': f"[{c.id_ixc}] {c.nome_fantasia or c.razao_social}" if c.id_ixc else (c.nome_fantasia or c.razao_social),
        'documento': getattr(c, 'cnpj_cpf', 'Sem documento')
    } for c in clientes]
    
    return JsonResponse(data, safe=False)

@login_required
@user_passes_test(check_lastmile_group)
def api_cliente_enderecos(request, pk):
    """Retorna endereços de um cliente específico"""
    cliente = get_object_or_404(Cliente, pk=pk)
    enderecos = cliente.enderecos.all().order_by('logradouro')
    
    data = [{
        'id': e.id, 
        'endereco': e.logradouro, 
        'numero': e.numero,
        'cidade': e.cidade,
        'cep': e.cep,
        'display': f"{e.logradouro}, {e.numero} ({e.cidade})"
    } for e in enderecos]
    
    return JsonResponse(data, safe=False)

@login_required
@require_POST
@user_passes_test(check_lastmile_group)
def api_update_unit_status(request, pk):
    """API para atualização rápida de status via Modal"""
    try:
        data = json.loads(request.body)
        endereco = get_object_or_404(Endereco, pk=pk)
        
        novo_status = data.get('status')
        data_ativacao = data.get('data_ativacao')

        endereco.status = novo_status
        
        if novo_status == 'ativo':
            endereco.data_ativacao = data_ativacao
        else:
            endereco.data_ativacao = None
            
        endereco.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)