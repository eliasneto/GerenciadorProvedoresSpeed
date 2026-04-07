from django.db import models
from dateutil.relativedelta import relativedelta
from datetime import date, datetime
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

class Partner(models.Model):
    """
    DADOS MESTRE: Informações fixas da empresa parceira.
    """
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('aguardando_contratacao', 'Aguardando Contratação'),
        ('contratado', 'Contratado'),
        ('declinado', 'Declinado'),
        ('inativo', 'Inativo / Novo'),
        ('negociacao', 'Em Negociação'),
        ('andamento', 'Em Andamento (Reativar)'),
        ('inviavel', 'Inviável / Não Avançou'),
    ]

    razao_social = models.CharField('Razão Social', max_length=200, blank=True, null=True)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, blank=True, null=True, unique=True)
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True)
    contato_nome = models.CharField('Contato Principal', max_length=100, blank=True, null=True)
    email = models.EmailField('E-mail Corporativo', blank=True, null=True)
    telefone = models.CharField('Telefone Comercial', max_length=20, blank=True, null=True)
    
    # Campo status atualizado recebendo as novas escolhas
    status = models.CharField('Status', max_length=30, choices=STATUS_CHOICES, default='ativo')
    
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parceiro'
        verbose_name_plural = 'Parceiros'
        ordering = ['-data_cadastro']

    def __str__(self):
        return self.nome_fantasia or self.razao_social or "Parceiro sem Nome"


