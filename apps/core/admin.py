from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    EmailCotacaoRespostaImportacao,
    EmailCotacaoRespostaSync,
    IntegrationAudit,
    IntegrationAuditItem,
    RegistroHistorico,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    change_password_form = None
    fieldsets = (
        (None, {"fields": ("username",)}),
        ("Informacoes Pessoais", {"fields": ("first_name", "last_name", "email")}),
        ("Speed: Permissoes Especiais", {"fields": ("is_gestor", "is_active", "is_staff", "is_superuser")}),
        ("Grupos e Acessos", {"fields": ("groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Configuracoes Speed",
            {
                "classes": ("wide",),
                "fields": ("is_gestor",),
            },
        ),
    )
    list_display = ("username", "email", "is_gestor", "is_staff", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)
    readonly_fields = ("last_login", "date_joined")

    def get_urls(self):
        urls = super().get_urls()
        return [u for u in urls if u.name and "password" not in u.name]


@admin.register(RegistroHistorico)
class RegistroHistoricoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "data")
    list_filter = ("tipo", "data")
    search_fields = ("usuario__username", "acao")


@admin.register(EmailCotacaoRespostaSync)
class EmailCotacaoRespostaSyncAdmin(admin.ModelAdmin):
    list_display = ("mailbox_email", "ativo", "ultima_sincronizacao_em", "atualizado_em")
    readonly_fields = ("atualizado_em", "ultima_sincronizacao_em", "ultimo_erro", "inbox_delta_link")


@admin.register(EmailCotacaoRespostaImportacao)
class EmailCotacaoRespostaImportacaoAdmin(admin.ModelAdmin):
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


@admin.register(IntegrationAudit)
class IntegrationAuditAdmin(admin.ModelAdmin):
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
    readonly_fields = (
        "integration",
        "action",
        "usuario",
        "arquivo_nome",
        "total_registros",
        "total_sucessos",
        "total_erros",
        "detalhes_json",
        "criado_em",
    )
    inlines = [IntegrationAuditItemInline]


@admin.register(IntegrationAuditItem)
class IntegrationAuditItemAdmin(admin.ModelAdmin):
    list_display = ("audit", "linha_numero", "status", "criado_em")
    list_filter = ("status", "criado_em", "audit__integration")
    search_fields = ("audit__arquivo_nome", "mensagem")
    readonly_fields = ("audit", "linha_numero", "status", "mensagem", "dados_json", "criado_em")
