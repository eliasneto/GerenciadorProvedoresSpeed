from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# Importação correta: do módulo leads para o módulo core
from leads.models import Lead 

@login_required
def home(request):
    """Página inicial com contadores de parceiros e prospecções"""
    context = {
        'total_leads': Lead.objects.count(),
        # Aqui você adicionará outros contadores conforme criar os apps
    }
    return render(request, 'core/home.html', context)