class PartnerPlan(models.Model):
    SIM_NAO_CHOICES = [
        ('', 'Selecione'),
        ('Sim', 'Sim'),
        ('Não', 'Não'),
    ]

    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='planos')
    nome_plano = models.CharField('Nome do Plano', max_length=120)
    velocidade = models.CharField('Velocidade (Mbps)', max_length=50, blank=True, null=True)
    tecnologia = models.CharField('Tecnologia de Acesso', max_length=50, blank=True, null=True)
    disponibilidade = models.CharField('Disponibilidade (%)', max_length=10, blank=True, null=True)
    mttr = models.IntegerField('MTTR (hs)', blank=True, null=True)
    perda_pacote = models.CharField('Perda de Pacote', max_length=10, blank=True, null=True)
    latencia = models.IntegerField('Latência (ms)', blank=True, null=True)
    interfaces = models.CharField('Interfaces', max_length=100, blank=True, null=True)
    tipo_acesso = models.CharField('Tipo de Acesso', max_length=100, blank=True, null=True)
    ipv4_bloco = models.CharField('Bloco IP', max_length=50, blank=True, null=True)
    dupla_abordagem = models.CharField('Dupla Abordagem', max_length=3, blank=True, null=True, choices=SIM_NAO_CHOICES)
    entrega_rb = models.CharField('Entrega RB', max_length=3, blank=True, null=True, choices=SIM_NAO_CHOICES)
    designador = models.CharField('Designador', max_length=100, blank=True, null=True)
    trunk = models.CharField('Interface em Trunk?', max_length=3, blank=True, null=True, choices=SIM_NAO_CHOICES)
    dhcp = models.CharField('DHCP habilitado?', max_length=3, blank=True, null=True, choices=SIM_NAO_CHOICES)
    prazo_ativacao = models.IntegerField('Prazo de Ativação (dias)', blank=True, null=True)
    valor_plano = models.DecimalField('Valor do Plano', max_digits=10, decimal_places=2, blank=True, null=True)
    contato_suporte = models.CharField('Contato para Suporte', max_length=100, blank=True, null=True)
    telefone_suporte = models.CharField('Número do Telefone', max_length=25, blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plano do Parceiro'
        verbose_name_plural = 'Planos dos Parceiros'
        ordering = ['nome_plano', '-id']

    def __str__(self):
        parceiro = self.partner.nome_fantasia or self.partner.razao_social or f"Parceiro #{self.partner_id}"
        return f"{self.nome_plano} - {parceiro}"


class ProposalMotivoInviavel(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
    ]

    nome = models.CharField('Nome do Motivo', max_length=120, unique=True)
    status = models.CharField('Status', max_length=10, choices=STATUS_CHOICES, default='ativo')
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Motivo de Cotação Inviável'
        verbose_name_plural = 'Motivos de Cotações Inviáveis'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Proposal(models.Model):
    STATUS_CHOICES = [
        ('analise', 'Em Negociação'),
        ('ativa', 'Viavel'),
        ('aguardando_contratacao', 'Aguardando Contratação'),
        ('contratado', 'Contratado'),
        ('declinado', 'Declinado'),
        ('encerrada', 'Inviavel'),
    ]

    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='proposals')
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='propostas_responsavel',
        null=True,
        blank=True,
        verbose_name='Responsável'
    )
    
    # VÍNCULO COM CLIENTE
    cliente = models.ForeignKey(
        'clientes.Cliente', 
        on_delete=models.CASCADE, 
        related_name='proposals',
        null=True, blank=True
    )

    # RASTREABILIDADE TÉCNICA: Vínculo com a Unidade específica
    client_address = models.ForeignKey(
        'clientes.Endereco', 
        on_delete=models.SET_NULL, 
        related_name='proposals',
        null=True, 
        blank=True,
        verbose_name="Unidade de Instalação"
    )
    
    # --- DADOS TÉCNICOS ---
    grupo_proposta_id = models.PositiveIntegerField('Grupo da Cotação', null=True, blank=True, db_index=True)
    codigo_proposta = models.CharField('Código da Cotação', max_length=30, null=True, blank=True, db_index=True)
    nome_proposta = models.CharField('Nome da Cotação', max_length=150, blank=True, null=True)
    os_numero = models.CharField('OS nº', max_length=50, blank=True, null=True)
    data_emissao = models.DateField('Data de Emissão', null=True, blank=True)
    velocidade = models.CharField('Velocidade (Mbps)', max_length=50, default='50 Mbps')
    tecnologia = models.CharField('Tecnologia de Acesso', max_length=50, default='Fibra')
    disponibilidade = models.CharField('Disponibilidade (%)', max_length=10, default='99,50%')
    mttr = models.IntegerField('MTTR (hs)', default=4)
    perda_pacote = models.CharField('Perda de Pacote', max_length=10, default='<1%')
    interfaces = models.CharField('Interfaces', max_length=100, default='Gigabit Ethernet (elétrica)')
    tipo_acesso = models.CharField('Tipo de Acesso', max_length=100, blank=True, null=True)
    ipv4_bloco = models.CharField('Bloco IP', max_length=50, default='IPv4 bloco/30')
    dupla_abordagem = models.CharField('Dupla Abordagem', max_length=3, blank=True, null=True)
    entrega_rb = models.CharField('Entrega RB', max_length=3, blank=True, null=True)
    designador = models.CharField('Designador', max_length=100, blank=True, null=True)
    trunk = models.CharField('Interface em Trunk?', max_length=3, default='Não')
    dhcp = models.CharField('DHCP habilitado?', max_length=3, default='Sim')
    latencia = models.IntegerField('Latência (ms)', default=50)
    prazo_ativacao = models.IntegerField('Prazo de Ativação (dias)', default=15)
    contato_suporte = models.CharField('Contato para Suporte', max_length=100, blank=True, null=True)
    telefone_suporte = models.CharField('Número do Telefone', max_length=25, blank=True, null=True)

    # --- CAMPOS DE ESPELHO (Úteis para histórico rápido) ---
    inst_endereco = models.CharField('Endereço Instalação', max_length=255, blank=True, null=True)
    inst_cidade = models.CharField('Cidade Instalação', max_length=100, blank=True, null=True)
    inst_cep = models.CharField('CEP Instalação', max_length=20, blank=True, null=True)
    
    # --- COMERCIAL ---
    ticket_cliente = models.DecimalField('Valor Mensal Cliente', max_digits=10, decimal_places=2, null=True, blank=True)
    ticket_empresa = models.DecimalField('Target Empresa', max_digits=10, decimal_places=2, null=True, blank=True)
    valor_mensal = models.DecimalField('Valor Mensal', max_digits=10, decimal_places=2, null=True, blank=True)
    taxa_instalacao = models.DecimalField('Taxa de Instalação Parceiro', max_digits=10, decimal_places=2, null=True, blank=True)
    tempo_contrato = models.IntegerField('Tempo Contrato (meses)', default=24)
    email_faturamento = models.EmailField('E-mail Faturamento', blank=True, null=True)
    valor_parceiro = models.DecimalField('Custo Parceiro', max_digits=10, decimal_places=2, null=True, blank=True)
    resultado_mes_1 = models.DecimalField('Resultado Mês 1', max_digits=12, decimal_places=2, null=True, blank=True)
    resultado_mensal = models.DecimalField('Resultado Mensal', max_digits=12, decimal_places=2, null=True, blank=True)
    valor_total_proposta = models.DecimalField('Rentabilidade', max_digits=12, decimal_places=2, null=True, blank=True)
    motivo_inviavel = models.ForeignKey(
        ProposalMotivoInviavel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='propostas',
        verbose_name='Motivo da Cotação Inviável',
    )
    observacao_inviavel = models.CharField('Observação da Cotação Inviável', max_length=150, blank=True, null=True)

    # --- CONTROLE DE DATAS ---
    status = models.CharField('Status da Cotação', max_length=30, choices=STATUS_CHOICES, default='analise')
    data_ativacao = models.DateField('Data de Ativação', null=True, blank=True)
    data_vencimento = models.DateField('Data de Vencimento', null=True, blank=True)

    class Meta:
        verbose_name = 'Cotação'
        verbose_name_plural = 'Cotações'
        ordering = ['-id']

    @property
    def vencido(self):
        """Retorna True se a data de vencimento já passou"""
        if self.data_vencimento:
            return self.data_vencimento < date.today()
        return False

    @property
    def identificador_lote(self):
        return self.grupo_proposta_id or self.id

    @staticmethod
    def montar_codigo_proposta(sequencial, referencia=None):
        if referencia is None:
            referencia = timezone.localdate() if settings.USE_TZ else date.today()
        elif isinstance(referencia, datetime):
            referencia = timezone.localtime(referencia).date() if timezone.is_aware(referencia) else referencia.date()
        return f"{sequencial}{referencia:%d%m%Y}"

    @property
    def codigo_exibicao(self):
        if self.codigo_proposta:
            return self.codigo_proposta
        referencia = self.data_emissao or self.data_ativacao or timezone.localdate()
        return self.montar_codigo_proposta(self.identificador_lote, referencia)

    def save(self, *args, **kwargs):
        # Lógica: Cálculo automático do vencimento com base na ativação
        if self.data_ativacao and self.tempo_contrato:
            self.data_vencimento = self.data_ativacao + relativedelta(months=self.tempo_contrato)

        mensal = self.valor_mensal or Decimal('0')
        instalacao = self.taxa_instalacao or Decimal('0')
        parceiro = self.valor_parceiro or Decimal('0')
        vigencia = Decimal(str(self.tempo_contrato or 0))
        self.resultado_mensal = mensal - parceiro
        self.resultado_mes_1 = self.resultado_mensal + instalacao
        if vigencia <= 0:
            self.valor_total_proposta = Decimal('0')
        elif vigencia == 1:
            self.valor_total_proposta = self.resultado_mes_1
        else:
            self.valor_total_proposta = self.resultado_mes_1 + (self.resultado_mensal * (vigencia - Decimal('1')))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"OS {self.os_numero or 'S/N'} - {self.partner.nome_fantasia or self.partner.razao_social}"
