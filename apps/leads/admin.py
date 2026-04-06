from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'cidade', 'estado', 'status', 'confianca', 'data_criacao')
    list_filter = ('status', 'estado', 'confianca', 'fonte')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade', 'bairro', 'cep')

    fieldsets = (
        ('Identificação do Parceiro', {
            'fields': ('razao_social', 'nome_fantasia', 'cnpj_cpf', 'site', 'status')
        }),
        ('Localização', {
            'fields': ('cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
        }),
        ('Contato', {
            'fields': ('contato_nome', 'email', 'telefone')
        }),
        ('Inteligência Artificial & Captação', {
            'fields': ('fonte', 'confianca', 'instagram_username', 'instagram_url', 'bio_instagram', 'observacao_ia'),
            'classes': ('collapse',)
        }),
    )
