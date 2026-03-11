# clientes/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.urls import reverse_lazy 
from django.views.generic import UpdateView 
from django.contrib.auth.mixins import LoginRequiredMixin 
from .models import Cliente, Endereco 
from .forms import ClienteForm, EnderecoForm
from django.http import JsonResponse
from django.db.models import Q  
import json
from django.views.decorators.http import require_POST

# ... seus outros imports ...

@login_required
def cliente_list(request):
    # Buscamos os clientes e usamos prefetch_related para otimizar a query dos endereços
    clientes_queryset = Cliente.objects.all().prefetch_related('enderecos').order_by('-data_cadastro')
    
    # Paginação: 10 por página
    paginator = Paginator(clientes_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clientes/cliente_list.html', {
        'page_obj': page_obj,
        'total_clientes': clientes_queryset.count()
    })

@login_required
def cliente_create(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cliente_list')
    else:
        form = ClienteForm()
    
    return render(request, 'clientes/cliente_form.html', {'form': form})


# ==========================================
# EDIÇÃO DE CLIENTE (SPEED)
# ==========================================
class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'clientes/cliente_form.html'
    
    def get_success_url(self):
        return reverse_lazy('cliente_list')


# ==========================================
# CRIAÇÃO DE ENDEREÇO (UNIDADE)
# ==========================================
@login_required
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


# ==========================================
# EDIÇÃO DE ENDEREÇO (NOVA VIEW SPEED)
# ==========================================
class EnderecoUpdateView(LoginRequiredMixin, UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'clientes/endereco_form.html'
    
    def get_context_data(self, **kwargs):
        # Injeta o cliente no contexto para que o cabeçalho do template funcione
        context = super().get_context_data(**kwargs)
        context['cliente'] = self.object.cliente
        return context

    def get_success_url(self):
        # Redireciona de volta para o grid de unidades do cliente
        return reverse_lazy('endereco_list', kwargs={'pk': self.object.cliente.pk})


# ==========================================
# LISTAGEM E APIS
# ==========================================
@login_required
def endereco_list(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    enderecos = cliente.enderecos.all().order_by('-principal', 'tipo')
    
    total_ativas = cliente.enderecos.filter(status='ativo').count()
    
    return render(request, 'clientes/endereco_list.html', {
        'cliente': cliente,
        'enderecos': enderecos,
        'total_ativas': total_ativas 
    })

@login_required
def api_cliente_search(request):
    """API para busca rápida de clientes no modal"""
    q = request.GET.get('q', '')
    
    clientes = Cliente.objects.filter(
        Q(razao_social__icontains=q) | Q(nome_fantasia__icontains=q)
    )[:10] 
    
    data = [{
        'id': c.id, 
        'nome': c.nome_fantasia or c.razao_social,
        'documento': getattr(c, 'cnpj_cpf', 'Sem documento')
    } for c in clientes]
    
    return JsonResponse(data, safe=False)

@login_required
def api_cliente_enderecos(request, pk):
    """Retorna endereços de um cliente específico em ordem alfabética"""
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
def cliente_detail(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    proposals = cliente.proposals.all().order_by('-id')
    return render(request, 'clientes/cliente_detail.html', {
        'cliente': cliente,
        'proposals': proposals
    })

@login_required
@require_POST
def api_update_unit_status(request, pk):
    """API para atualização rápida de status e data de ativação"""
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