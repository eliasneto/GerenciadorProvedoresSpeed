from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Automacao
from .utils import sincronizar_automacoes
from .executor import disparar_robo

def lista_automacoes(request):
    sincronizar_automacoes() # Garante que pastas novas apareçam
    automacoes = Automacao.objects.all().order_by('nome')
    return render(request, 'automacoes/lista.html', {'automacoes': automacoes})

def iniciar_automacao(request, pk):
    automacao = get_object_or_404(Automacao, pk=pk)
    
    if request.method == 'POST':
        if request.FILES.get('arquivo'):
            automacao.arquivo_entrada = request.FILES['arquivo']
        
        # Tenta disparar o script
        sucesso, msg = disparar_robo(automacao)
        
        if sucesso:
            automacao.status = 'RODANDO'
            automacao.save()
            messages.success(request, f"O robô {automacao.nome} foi iniciado!")
        else:
            messages.error(request, f"Falha ao iniciar: {msg}")
            
    return redirect('lista_automacoes')