from django.contrib import admin
from .models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC

# 1. Timeline de mudanças (O que mudou no IXC)
class LogAlteracaoInline(admin.TabularInline):
    model = LogAlteracaoIXC
    extra = 0
    readonly_fields = ('data_registro', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    can_delete = False
    verbose_name = "Histórico de Alteração IXC"
    
    # Impede que alguém edite o log manualmente pelo admin
    def has_add_permission(self, request, obj=None):
        return False

# 2. Endereços e Logins do cliente
class EnderecoInline(admin.TabularInline):
    model = Endereco
    extra = 0
    fields = ('login_ixc', 'status', 'cidade', 'filial_ixc', 'logradouro')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id_ixc', 'razao_social', 'cnpj_cpf', 'get_status_consolidado')
    search_fields = ('razao_social', 'cnpj_cpf', 'id_ixc')
    list_filter = ('enderecos__status', 'enderecos__filial_ixc')
    
    # Adicionamos os dois Inlines aqui!
    inlines = [EnderecoInline, LogAlteracaoInline]

    def get_status_consolidado(self, obj):
        # Mostra se o cliente tem algum contrato ativo de forma visual
        tem_ativo = obj.enderecos.filter(status='ativo').exists()
        return "✅ Ativo" if tem_ativo else "❌ Inativo/Cancelado"
    get_status_consolidado.short_description = "Status Geral"

# 3. Monitor da Integração (Para ver se o robô deu erro ou sucesso)
@admin.register(HistoricoSincronizacao)
class HistoricoSincronizacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_inicio', 'status', 'registros_processados', 'tempo_execucao')
    list_filter = ('status',)
    readonly_fields = ('data_inicio', 'data_fim', 'status', 'registros_processados', 'detalhes')

    def tempo_execucao(self, obj):
        if obj.data_fim:
            diff = obj.data_fim - obj.data_inicio
            return f"{diff.seconds} segundos"
        return "Em execução..."

# 4. Registro avulso de logs (Caso queira pesquisar por um log específico)
@admin.register(LogAlteracaoIXC)
class LogAlteracaoIXCAdmin(admin.ModelAdmin):
    list_display = ('data_registro', 'cliente', 'campo_alterado', 'valor_antigo', 'valor_novo')
    search_fields = ('cliente__razao_social', 'login_ixc')
    list_filter = ('campo_alterado', 'data_registro')