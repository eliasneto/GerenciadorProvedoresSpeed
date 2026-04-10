from django.db import models


LEAD_STATUS_CHOICES = [
    ('novo', 'Novo'),
    ('negociacao', 'Em Negociação'),
    ('andamento', 'Em Andamento'),
    ('ativo', 'Ativo'),
    ('inviavel', 'Inviável / Não Avançou'),
]


class LeadEmpresa(models.Model):
    razao_social = models.CharField('Razão Social / Nome', max_length=200, blank=True, null=True)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, blank=True, null=True)
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True)
    site = models.URLField('Site', max_length=200, blank=True, null=True)

    contato_nome = models.CharField('Pessoa de Contato', max_length=100, blank=True, null=True)
    email = models.EmailField('E-mail', blank=True, null=True)
    telefone = models.CharField('Telefone/WhatsApp', max_length=20, blank=True, null=True)

    fonte = models.CharField('Fonte de Captação', max_length=100, blank=True, null=True)
    confianca = models.CharField('Confiança dos Dados', max_length=50, blank=True, null=True)
    instagram_username = models.CharField('Usuário Instagram', max_length=100, blank=True, null=True)
    instagram_url = models.URLField('Link Instagram', max_length=255, blank=True, null=True)
    bio_instagram = models.TextField('Bio do Instagram', blank=True, null=True)
    observacao_ia = models.TextField('Observação da IA', blank=True, null=True)

    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES, default='novo')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = 'Empresa de Lead'
        verbose_name_plural = 'Empresas de Leads'

    def __str__(self):
        return self.nome_fantasia or self.razao_social or "Empresa sem nome"


class LeadEndereco(models.Model):
    empresa = models.ForeignKey(
        LeadEmpresa,
        on_delete=models.CASCADE,
        related_name='enderecos',
        verbose_name='Empresa',
    )
    cep = models.CharField('CEP', max_length=20, blank=True, null=True)
    endereco = models.CharField('Logradouro / Endereço', max_length=255, blank=True, null=True)
    numero = models.CharField('Número', max_length=20, blank=True, null=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True, null=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True, null=True)
    estado = models.CharField('Estado', max_length=2, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['empresa__razao_social', 'cidade', 'bairro', 'endereco', 'id']
        verbose_name = 'Endereco de Lead'
        verbose_name_plural = 'Enderecos de Leads'

    def __str__(self):
        partes = [self.endereco or 'Endereco sem nome']
        if self.numero:
            partes.append(self.numero)
        if self.cidade:
            partes.append(self.cidade)
        return ' - '.join(partes)


class Lead(models.Model):
    # Identificacao basica
    razao_social = models.CharField('Razão Social / Nome', max_length=200, blank=True, null=True)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, blank=True, null=True)
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True)
    site = models.URLField('Site', max_length=200, blank=True, null=True)

    # Localizacao
    cep = models.CharField('CEP', max_length=20, blank=True, null=True)
    endereco = models.CharField('Logradouro / Endereço', max_length=255, blank=True, null=True)
    numero = models.CharField('Número', max_length=20, blank=True, null=True)
    bairro = models.CharField('Bairro', max_length=100, blank=True, null=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True, null=True)
    estado = models.CharField('Estado', max_length=2, blank=True, null=True)

    # Contatos
    contato_nome = models.CharField('Pessoa de Contato', max_length=100, blank=True, null=True)
    email = models.EmailField('E-mail', blank=True, null=True)
    telefone = models.CharField('Telefone/WhatsApp', max_length=20, blank=True, null=True)

    # Integracao IA
    fonte = models.CharField('Fonte de Captação', max_length=100, blank=True, null=True)
    confianca = models.CharField('Confiança dos Dados', max_length=50, blank=True, null=True)
    instagram_username = models.CharField('Usuário Instagram', max_length=100, blank=True, null=True)
    instagram_url = models.URLField('Link Instagram', max_length=255, blank=True, null=True)
    bio_instagram = models.TextField('Bio do Instagram', blank=True, null=True)
    observacao_ia = models.TextField('Observação da IA', blank=True, null=True)

    empresa_estruturada = models.ForeignKey(
        LeadEmpresa,
        on_delete=models.SET_NULL,
        related_name='leads_legados',
        blank=True,
        null=True,
        verbose_name='Empresa Estruturada',
    )
    endereco_estruturado = models.ForeignKey(
        LeadEndereco,
        on_delete=models.SET_NULL,
        related_name='leads_legados',
        blank=True,
        null=True,
        verbose_name='Endereco Estruturado',
    )

    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES, default='novo')
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return self.nome_fantasia or self.razao_social or "Lead sem nome"
