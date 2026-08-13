from django.conf import settings
from django.db import models

from apps.clientes.models import HistoricoSincronizacao, LogAlteracaoIXC
from apps.core.models import (
    CotacaoStatusAuditoria as CotacaoStatusAuditoriaCore,
    EmailCotacaoRespostaImportacao,
    EmailCotacaoRespostaSync,
    IntegrationAudit,
    IntegrationAuditItem,
    RegistroHistorico,
    RestoreBackupAuditoria as RestoreBackupAuditoriaCore,
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


class RestoreBackupAuditoria(RestoreBackupAuditoriaCore):
    """Proxy de exibicao: dado e regra moraram em apps.core (PO-036, ADR-007 item 8),
    mantido aqui apenas para preservar a secao do Django Admin onde este log
    ja era exibido (mesmo precedente do IntegrationAudit/IntegrationAuditAuditoria)."""

    class Meta:
        proxy = True
        app_label = "auditoria"
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Restore de Backup"
        verbose_name_plural = "Auditorias de Restore de Backup"


class CotacaoStatusAuditoria(CotacaoStatusAuditoriaCore):
    """Proxy de exibicao: dado e regra moraram em apps.core (PO-036, ADR-007 item 8),
    mantido aqui apenas para preservar a secao do Django Admin onde este log
    ja era exibido (mesmo precedente do IntegrationAudit/IntegrationAuditAuditoria)."""

    class Meta:
        proxy = True
        app_label = "auditoria"
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Status da Cotacao"
        verbose_name_plural = "Auditorias de Status das Cotacoes"


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


class CadastroClienteIXCAuditoria(IntegrationAudit):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Cadastro de Cliente IXC"
        verbose_name_plural = "Cadastro de Clientes IXC"


class EdicaoLoginIXCAuditoria(IntegrationAudit):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Edicao de Login IXC"
        verbose_name_plural = "Edicao de Logins IXC"


class EdicaoAtendimentoIXCAuditoria(IntegrationAudit):
    class Meta:
        proxy = True
        app_label = "auditoria"
        verbose_name = "Edicao de Atendimento IXC"
        verbose_name_plural = "Edicao de Atendimentos IXC"


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
