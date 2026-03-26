from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages

# Importações dos modelos
from leads.models import Lead 
from .models import RegistroHistorico # Importa a Timeline que criamos no models do core

# 1. Cria a regra de verificação para Administradores
def grupo_Administrador_required(user):
    if user.groups.filter(name='Administrador').exists() or user.is_superuser:
        return True
    raise PermissionDenied

# 🚀 NOVA REGRA: Libera para todo mundo da operação (LastMile, Parceiros, BackOffice) e Admins
def grupo_Operacao_required(user):
    grupos_permitidos = ['Administrador', 'LastMile', 'Parceiros', 'BackOffice']
    if user.groups.filter(name__in=grupos_permitidos).exists() or user.is_superuser:
        return True
    raise PermissionDenied

@login_required
def home(request):
    """Página inicial com contadores de parceiros e prospecções"""
    context = {
        'total_leads': Lead.objects.count(),
        # Aqui você adicionará outros contadores conforme criar os apps
    }
    return render(request, 'core/home.html', context)

# 🚀 TROCAMOS A TRAVA AQUI! Agora usa a regra 'grupo_Operacao_required'
@user_passes_test(grupo_Operacao_required)
@login_required
def timeline_global(request, app_label, model_name, object_id):
    """
    Tela Global de Histórico.
    Funciona para leads, partners, proposals, ou qualquer outra tabela futura.
    """
    # 1. Descobre qual é a tabela do banco dinamicamente (ex: app 'leads', model 'lead')
    content_type = get_object_or_404(ContentType, app_label=app_label, model=model_name)
    
    # 2. Busca o objeto real (o Lead ou Parceiro) só para pegar o nome dele
    obj_class = content_type.model_class()
    obj = get_object_or_404(obj_class, pk=object_id)
    
    # Tenta pegar a Razão Social ou Nome Fantasia. Se não achar, pega o padrão do sistema
    nome_objeto = getattr(obj, 'nome_fantasia', getattr(obj, 'razao_social', str(obj)))

    # 3. Busca o histórico atrelado a este objeto
    historico = RegistroHistorico.objects.filter(content_type=content_type, object_id=object_id)

    # 4. Salva um novo registro (se a requisição for um POST do formulário)
    if request.method == 'POST':
        descricao = request.POST.get('descricao')
        arquivo = request.FILES.get('arquivo')
        
        if descricao or arquivo:
            tipo = 'anexo' if arquivo else 'comentario'
            RegistroHistorico.objects.create(
                tipo=tipo,
                acao=descricao,
                arquivo=arquivo,
                usuario=request.user,
                content_type=content_type,
                object_id=object_id
            )
            messages.success(request, "Registro salvo com sucesso!")
            # Redireciona para a mesma página para limpar o formulário e evitar reenvio
            return redirect('timeline_global', app_label=app_label, model_name=model_name, object_id=object_id)

    return render(request, 'core/timeline_global.html', {
        'historico': historico,
        'nome_objeto': nome_objeto,
        'modulo_origem': model_name.upper() # Fica bonito na tela (Ex: LEAD, PARTNER)
    })