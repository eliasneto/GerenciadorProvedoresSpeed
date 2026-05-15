import subprocess

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.http import urlencode

from clientes.sync_utils import buscar_rotina_em_execucao, descrever_rotina_em_execucao
from core.admin_integration_exports import IntegrationAuditExportAdminMixin
from core.models import IntegrationAuditItem

from .models import (
    CotacaoStatusAuditoria,
    EmailCotacaoRespostaImportacaoAuditoria,
    EmailCotacaoRespostaSyncAuditoria,
    HistoricoSincronizacaoAuditoria,
    IntegrationAuditAuditoria,
    IntegrationAuditItemAuditoria,
    LoginAuditoria,
    RestoreBackupAuditoria,
    LogAlteracaoIXCAuditoria,
    RegistroHistoricoAuditoria,
)


@admin.register(RegistroHistoricoAuditoria)
class RegistroHistoricoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "data")
    list_filter = ("tipo", "data")
    search_fields = ("usuario__username", "acao")


@admin.register(LoginAuditoria)
class LoginAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "acao", "sucesso", "username_informado", "usuario", "endereco_ip")
    list_filter = ("acao", "sucesso", "criado_em")
    search_fields = ("username_informado", "usuario__username", "endereco_ip", "detalhes")
    readonly_fields = ("usuario", "username_informado", "acao", "sucesso", "endereco_ip", "user_agent", "detalhes", "criado_em")


@admin.register(RestoreBackupAuditoria)
class RestoreBackupAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "arquivo_nome", "origem", "sucesso", "media_restaurada", "usuario", "endereco_ip")
    list_filter = ("origem", "sucesso", "media_restaurada", "criado_em")
    search_fields = ("arquivo_nome", "usuario__username", "endereco_ip", "detalhes")
    readonly_fields = ("usuario", "origem", "arquivo_nome", "sucesso", "media_restaurada", "endereco_ip", "user_agent", "detalhes", "criado_em")


@admin.register(CotacaoStatusAuditoria)
class CotacaoStatusAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "criado_em",
        "codigo_cotacao",
        "parceiro_nome",
        "cliente_nome",
        "status_anterior",
        "status_novo",
        "origem",
        "integrou_ixc",
        "usuario",
    )
    list_filter = ("origem", "integrou_ixc", "status_anterior", "status_novo", "criado_em")
    search_fields = (
        "codigo_cotacao",
        "codigo_lote",
        "parceiro_nome",
        "cliente_nome",
        "endereco_referencia",
        "usuario__username",
        "detalhes",
    )
    readonly_fields = (
        "usuario",
        "proposal",
        "codigo_cotacao",
        "codigo_lote",
        "parceiro_nome",
        "cliente_nome",
        "endereco_referencia",
        "status_anterior",
        "status_novo",
        "origem",
        "integrou_ixc",
        "endereco_ip",
        "user_agent",
        "detalhes",
        "criado_em",
    )


@admin.register(EmailCotacaoRespostaSyncAuditoria)
class EmailCotacaoRespostaSyncAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("mailbox_email", "ativo", "ultima_sincronizacao_em", "atualizado_em")
    readonly_fields = ("atualizado_em", "ultima_sincronizacao_em", "ultimo_erro", "inbox_delta_link")


@admin.register(EmailCotacaoRespostaImportacaoAuditoria)
class EmailCotacaoRespostaImportacaoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("proposal", "remetente", "assunto", "recebido_em", "importado_em")
    list_filter = ("recebido_em", "importado_em")
    search_fields = ("proposal__codigo_proposta", "assunto", "remetente", "graph_message_id", "internet_message_id")
    readonly_fields = (
        "proposal",
        "historico",
        "graph_message_id",
        "internet_message_id",
        "assunto",
        "remetente",
        "recebido_em",
        "importado_em",
    )


class IntegrationAuditItemInline(admin.TabularInline):
    model = IntegrationAuditItem
    extra = 0
    can_delete = False
    readonly_fields = ("linha_numero", "status", "mensagem", "dados_json", "criado_em")


@admin.register(IntegrationAuditAuditoria)
class IntegrationAuditAuditoriaAdmin(IntegrationAuditExportAdminMixin, admin.ModelAdmin):
    list_display = (
        "integration",
        "action",
        "usuario",
        "arquivo_nome",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "criado_em",
    )
    list_filter = ("integration", "action", "criado_em")
    search_fields = ("usuario__username", "arquivo_nome")
    fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    readonly_fields = IntegrationAuditExportAdminMixin.integration_audit_fields
    inlines = [IntegrationAuditItemInline]


@admin.register(IntegrationAuditItemAuditoria)
class IntegrationAuditItemAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("audit", "linha_numero", "status", "criado_em")
    list_filter = ("status", "criado_em", "audit__integration")
    search_fields = ("audit__arquivo_nome", "mensagem")
    readonly_fields = ("audit", "linha_numero", "status", "mensagem", "dados_json", "criado_em")


@admin.register(LogAlteracaoIXCAuditoria)
class LogAlteracaoIXCAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "login_ixc", "campo_alterado", "data_registro")
    list_filter = ("campo_alterado", "data_registro")
    search_fields = ("cliente__razao_social", "cliente__nome_fantasia", "login_ixc", "campo_alterado", "valor_antigo", "valor_novo")
    autocomplete_fields = ("cliente",)
    ordering = ("-data_registro",)


