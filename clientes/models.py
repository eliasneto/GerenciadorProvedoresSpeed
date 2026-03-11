from django.db import models

class Cliente(models.Model):
    razao_social = models.CharField('Razão Social', max_length=200, default='')
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True, default='')
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, unique=True, default='')
    contato_nome = models.CharField('Nome do Contato', max_length=100, blank=True, null=True, default='')
    email = models.EmailField('E-mail Principal', blank=True, null=True, default='contato@exemplo.com')
    telefone = models.CharField('Telefone', max_length=20, blank=True, null=True, default='')
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nome_fantasia or self.razao_social

class Endereco(models.Model):
    # Choices para o Estado (UF)
    ESTADO_CHOICES = [
        ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'), 
        ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'), 
        ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'), 
        ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'), 
        ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'), 
        ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'), 
        ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
    ]

    # NOVO: Choices para o Status da Unidade
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('cancelado', 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='enderecos')
    tipo = models.CharField('Tipo', max_length=50, default='Matriz', help_text="Ex: Matriz, Filial")
    cep = models.CharField('CEP', max_length=20, default='')
    logradouro = models.CharField('Endereço', max_length=255, default='')
    numero = models.CharField('Número', max_length=20, default='S/N')
    bairro = models.CharField('Bairro', max_length=100, default='')
    cidade = models.CharField('Cidade', max_length=100, default='Fortaleza')
    estado = models.CharField('UF', max_length=2, choices=ESTADO_CHOICES, default='CE')


    # NOVO CAMPO: Status com valor padrão 'pendente'
    status = models.CharField(
        'Status', 
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='pendente'
    )
    data_ativacao = models.DateField('Data de Ativação', null=True, blank=True)
    principal = models.BooleanField('Endereço Principal?', default=False)

    class Meta:
        verbose_name = 'Endereço'
        verbose_name_plural = 'Endereços'
        # Ordenação: Primeiro os ativos, depois por logradouro
        ordering = ['status', 'logradouro']

    def __str__(self):
        return f"{self.tipo} - {self.cidade}/{self.estado} ({self.get_status_display()})"