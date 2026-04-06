import subprocess
from django.urls import path
from django.http import HttpResponseRedirect
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
    fields = ('login_ixc', 'agent_circuit_id', 'status', 'cidade', 'cidade_id_ixc', 'filial_ixc', 'logradouro')

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
    
    # Adicionamos o template customizado para os botões aparecerem
    change_list_template = "admin/historico_botoes.html"

    # Mantemos APENAS a ação de Parar no dropdown (já que ela precisa de seleção)
    actions = ['parar_sincronizacao']

    # --- 🔗 ROTAS PARA OS BOTÕES FIXOS ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('rodar-carga-total/', self.admin_site.admin_view(self.btn_rodar_carga_total), name='rodar-carga-total'),
            path('rodar-incremental/', self.admin_site.admin_view(self.btn_rodar_incremental), name='rodar-incremental'),
            path('rodar-faxina/', self.admin_site.admin_view(self.btn_rodar_faxina), name='rodar-faxina'),
        ]
        return custom_urls + urls

    # --- 🚀 FUNÇÕES DOS BOTÕES (Sem precisar de QuerySet) ---
    def btn_rodar_carga_total(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api.py", "manual", request.user.username])
        self.message_user(request, "🚀 Carga Total iniciada em segundo plano!", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_incremental(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api_incremental.py", "manual", request.user.username])
        self.message_user(request, "⚡ Sincronização Incremental iniciada!", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_faxina(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_faxina.py", "manual", request.user.username])
        self.message_user(request, "🧹 Rotina de Faxina iniciada!", messages.SUCCESS)
        return HttpResponseRedirect("../")

    # --- 🛑 AÇÃO DE PARAR (Mantida no Dropdown) ---
    @admin.action(description="🛑 PARAR processos selecionados")
    def parar_sincronizacao(self, request, queryset):
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


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'login_ixc', 'agent_circuit_id', 'cidade', 'cidade_id_ixc', 'estado', 'status', 'filial_ixc', 'principal')
    list_filter = ('status', 'estado', 'filial_ixc', 'principal')
    search_fields = ('cliente__razao_social', 'cliente__nome_fantasia', 'login_ixc', 'agent_circuit_id', 'logradouro', 'cidade', 'cidade_id_ixc')
    autocomplete_fields = ('cliente',)
    ordering = ('cliente__razao_social', 'logradouro')


@admin.register(LogAlteracaoIXC)
class LogAlteracaoIXCAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'login_ixc', 'campo_alterado', 'data_registro')
    list_filter = ('campo_alterado', 'data_registro')
    search_fields = ('cliente__razao_social', 'cliente__nome_fantasia', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    autocomplete_fields = ('cliente',)
    ordering = ('-data_registro',)


class EnderecoExcluidoInline(admin.TabularInline):
    model = EnderecoExcluido
    extra = 0
    can_delete = False
    readonly_fields = ('login_ixc', 'agent_circuit_id', 'detalhes_json')


@admin.register(ClienteExcluido)
class ClienteExcluidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_ixc', 'razao_social', 'cnpj_cpf', 'data_exclusao')
    search_fields = ('id_ixc', 'razao_social', 'cnpj_cpf')
    readonly_fields = ('id_ixc', 'razao_social', 'cnpj_cpf', 'dados_completos_json', 'data_exclusao')
    inlines = [EnderecoExcluidoInline]
    ordering = ('-data_exclusao',)


@admin.register(EnderecoExcluido)
class EnderecoExcluidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente_excluido', 'login_ixc', 'agent_circuit_id')
    search_fields = ('cliente_excluido__razao_social', 'login_ixc', 'agent_circuit_id')
    readonly_fields = ('cliente_excluido', 'login_ixc', 'agent_circuit_id', 'detalhes_json')
    ordering = ('-id',)
