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
    """RN-029: historico de comentario/anexo/log automatico, vinculado a
    qualquer model via GenericForeignKey.

    RN-041 acrescentou `rotulo`/`valor_anterior`/`valor_novo`/`setor_nome`,
    usados somente pelo tipo `sistema`, para exibir a alteracao em formato
    De/Para estruturado no modal de historico (RN-029), em vez de somente a
    frase livre em `acao`. Todos opcionais e sem migracao retroativa —
    somente registro antigo (anterior a esta estruturacao) continua sem
    esses campos, e o template mantem `acao` como frase nesse caso.

    RN-041 (ampliada): quando mais de um campo muda no mesmo submit (ex.:
    cascata Setor->Status, ver `apps/leads/services.py::registrar_historico_alteracao_rede`),
    cada campo gera o seu proprio registro estruturado — nunca um unico
    registro com frase combinada."""

    TIPO_CHOICES = [
        ("comentario", "Comentario Manual"),
        ("anexo", "Documento Anexado"),
        ("sistema", "Log Automatico do Sistema"),
    ]

    arquivado = models.BooleanField(default=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="comentario")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.TextField("Acao/Descricao", blank=True, null=True)
    rotulo = models.CharField("Rotulo", max_length=100, blank=True, null=True)
    valor_anterior = models.TextField("Valor anterior", blank=True, null=True)
    valor_novo = models.TextField("Valor novo", blank=True, null=True)
    setor_nome = models.CharField("Setor", max_length=150, blank=True, null=True)
    data = models.DateTimeField("Data", auto_now_add=True)
    arquivo = models.FileField(upload_to="historicos_anexos/%Y/%m/", blank=True, null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["-data"]
        verbose_name = "Registro de Historico"
        verbose_name_plural = "Registros de Historico"


class EmailCotacaoRespostaSync(models.Model):
    mailbox_email = models.EmailField("Caixa monitorada", unique=True)
    inbox_delta_link = models.TextField("DeltaLink da Inbox", blank=True, null=True)
    ultima_sincronizacao_em = models.DateTimeField("Ultima sincronizacao", blank=True, null=True)
    ultimo_erro = models.TextField("Ultimo erro", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Sync de respostas por e-mail da cotacao"
        verbose_name_plural = "Syncs de respostas por e-mail da cotacao"

    def __str__(self):
        return self.mailbox_email

    @classmethod
    def obter_configuracao(cls, mailbox_email):
        mailbox_normalizado = (mailbox_email or "").strip().lower()
        if not mailbox_normalizado:
            raise ValueError("Nao foi possivel determinar a caixa de e-mail monitorada para respostas.")

        configuracao = cls.objects.order_by("id").first()
        if configuracao:
            if configuracao.mailbox_email.strip().lower() != mailbox_normalizado:
                configuracao.mailbox_email = mailbox_normalizado
                configuracao.save(update_fields=["mailbox_email", "atualizado_em"])
            return configuracao

        return cls.objects.create(mailbox_email=mailbox_normalizado)


class EmailCotacaoRespostaImportacao(models.Model):
    proposal = models.ForeignKey(
        "partners.Proposal",
        on_delete=models.CASCADE,
        related_name="respostas_email_importadas",
        verbose_name="Cotacao",
    )
    historico = models.ForeignKey(
        "RegistroHistorico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respostas_email_importadas",
        verbose_name="Historico gerado",
    )
    graph_message_id = models.CharField("ID da mensagem no Graph", max_length=255, unique=True)
    internet_message_id = models.CharField("Message-ID da internet", max_length=500, blank=True, null=True)
    assunto = models.CharField("Assunto", max_length=998)
    remetente = models.EmailField("Remetente", blank=True, null=True)
    recebido_em = models.DateTimeField("Recebido em", blank=True, null=True)
    importado_em = models.DateTimeField("Importado em", auto_now_add=True)

    class Meta:
        ordering = ["-importado_em"]
        verbose_name = "Resposta de e-mail importada"
        verbose_name_plural = "Respostas de e-mail importadas"

    def __str__(self):
        return f"{self.proposal.codigo_exibicao} - {self.assunto}"


class EmailEscolaRespostaImportacao(models.Model):
    """PO-066/RN-042: mesmo padrao de `EmailCotacaoRespostaImportacao`, mas
    para e-mail enviado (e respondido) a partir da Escola (nivel "Global",
    RN-023) ou de um RE/RI/Mapa Calor (RN-029/RN-043) — mesma caixa
    compartilhada do Microsoft Graph usada para cotacao. Model separado
    (em vez de reaproveitar `EmailCotacaoRespostaImportacao`) para nao
    confundir resposta de Escola/RE/RI/Mapa Calor com resposta de cotacao
    na mesma caixa (decisao do usuario, 2026-08-11).

    `content_type`/`object_id` (GenericForeignKey, nao FK direta) porque
    `apps.core` (camada base) nao pode importar `apps.escolas` (camada de
    dominio) sem inverter a ordem de camada da ADR-007 — mesmo padrao ja
    usado por `RegistroHistorico`/`CampoValor`. Aponta para `Escola`
    (nivel Global) ou para `RedeExterna`/`RedeInterna`/`MapaCalor` (nivel
    RE/RI/MC)."""

    NIVEL_RE = "re"
    NIVEL_RI = "ri"
    NIVEL_MC = "mc"
    NIVEL_GLOBAL = "global"
    NIVEL_CHOICES = [
        (NIVEL_RE, "Rede Externa (RE)"),
        (NIVEL_RI, "Rede Interna (RI)"),
        (NIVEL_MC, "Mapa Calor (MC)"),
        (NIVEL_GLOBAL, "Escola (Global)"),
    ]

    nivel = models.CharField("Nivel", max_length=10, choices=NIVEL_CHOICES)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    codigo_rastreio = models.CharField("Codigo de rastreio", max_length=64, db_index=True)
    historico = models.ForeignKey(
        "RegistroHistorico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respostas_email_escola_importadas",
        verbose_name="Historico gerado",
    )
    graph_message_id = models.CharField("ID da mensagem no Graph", max_length=255, unique=True)
    internet_message_id = models.CharField("Message-ID da internet", max_length=500, blank=True, null=True)
    assunto = models.CharField("Assunto", max_length=998)
    remetente = models.EmailField("Remetente", blank=True, null=True)
    recebido_em = models.DateTimeField("Recebido em", blank=True, null=True)
    importado_em = models.DateTimeField("Importado em", auto_now_add=True)

    class Meta:
        ordering = ["-importado_em"]
        verbose_name = "Resposta de e-mail de Escola/RE/RI importada"
        verbose_name_plural = "Respostas de e-mail de Escola/RE/RI importadas"

    def __str__(self):
        return f"{self.codigo_rastreio} - {self.assunto}"


class IntegrationAudit(models.Model):
    INTEGRATION_CHOICES = [
        ("logins_ixc", "Logins IXC"),
        ("edicao_login_ixc", "Edicao de Login IXC"),
        ("atendimento_ixc", "Atendimento IXC"),
        ("edicao_atendimento_ixc", "Edicao de Atendimento IXC"),
        ("desativacao_atendimento_ixc", "Desativacao de Atendimento IXC"),
        ("buscar_fornecedores", "Buscar Fornecedores"),
        ("importador_leads", "Importador de Leads"),
        ("cadastro_cliente_ixc", "Cadastro de Cliente IXC"),
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
    execucao_id = models.CharField("ID de Execucao", max_length=64, blank=True, null=True, db_index=True)
    progresso_atual = models.JSONField("Progresso Atual", blank=True, null=True, default=dict)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Log de Integracao"
        verbose_name_plural = "Logs de Integracoes"

    def __str__(self):
        return f"{self.get_integration_display()} - {self.get_action_display()} - {self.criado_em:%d/%m/%Y %H:%M}"


class AutomacaoMenu(models.Model):
    MENU_ADMINISTRADOR = 'administrador'
    MENU_BACKOFFICE = 'backoffice'
    MENU_LASTMILE = 'lastmile'
    MENU_PARCEIRO = 'parceiro'

    MENU_CHOICES = [
        (MENU_ADMINISTRADOR, 'Administrador'),
        (MENU_BACKOFFICE, 'Backoffice'),
        (MENU_LASTMILE, 'LastMile'),
        (MENU_PARCEIRO, 'Parceiro'),
    ]

    slug = models.SlugField(max_length=64, unique=True, verbose_name='Identificador')
    nome_exibicao = models.CharField(max_length=120, verbose_name='Nome de exibicao')
    menu = models.CharField(
        max_length=20,
        choices=MENU_CHOICES,
        default=MENU_ADMINISTRADOR,
        verbose_name='Menu de exibicao',
    )
    url_name = models.CharField(max_length=80, verbose_name='Nome da rota')
    icone = models.CharField(max_length=40, default='sparkles', verbose_name='Icone (lucide)')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    ordem = models.PositiveIntegerField(default=0, verbose_name='Ordem')

    class Meta:
        db_table = 'core_admin_automacaomenu'
        verbose_name = 'Menu de Automacao'
        verbose_name_plural = 'Menus de Automacao'
        ordering = ['ordem', 'nome_exibicao']

    def __str__(self):
        return f'{self.nome_exibicao} ({self.get_menu_display()})'

    @property
    def partial_template(self):
        return f'core_admin/partials/{self.slug}.html'


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
        db_table = "auditoria_restorebackupauditoria"
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
        db_table = "auditoria_cotacaostatusauditoria"
        ordering = ["-criado_em"]
        verbose_name = "Auditoria de Status da Cotacao"
        verbose_name_plural = "Auditorias de Status das Cotacoes"

    def __str__(self):
        return (
            f"{self.codigo_cotacao or 'cotacao'} - "
            f"{self.status_anterior} -> {self.status_novo} - "
            f"{self.criado_em:%d/%m/%Y %H:%M}"
        )


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
