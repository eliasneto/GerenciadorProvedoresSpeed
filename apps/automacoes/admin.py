from django.contrib import admin
from .models import Automacao

@admin.register(Automacao)
class AutomacaoAdmin(admin.ModelAdmin):
    # Colunas que vão aparecer na lista
    list_display = ('nome', 'status', 'progresso', 'ultima_execucao')
    # Permite editar o status e o progresso direto na lista
    list_editable = ('status', 'progresso')
    # Filtros laterais
    list_filter = ('status',)
    search_fields = ('nome',)