from django.contrib import admin

from .models import Lead, LeadEmpresa, LeadEndereco


class LeadEnderecoInline(admin.TabularInline):
    model = LeadEndereco
    extra = 0
    fields = ('cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado')


@admin.register(LeadEmpresa)
class LeadEmpresaAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade_principal', 'status', 'data_criacao')
    list_filter = ('status', 'confianca', 'fonte')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'email', 'telefone')
    inlines = [LeadEnderecoInline]

    def cidade_principal(self, obj):
        primeiro_endereco = obj.enderecos.order_by('id').first()
        return (primeiro_endereco.cidade if primeiro_endereco else '') or '-'

    cidade_principal.short_description = 'Cidade Principal'


@admin.register(LeadEndereco)
class LeadEnderecoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
    list_filter = ('estado', 'cidade')
    search_fields = ('empresa__nome_fantasia', 'empresa__razao_social', 'empresa__cnpj_cpf', 'endereco', 'bairro', 'cidade', 'cep')


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('nome_fantasia', 'cidade', 'estado', 'status', 'confianca', 'data_criacao')
    list_filter = ('status', 'estado', 'confianca', 'fonte')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'cidade', 'bairro', 'cep')

    fieldsets = (
        ('Identificacao do Parceiro', {
            'fields': ('razao_social', 'nome_fantasia', 'cnpj_cpf', 'site', 'status')
        }),
        ('Localizacao', {
            'fields': ('cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado')
        }),
        ('Contato', {
            'fields': ('contato_nome', 'email', 'telefone')
        }),
        ('Estrutura Nova', {
            'fields': ('empresa_estruturada', 'endereco_estruturado'),
            'classes': ('collapse',)
        }),
        ('Inteligencia Artificial & Captacao', {
            'fields': ('fonte', 'confianca', 'instagram_username', 'instagram_url', 'bio_instagram', 'observacao_ia'),
            'classes': ('collapse',)
        }),
    )
