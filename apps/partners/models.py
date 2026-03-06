from django.db import models
from dateutil.relativedelta import relativedelta
from datetime import date

class Partner(models.Model):
    """
    DADOS MESTRE: Informações fixas da empresa parceira.
    """
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
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
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='ativo')
    
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parceiro'
        verbose_name_plural = 'Parceiros'
        ordering = ['-data_cadastro']

    def __str__(self):
        return self.nome_fantasia or self.razao_social or "Parceiro sem Nome"


class Proposal(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='proposals')
    
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
    os_numero = models.CharField('OS nº', max_length=50, blank=True, null=True)
    data_emissao = models.DateField('Data de Emissão', null=True, blank=True)
    velocidade = models.CharField('Velocidade', max_length=50, default='50 Mbps')
    tecnologia = models.CharField('Tecnologia', max_length=50, default='Fibra')
    disponibilidade = models.CharField('Disponibilidade (%)', max_length=10, default='99,50%')
    mttr = models.IntegerField('MTTR (hs)', default=4)
    perda_pacote = models.CharField('Perda de Pacote', max_length=10, default='<1%')
    interfaces = models.CharField('Interfaces', max_length=100, default='Gigabit Ethernet (elétrica)')
    ipv4_bloco = models.CharField('IPs (bloco)', max_length=50, default='IPv4 bloco/30')
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
    valor_mensal = models.DecimalField('Valor Mensal', max_digits=10, decimal_places=2, null=True, blank=True)
    taxa_instalacao = models.DecimalField('Taxa Instalação', max_digits=10, decimal_places=2, null=True, blank=True)
    tempo_contrato = models.IntegerField('Tempo Contrato (meses)', default=24)
    email_faturamento = models.EmailField('E-mail Faturamento', blank=True, null=True)
    valor_parceiro = models.DecimalField('Valor Pago ao parceiro', max_digits=10, decimal_places=2, null=True, blank=True)

    # --- CONTROLE DE DATAS ---
    data_ativacao = models.DateField('Data de Ativação', null=True, blank=True)
    data_vencimento = models.DateField('Data de Vencimento', null=True, blank=True)

    class Meta:
        verbose_name = 'Proposta'
        verbose_name_plural = 'Propostas'
        ordering = ['-id']

    @property
    def vencido(self):
        """Retorna True se a data de vencimento já passou"""
        if self.data_vencimento:
            return self.data_vencimento < date.today()
        return False

    def save(self, *args, **kwargs):
        # Lógica: Cálculo automático do vencimento com base na ativação
        if self.data_ativacao and self.tempo_contrato:
            self.data_vencimento = self.data_ativacao + relativedelta(months=self.tempo_contrato)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"OS {self.os_numero or 'S/N'} - {self.partner.nome_fantasia or self.partner.razao_social}"