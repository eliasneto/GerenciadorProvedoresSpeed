from django.conf import settings
from django.db import models

from clientes.models import HistoricoSincronizacao, LogAlteracaoIXC
from core.models import (
    EmailCotacaoRespostaImportacao,
    EmailCotacaoRespostaSync,
    IntegrationAudit,
    IntegrationAuditItem,
    RegistroHistorico,
)


class LoginAuditoria(models.Model):
    ACAO_CHOICES = [
        ("login_sucesso", "Login com sucesso"),
        ("login_falha", "Falha no login"),
        ("logout", "Logout"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_login",
        verbose_name="Usuario",
    )
    username_informado = models.CharField("Usuario informado", max_length=150, blank=True)
    acao = models.CharField("Acao", max_length=20, choices=ACAO_CHOICES)
    sucesso = models.BooleanField("Sucesso", default=False)
    endereco_ip = models.GenericIPAddressField("Endereco IP", blank=True, null=True)
    user_agent = models.CharField("User Agent", max_length=500, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Login"
        verbose_name_plural = "Auditorias de Login"

    def __str__(self):
        usuario = self.username_informado or getattr(self.usuario, "username", "") or "desconhecido"
        return f"{self.get_acao_display()} - {usuario} - {self.criado_em:%d/%m/%Y %H:%M}"


class RestoreBackupAuditoria(models.Model):
    ORIGEM_CHOICES = [
        ("servidor", "Backup do servidor"),
        ("upload", "Upload manual"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_restore_backup",
        verbose_name="Usuario",
    )
    origem = models.CharField("Origem", max_length=20, choices=ORIGEM_CHOICES)
    arquivo_nome = models.CharField("Arquivo", max_length=255)
    sucesso = models.BooleanField("Sucesso", default=False)
    media_restaurada = models.BooleanField("Midia restaurada", default=False)
    endereco_ip = models.GenericIPAddressField("Endereco IP", blank=True, null=True)
    user_agent = models.CharField("User Agent", max_length=500, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Restore de Backup"
        verbose_name_plural = "Auditorias de Restore de Backup"

    def __str__(self):
        return f"{self.arquivo_nome} - {'sucesso' if self.sucesso else 'erro'} - {self.criado_em:%d/%m/%Y %H:%M}"


class CotacaoStatusAuditoria(models.Model):
    ORIGEM_CHOICES = [
        ("alteracao_individual", "Alteracao individual"),
        ("alteracao_lote", "Alteracao em lote"),
        ("conversao_viavel", "Conversao de cotacao viavel"),
        ("fechamento_automatico", "Fechamento automatico de outra cotacao"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_status_cotacao",
        verbose_name="Usuario",
    )
    proposal = models.ForeignKey(
        "partners.Proposal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias_status",
        verbose_name="Cotacao",
    )
    codigo_cotacao = models.CharField("Codigo da cotacao", max_length=30, blank=True)
    codigo_lote = models.CharField("Codigo do lote", max_length=30, blank=True)
    parceiro_nome = models.CharField("Parceiro", max_length=200, blank=True)
    cliente_nome = models.CharField("Cliente", max_length=255, blank=True)
    endereco_referencia = models.CharField("Endereco", max_length=255, blank=True)
    status_anterior = models.CharField("Status anterior", max_length=30)
    status_novo = models.CharField("Status novo", max_length=30)
    origem = models.CharField("Origem", max_length=30, choices=ORIGEM_CHOICES)
    integrou_ixc = models.BooleanField("Integrou com IXC", default=False)
    endereco_ip = models.GenericIPAddressField("Endereco IP", blank=True, null=True)
    user_agent = models.CharField("User Agent", max_length=500, blank=True)
    detalhes = models.TextField("Detalhes", blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Status da Cotacao"
        verbose_name_plural = "Auditorias de Status das Cotacoes"

    def __str__(self):
        return (
            f"{self.codigo_cotacao or 'cotacao'} - "
            f"{self.status_anterior} -> {self.status_novo} - "
            f"{self.criado_em:%d/%m/%Y %H:%M}"
        )


class RegistroHistoricoAuditoria(RegistroHistorico):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Registro de Historico"
        verbose_name_plural = "Registros de Historico"


class EmailCotacaoRespostaSyncAuditoria(EmailCotacaoRespostaSync):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Sync de respostas por e-mail da cotacao"
        verbose_name_plural = "Syncs de respostas por e-mail da cotacao"


class EmailCotacaoRespostaImportacaoAuditoria(EmailCotacaoRespostaImportacao):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Resposta de e-mail importada"
        verbose_name_plural = "Respostas de e-mail importadas"


class IntegrationAuditAuditoria(IntegrationAudit):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Log de Integracao"
        verbose_name_plural = "Logs de Integracoes"


class IntegrationAuditItemAuditoria(IntegrationAuditItem):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Item do Log de Integracao"
        verbose_name_plural = "Itens do Log de Integracao"


class DesativacaoAtendimentoIXCAuditoria(IntegrationAudit):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Desativacao de Atendimento IXC"
        verbose_name_plural = "Desativacao de Atendimentos IXC"


class HistoricoSincronizacaoAuditoria(HistoricoSincronizacao):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Historico de Sincronizacao"
        verbose_name_plural = "Historico de Sincronizacoes"


class LogAlteracaoIXCAuditoria(LogAlteracaoIXC):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Log de Alteracao IXC"
        verbose_name_plural = "Log de Alteracoes IXC"
