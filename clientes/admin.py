from django.contrib import admin
from .models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC

# 1. Timeline de mudanças (O que mudou no IXC)
class LogAlteracaoInline(admin.TabularInline):
    model = LogAlteracaoIXC
    extra = 0
    # O agent_circuit_id aparecerá aqui automaticamente quando houver mudança, 
    # pois o campo_alterado registrará o nome do campo.
    readonly_fields = ('data_registro', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    can_delete = False
    verbose_name = "Histórico de Alteração IXC"
    
    def has_add_permission(self, request, obj=None):
        return False

# 2. Endereços e Logins do cliente (Incluso Agent Circuit ID)
class EnderecoInline(admin.TabularInline):
    model = Endereco
    extra = 0
    # Adicionamos o 'agent_circuit_id' logo após o login para facilitar a leitura
    fields = ('login_ixc', 'agent_circuit_id', 'status', 'cidade', 'filial_ixc', 'logradouro')
    # Deixamos o Circuit ID como leitura se você quiser que apenas a API o altere
    # readonly_fields = ('agent_circuit_id',) 

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id_ixc', 'razao_social', 'cnpj_cpf', 'get_status_consolidado')
    # Turbinamos a busca: agora você pode pesquisar pelo ID do Circuito direto na busca de Clientes!
    search_fields = ('razao_social', 'cnpj_cpf', 'id_ixc', 'enderecos__agent_circuit_id')
    list_filter = ('enderecos__status', 'enderecos__filial_ixc')
    
    inlines = [EnderecoInline, LogAlteracaoInline]

    def get_status_consolidado(self, obj):
        tem_ativo = obj.enderecos.filter(status='ativo').exists()
        return "✅ Ativo" if tem_ativo else "❌ Inativo/Cancelado"
    get_status_consolidado.short_description = "Status Geral"

# 3. Monitor da Integração
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

# 4. Registro avulso de logs
@admin.register(LogAlteracaoIXC)
class LogAlteracaoIXCAdmin(admin.ModelAdmin):
    # Aqui também incluímos o login_ixc para saber de qual contrato é a mudança
    list_display = ('data_registro', 'cliente', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    search_fields = ('cliente__razao_social', 'login_ixc', 'valor_novo')
    list_filter = ('campo_alterado', 'data_registro')