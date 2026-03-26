from django.db import models

class Lead(models.Model):
    STATUS_CHOICES = [
        ('novo', 'Novo'),
        ('negociacao', 'Em Negociação'),
        ('andamento', 'Em Andamento'),
        ('ativo', 'Ativo'),
        ('inviavel', 'Inviável / Não Avançou'),
    ]

    # Identificação básica
    razao_social = models.CharField('Razão Social / Nome', max_length=200, blank=True, null=True)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, blank=True, null=True)
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True)
    site = models.URLField('Site', max_length=200, blank=True, null=True)
    
    # Localização
    endereco = models.CharField('Endereço', max_length=255, blank=True, null=True)
    cidade = models.CharField('Cidade', max_length=100, blank=True, null=True)
    estado = models.CharField('Estado', max_length=2, blank=True, null=True) 
    
    # Contatos
    contato_nome = models.CharField('Pessoa de Contato', max_length=100, blank=True, null=True)
    email = models.EmailField('E-mail', blank=True, null=True)
    telefone = models.CharField('Telefone/WhatsApp', max_length=20, blank=True, null=True)
    
    # ==========================================
    # 🚀 NOVOS CAMPOS DA INTEGRAÇÃO IA (SERPER)
    # ==========================================
    fonte = models.CharField('Fonte de Captação', max_length=100, blank=True, null=True)
    confianca = models.CharField('Confiança dos Dados', max_length=50, blank=True, null=True)
    instagram_username = models.CharField('Usuário Instagram', max_length=100, blank=True, null=True)
    instagram_url = models.URLField('Link Instagram', max_length=255, blank=True, null=True)
    bio_instagram = models.TextField('Bio do Instagram', blank=True, null=True)
    observacao_ia = models.TextField('Observação da IA', blank=True, null=True)
    # ==========================================
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='novo'
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_criacao']

    def __str__(self):
        return self.nome_fantasia or self.razao_social or "Lead sem nome"