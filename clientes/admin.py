import subprocess

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.http import urlencode

from .models import (
    Cliente,
    ClienteExcluido,
    Endereco,
    EnderecoExcluido,
    HistoricoSincronizacao,
    LogAlteracaoIXC,
)


class LogAlteracaoInline(admin.TabularInline):
    model = LogAlteracaoIXC
    extra = 0
    readonly_fields = ('data_registro', 'login_ixc', 'campo_alterado', 'valor_antigo', 'valor_novo')
    can_delete = False
    verbose_name = "Historico de Alteracao IXC"

    def has_add_permission(self, request, obj=None):
        return False


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
        return "Ativo" if tem_ativo else "Inativo/Cancelado"

    get_status_consolidado.short_description = "Status Geral"


@admin.register(HistoricoSincronizacao)
class HistoricoSincronizacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_inicio', 'tipo', 'origem', 'executado_por', 'status', 'registros_processados', 'tempo_execucao')
    list_filter = ('status', 'tipo', 'origem')
    readonly_fields = ('data_inicio', 'data_fim', 'status', 'origem', 'executado_por', 'registros_processados', 'detalhes')
    change_list_template = "admin/historico_botoes.html"
    actions = ['parar_sincronizacao']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('rodar-carga-total/', self.admin_site.admin_view(self.btn_rodar_carga_total), name='rodar-carga-total'),
            path('rodar-incremental/', self.admin_site.admin_view(self.btn_rodar_incremental), name='rodar-incremental'),
            path('rodar-faxina/', self.admin_site.admin_view(self.btn_rodar_faxina), name='rodar-faxina'),
            path('rodar-os-comercial-lastmile/', self.admin_site.admin_view(self.btn_rodar_os_comercial_lastmile), name='rodar-os-comercial-lastmile'),
        ]
        return custom_urls + urls

    def btn_rodar_carga_total(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api.py", "manual", request.user.username])
        self.message_user(request, "Carga total iniciada em segundo plano.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_incremental(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_api_incremental.py", "manual", request.user.username])
        self.message_user(request, "Sincronizacao incremental iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_faxina(self, request):
        subprocess.Popen(["python", "scripts/integracoes/ixc_faxina.py", "manual", request.user.username])
        self.message_user(request, "Rotina de faxina iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_os_comercial_lastmile(self, request):
        comando = ["python", "scripts/integracoes/ixc_os_comercial_lastmile.py", "manual", request.user.username]

        cliente_local_id = (request.GET.get("cliente_local_id") or "").strip()
        cliente_ixc_id = (request.GET.get("cliente_ixc_id") or "").strip()
        os_alterada_desde = (request.GET.get("os_alterada_desde") or "").strip()
        os_alterada_nos_ultimos_dias = (request.GET.get("os_alterada_nos_ultimos_dias") or "").strip()

        if cliente_local_id:
            comando.append(f"--cliente-local-id={cliente_local_id}")
        if cliente_ixc_id:
            comando.append(f"--cliente-ixc-id={cliente_ixc_id}")
        if os_alterada_desde:
            comando.append(f"--os-alterada-desde={os_alterada_desde}")
        if os_alterada_nos_ultimos_dias:
            comando.append(f"--os-alterada-nos-ultimos-dias={os_alterada_nos_ultimos_dias}")

        subprocess.Popen(comando)

        detalhes = []
        if cliente_local_id:
            detalhes.append(f"cliente local {cliente_local_id}")
        if cliente_ixc_id:
            detalhes.append(f"cliente IXC {cliente_ixc_id}")
        if os_alterada_desde:
            detalhes.append(f"O.S. alterada desde {os_alterada_desde}")
        if os_alterada_nos_ultimos_dias:
            detalhes.append(f"O.S. alterada nos ultimos {os_alterada_nos_ultimos_dias} dias")

        mensagem = "Rotina de OS Comercial | Lastmile iniciada."
        if detalhes:
            mensagem += " Filtros: " + ", ".join(detalhes) + "."

        self.message_user(request, mensagem, messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

    @admin.action(description="PARAR processos selecionados")
    def parar_sincronizacao(self, request, queryset):
        vivos = queryset.filter(status='rodando')
        if vivos.exists():
            vivos.update(detalhes="STOP")
            self.message_user(request, f"Sinal de parada enviado para {vivos.count()} processo(s).", messages.WARNING)
        else:
            self.message_user(request, "Nenhum processo em execucao foi selecionado.", messages.ERROR)

    def tempo_execucao(self, obj):
        if obj.data_fim:
            diff = obj.data_fim - obj.data_inicio
            return f"{diff.seconds} segundos"
        return "Em execucao..."


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
