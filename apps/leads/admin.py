from django.contrib import admin
from .models import Lead

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    # 1. Colunas que aparecem na lista (tabela) inicial do Admin
    list_display = ('nome_fantasia', 'cidade', 'estado', 'status', 'confianca', 'data_criacao')
    
    # 2. Cria um menu de filtros na lateral direita
    list_filter = ('status', 'estado', 'confianca', 'fonte')
    
    # 3. Cria uma barra de pesquisa no topo
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade')
    
    # 4. Organiza os campos em blocos bonitos na hora de editar um Lead
    fieldsets = (
        ('Identificação da Empresa', {
            'fields': ('razao_social', 'nome_fantasia', 'cnpj_cpf', 'site', 'status')
        }),
        ('Localização', {
            'fields': ('endereco', 'cidade', 'estado')
        }),
        ('Contato', {
            'fields': ('contato_nome', 'email', 'telefone')
        }),
        ('Inteligência Artificial & Captação', {
            'fields': ('fonte', 'confianca', 'instagram_username', 'instagram_url', 'bio_instagram', 'observacao_ia'),
            'classes': ('collapse',) # Mágica: Cria uma "sanfona" fechada para não poluir a tela
        }),
    )