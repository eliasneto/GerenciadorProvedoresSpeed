from django.db import models

class Lead(models.Model):
    # Status atualizados com as novas opções solicitadas
    STATUS_CHOICES = [
        ('novo', 'Novo'),
        ('negociacao', 'Em Negociação'),
        ('andamento', 'Em Andamento'),
        ('ativo', 'Ativo'),
        ('inviavel', 'Inviável / Não Avançou'),
    ]

    # Identificação básica - Tudo é opcional (blank=True, null=True)
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
    
    # Controle de status com o padrão forçado para 'novo'
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='novo'
    )
    
    # Metadados
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ordenação decrescente: os leads mais novos aparecem primeiro no grid
        ordering = ['-data_criacao']

    def __str__(self):
        # Exibe o Nome Fantasia no Admin/Formulários; se vazio, usa Razão Social
        return self.nome_fantasia or self.razao_social or "Lead sem nome"