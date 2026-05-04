from django.db import models


class TabelaAcessoBanco(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    ]

    nome_tabela = models.CharField(max_length=128, unique=True, verbose_name='Nome da tabela')
    descricao = models.CharField(max_length=255, blank=True, verbose_name='Descrição')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ativo', verbose_name='Status')

    class Meta:
        verbose_name = 'Tabela de Acesso ao Banco'
        verbose_name_plural = 'Tabelas de Acesso ao Banco'
        ordering = ['nome_tabela']

    def __str__(self):
        return self.nome_tabela


class AcessoBancoDados(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    ]

    nome = models.CharField(max_length=120, verbose_name='Nome do acesso')
    usuario_banco = models.CharField(max_length=64, unique=True, verbose_name='Usuário do banco')
    senha_banco = models.CharField(max_length=128, verbose_name='Senha do banco')
    host_acesso = models.CharField(max_length=100, default='%', verbose_name='Host de acesso')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ativo', verbose_name='Status')
    tabelas_permitidas = models.ManyToManyField(
        TabelaAcessoBanco,
        blank=True,
        verbose_name='Tabelas permitidas',
        related_name='acessos_banco',
    )
    ultimo_aplicado_em = models.DateTimeField(null=True, blank=True, verbose_name='Última aplicação')
    ultimo_erro = models.TextField(blank=True, verbose_name='Último erro')
    observacao = models.TextField(blank=True, verbose_name='Observação')

    class Meta:
        verbose_name = 'Acesso Banco de Dados'
        verbose_name_plural = 'Acessos Banco de Dados'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} ({self.usuario_banco})'


class ConfiguracaoEmailEnvio(models.Model):
    nome = models.CharField(max_length=80, default='Padrao do Sistema', verbose_name='Identificacao')
    email_remetente_padrao = models.EmailField(
        blank=True,
        null=True,
        verbose_name='E-mail remetente padrao',
        help_text='Este e-mail aparece como remetente padrao na composicao das mensagens do sistema.',
    )
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Configuracao de E-mail'
        verbose_name_plural = 'Configuracoes de E-mail'

    def __str__(self):
        return self.nome or 'Configuracao de E-mail'

    @classmethod
    def obter_configuracao(cls):
        configuracao = cls.objects.order_by('id').first()
        if configuracao:
            return configuracao
        return cls.objects.create()
