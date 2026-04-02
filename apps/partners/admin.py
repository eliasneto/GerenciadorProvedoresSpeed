from django.contrib import admin

from .models import Partner, Proposal, ProposalMotivoInviavel


class ProposalInline(admin.TabularInline):
    model = Proposal
    extra = 0
    fields = ('codigo_proposta', 'nome_proposta', 'cliente', 'client_address', 'responsavel', 'status', 'valor_mensal')
    readonly_fields = ('codigo_proposta',)
    show_change_link = True


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_fantasia', 'cnpj_cpf', 'status', 'contato_nome', 'telefone', 'data_cadastro')
    list_filter = ('status', 'data_cadastro')
    search_fields = ('nome_fantasia', 'razao_social', 'cnpj_cpf', 'contato_nome', 'email', 'telefone')
    ordering = ('-data_cadastro',)
    inlines = [ProposalInline]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'codigo_proposta', 'nome_proposta', 'partner', 'cliente',
        'client_address', 'responsavel', 'status', 'motivo_inviavel', 'valor_mensal', 'valor_parceiro'
    )
    list_filter = ('status', 'tecnologia', 'partner')
    search_fields = (
        'codigo_proposta', 'nome_proposta', 'os_numero',
        'partner__nome_fantasia', 'partner__razao_social',
        'cliente__nome_fantasia', 'cliente__razao_social',
        'client_address__login_ixc', 'client_address__agent_circuit_id'
    )
    autocomplete_fields = ('partner', 'cliente', 'client_address', 'responsavel')
    ordering = ('-id',)


@admin.register(ProposalMotivoInviavel)
class ProposalMotivoInviavelAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'status', 'data_cadastro')
    list_filter = ('status',)
    search_fields = ('nome',)
    ordering = ('nome',)