@admin.register(HistoricoSincronizacaoAuditoria)
class HistoricoSincronizacaoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "data_inicio", "tipo", "origem", "executado_por", "status", "registros_processados", "tempo_execucao")
    list_filter = ("status", "tipo", "origem")
    readonly_fields = ("data_inicio", "data_fim", "status", "origem", "executado_por", "registros_processados", "detalhes")
    change_list_template = "admin/historico_botoes.html"
    change_form_template = "admin/historico_sincronizacao_change_form.html"
    actions = ["parar_sincronizacao"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("rodar-carga-total/", self.admin_site.admin_view(self.btn_rodar_carga_total), name="rodar-carga-total"),
            path("rodar-incremental/", self.admin_site.admin_view(self.btn_rodar_incremental), name="rodar-incremental"),
            path("rodar-faxina/", self.admin_site.admin_view(self.btn_rodar_faxina), name="rodar-faxina"),
            path("rodar-os-comercial-lastmile/", self.admin_site.admin_view(self.btn_rodar_os_comercial_lastmile), name="rodar-os-comercial-lastmile"),
            path("parar-os-comercial-lastmile/", self.admin_site.admin_view(self.btn_parar_os_comercial_lastmile), name="parar-os-comercial-lastmile"),
            path("rodar-respostas-email-cotacao/", self.admin_site.admin_view(self.btn_rodar_respostas_email_cotacao), name="rodar-respostas-email-cotacao"),
            path("rodar-backup/", self.admin_site.admin_view(self.btn_rodar_backup), name="rodar-backup"),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        rotina_os_lastmile_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        extra_context.update({
            "rotina_os_lastmile_ativa": rotina_os_lastmile_ativa,
            "rotina_os_lastmile_descricao": (
                descrever_rotina_em_execucao("os_comercial_lastmile", rotina_os_lastmile_ativa)
                if rotina_os_lastmile_ativa else ""
            ),
        })
        return super().changelist_view(request, extra_context=extra_context)

    def btn_rodar_carga_total(self, request):
        rotina_ativa = buscar_rotina_em_execucao("total")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("total", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_api.py", "manual", request.user.username])
        self.message_user(request, "Carga total iniciada em segundo plano.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_incremental(self, request):
        rotina_ativa = buscar_rotina_em_execucao("incremental")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("incremental", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_api_incremental.py", "manual", request.user.username])
        self.message_user(request, "Sincronizacao incremental iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_faxina(self, request):
        rotina_ativa = buscar_rotina_em_execucao("faxina")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("faxina", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../")
        subprocess.Popen(["python", "scripts/integracoes/ixc_faxina.py", "manual", request.user.username])
        self.message_user(request, "Rotina de faxina iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../")

    def btn_rodar_os_comercial_lastmile(self, request):
        rotina_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        if rotina_ativa:
            self.message_user(
                request,
                descrever_rotina_em_execucao("os_comercial_lastmile", rotina_ativa),
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

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

    def btn_parar_os_comercial_lastmile(self, request):
        rotina_ativa = buscar_rotina_em_execucao("os_comercial_lastmile")
        if not rotina_ativa:
            self.message_user(
                request,
                "Nenhuma rotina de OS Comercial | Lastmile em execucao foi encontrada.",
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

        rotina_ativa.detalhes = "STOP"
        rotina_ativa.save(update_fields=["detalhes"])
        self.message_user(
            request,
            f"Sinal de parada enviado para a rotina de OS Comercial | Lastmile #{rotina_ativa.id}.",
            messages.WARNING,
        )
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "os_comercial_lastmile"}))

    def btn_rodar_backup(self, request):
        rotina_ativa = buscar_rotina_em_execucao("backup")
        if rotina_ativa:
            self.message_user(request, descrever_rotina_em_execucao("backup", rotina_ativa), messages.WARNING)
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "backup"}))
        subprocess.Popen(["python", "scripts/integracoes/backup_manual.py", "manual", request.user.username])
        self.message_user(request, "Backup manual iniciado em segundo plano.", messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "backup"}))

    def btn_rodar_respostas_email_cotacao(self, request):
        rotina_ativa = buscar_rotina_em_execucao("email_respostas_cotacao")
        if rotina_ativa:
            self.message_user(
                request,
                descrever_rotina_em_execucao("email_respostas_cotacao", rotina_ativa),
                messages.WARNING,
            )
            return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "email_respostas_cotacao"}))

        subprocess.Popen([
            "python",
            "scripts/integracoes/sincronizar_respostas_email_cotacao.py",
            "manual",
            request.user.username,
        ])
        self.message_user(request, "Sincronizacao manual das respostas de e-mail iniciada.", messages.SUCCESS)
        return HttpResponseRedirect("../?" + urlencode({"tipo__exact": "email_respostas_cotacao"}))

    @admin.action(description="PARAR processos selecionados")
    def parar_sincronizacao(self, request, queryset):
        vivos = queryset.filter(status="rodando")
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
