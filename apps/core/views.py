from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages

from leads.models import Lead
from .models import RegistroHistorico


@login_required
def home(request):
    """Página inicial com contadores."""
    context = {
        'total_leads': Lead.objects.count(),
    }
    return render(request, 'core/home.html', context)


@login_required
def timeline_global(request, app_label, model_name, object_id):
    """
    Tela global de histórico para qualquer objeto do sistema.
    Exemplo:
    /timeline/leads/lead/1/
    """

    content_type = get_object_or_404(
        ContentType,
        app_label=app_label,
        model=model_name
    )

    obj_class = content_type.model_class()
    obj = get_object_or_404(obj_class, pk=object_id)

    nome_objeto = (
        getattr(obj, 'nome_fantasia', None)
        or getattr(obj, 'razao_social', None)
        or getattr(obj, 'nome', None)
        or str(obj)
    )

    historico = RegistroHistorico.objects.filter(
        content_type=content_type,
        object_id=object_id
    ).order_by('-data')

    if request.method == 'POST':
        descricao = (request.POST.get('descricao') or '').strip()
        arquivo = request.FILES.get('arquivo')

        if not descricao and not arquivo:
            messages.warning(request, "Informe uma descrição ou envie um arquivo.")
            return redirect(
                'timeline_global',
                app_label=app_label,
                model_name=model_name,
                object_id=object_id
            )

        tipo = 'anexo' if arquivo else 'comentario'

        RegistroHistorico.objects.create(
            tipo=tipo,
            acao=descricao if descricao else None,
            arquivo=arquivo,
            usuario=request.user,
            content_type=content_type,
            object_id=object_id
        )

        messages.success(request, "Registro salvo com sucesso!")
        return redirect(
            'timeline_global',
            app_label=app_label,
            model_name=model_name,
            object_id=object_id
        )

    context = {
        'historico': historico,
        'nome_objeto': nome_objeto,
        'modulo_origem': model_name.upper(),
        'objeto': obj,
    }
    return render(request, 'core/timeline_global.html', context)