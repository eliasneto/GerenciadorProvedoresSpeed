from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("O nome de usuario e obrigatorio")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    username = models.CharField("Usuario", max_length=150, unique=True)
    email = models.EmailField("Endereco de E-mail", unique=True, blank=True, null=True)
    is_gestor = models.BooleanField("E Gestor?", default=False)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]
    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)


class RegistroHistorico(models.Model):
    TIPO_CHOICES = [
        ("comentario", "Comentario Manual"),
        ("anexo", "Documento Anexado"),
        ("sistema", "Log Automatico do Sistema"),
    ]

    arquivado = models.BooleanField(default=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="comentario")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.TextField("Acao/Descricao", blank=True, null=True)
    data = models.DateTimeField("Data", auto_now_add=True)
    arquivo = models.FileField(upload_to="historicos_anexos/%Y/%m/", blank=True, null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-data"]
        verbose_name = "Registro de Historico"
        verbose_name_plural = "Registros de Historico"


class IntegrationAudit(models.Model):
    INTEGRATION_CHOICES = [
        ("logins_ixc", "Logins IXC"),
        ("atendimento_ixc", "Atendimento IXC"),
        ("buscar_fornecedores", "Buscar Fornecedores"),
    ]

    ACTION_CHOICES = [
        ("download_modelo", "Download do Modelo"),
        ("importacao_planilha", "Importacao da Planilha"),
        ("execucao_integracao", "Execucao da Integracao"),
    ]

    integration = models.CharField("Integracao", max_length=40, choices=INTEGRATION_CHOICES)
    action = models.CharField("Acao", max_length=40, choices=ACTION_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="integration_audits",
        verbose_name="Usuario",
    )
    arquivo_nome = models.CharField("Arquivo", max_length=255, blank=True, null=True)
    total_registros = models.PositiveIntegerField("Total de Registros", default=0)
    total_sucessos = models.PositiveIntegerField("Total de Sucessos", default=0)
    total_erros = models.PositiveIntegerField("Total de Erros", default=0)
    detalhes_json = models.JSONField("Detalhes", blank=True, null=True, default=dict)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Log de Integracao"
        verbose_name_plural = "Logs de Integracoes"

    def __str__(self):
        return f"{self.get_integration_display()} - {self.get_action_display()} - {self.criado_em:%d/%m/%Y %H:%M}"


class IntegrationAuditItem(models.Model):
    STATUS_CHOICES = [
        ("importado", "Importado"),
        ("sucesso", "Sucesso"),
        ("erro", "Erro"),
    ]

    audit = models.ForeignKey(
        IntegrationAudit,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Log",
    )
    linha_numero = models.PositiveIntegerField("Linha", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default="importado")
    mensagem = models.TextField("Mensagem", blank=True, null=True)
    dados_json = models.JSONField("Dados Importados", blank=True, null=True, default=dict)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Item do Log de Integracao"
        verbose_name_plural = "Itens do Log de Integracao"
