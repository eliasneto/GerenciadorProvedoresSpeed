import subprocess
from django.contrib import admin, messages
from .models import Cliente, Endereco, HistoricoSincronizacao, LogAlteracaoIXC, EnderecoExcluido, ClienteExcluido

# 1. Timeline de mudanças (O que mudou no IXC)
class LogAlteracaoInline(admin.TabularInline):
    model = LogAlteracaoIXC
    extra = 0
    readonly_fields = ('data_registro', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    can_delete = False
    verbose_name = "Histórico de Alteração IXC"
    
    def has_add_permission(self, request, obj=None):
        return False

# 2. Endereços e Logins do cliente
class EnderecoInline(admin.TabularInline):
    model = Endereco
    extra = 0
    fields = ('login_ixc', 'agent_circuit_id', 'status', 'cidade', 'filial_ixc', 'logradouro')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('id_ixc', 'razao_social', 'cnpj_cpf', 'get_status_consolidado')
    search_fields = ('razao_social', 'cnpj_cpf', 'id_ixc', 'enderecos__agent_circuit_id')
    list_filter = ('enderecos__status', 'enderecos__filial_ixc')
    inlines = [EnderecoInline, LogAlteracaoInline]

    def get_status_consolidado(self, obj):
        tem_ativo = obj.enderecos.filter(status='ativo').exists()
        return "✅ Ativo" if tem_ativo else "❌ Inativo/Cancelado"
    get_status_consolidado.short_description = "Status Geral"

# 3. Monitor da Integração (COM BOTÕES DE PLAY E STOP)
@admin.register(HistoricoSincronizacao)
class HistoricoSincronizacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_inicio', 'tipo', 'origem', 'executado_por', 'status', 'registros_processados', 'tempo_execucao')
    list_filter = ('status', 'tipo', 'origem')
    readonly_fields = ('data_inicio', 'data_fim', 'status', 'origem', 'executado_por', 'registros_processados', 'detalhes')
    
    # --- 🚀 AÇÕES PARA RODAR OS SCRIPTS PELO ADMIN ---
    actions = ['rodar_carga_total', 'rodar_incremental', 'rodar_faxina', 'parar_sincronizacao']

    @admin.action(description="🚀 Rodar CARGA TOTAL agora")
    def rodar_carga_total(self, request, queryset):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api.py", "manual"])
        self.message_user(request, "Carga Total iniciada em segundo plano!", messages.SUCCESS)

    @admin.action(description="⚡ Rodar INCREMENTAL agora")
    def rodar_incremental(self, request, queryset):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api_incremental.py", "manual"])
        self.message_user(request, "Sincronização Incremental iniciada!", messages.SUCCESS)

    @admin.action(description="🧹 Rodar FAXINA (Limpeza) agora")
    def rodar_faxina(self, request, queryset):
        subprocess.Popen(["python", "scripts/integracoes/ixc_faxina.py", "manual"])
        self.message_user(request, "Rotina de Faxina iniciada!", messages.SUCCESS)

    @admin.action(description="🛑 PARAR processos selecionados")
    def parar_sincronizacao(self, request, queryset):
        # Marcamos como "STOP" para o script ler e interromper a execução
        vivos = queryset.filter(status='rodando')
        if vivos.exists():
            vivos.update(detalhes="STOP")
            self.message_user(request, f"Sinal de parada enviado para {vivos.count()} processo(s).", messages.WARNING)
        else:
            self.message_user(request, "Nenhum processo em execução foi selecionado.", messages.ERROR)

    def tempo_execucao(self, obj):
        if obj.data_fim:
            diff = obj.data_fim - obj.data_inicio
            return f"{diff.seconds} segundos"
        return "Em execução..."

# 4. Registro avulso de logs
@admin.register(LogAlteracaoIXC)
class LogAlteracaoIXCAdmin(admin.ModelAdmin):
    list_display = ('data_registro', 'cliente', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    search_fields = ('cliente__razao_social', 'login_ixc', 'valor_novo')
    list_filter = ('campo_alterado', 'data_registro')

# 5. Lixo de Clientes e Endereços
class EnderecoExcluidoInline(admin.TabularInline):
    model = EnderecoExcluido
    extra = 0
    readonly_fields = ('login_ixc', 'agent_circuit_id', 'detalhes_json')
    can_delete = False

@admin.register(ClienteExcluido)
class ClienteExcluidoAdmin(admin.ModelAdmin):
    list_display = ('id_ixc', 'razao_social', 'cnpj_cpf', 'data_exclusao')
    search_fields = ('razao_social', 'cnpj_cpf', 'id_ixc')
    readonly_fields = ('id_ixc', 'razao_social', 'cnpj_cpf', 'dados_completos_json', 'data_exclusao')
    inlines = [EnderecoExcluidoInline]