from django.db import models

class Cliente(models.Model):
    id_ixc = models.CharField('ID IXC', max_length=50, unique=True, blank=True, null=True)
    razao_social = models.CharField('Razão Social', max_length=200, default='')
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True, default='')
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, default='')
    contato_nome = models.CharField('Nome do Contato', max_length=100, blank=True, null=True, default='')
    email = models.EmailField('E-mail Principal', blank=True, null=True, default='contato@exemplo.com')
    telefone = models.CharField('Telefone', max_length=20, blank=True, null=True, default='')
    
    # NOVOS CAMPOS DE AUDITORIA
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

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

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('cancelado', 'Cancelado'),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='enderecos')
    tipo = models.CharField('Tipo', max_length=50, default='Matriz', help_text="Ex: Matriz, Filial")
    
    # 📍 DADOS DE LOCALIZAÇÃO 
    cep = models.CharField('CEP', max_length=20, default='')
    logradouro = models.CharField('Endereço', max_length=255, default='')
    numero = models.CharField('Número', max_length=20, default='S/N')
    bairro = models.CharField('Bairro', max_length=100, default='')
    cidade = models.CharField('Cidade', max_length=100, default='Fortaleza')
    estado = models.CharField('UF', max_length=2, choices=ESTADO_CHOICES, default='CE')

    # 🚀 NOVOS CAMPOS PARA INTEGRAÇÃO IXC
    login_ixc = models.CharField('Login IXC (PPPoE)', max_length=150, blank=True, null=True)
    filial_ixc = models.CharField('Filial (IXC)', max_length=100, blank=True, null=True)
    agente_id_ixc = models.CharField('Agente ID', max_length=50, blank=True, null=True)

    status = models.CharField('Status', max_length=15, choices=STATUS_CHOICES, default='pendente')
    data_ativacao = models.DateField('Data de Ativação', null=True, blank=True)
    principal = models.BooleanField('Endereço Principal?', default=False)

    # CAMPOS DE AUDITORIA
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Endereço/Login'
        verbose_name_plural = 'Endereços e Logins'
        ordering = ['status', 'logradouro']

    def __str__(self):
        # Agora o painel do Django vai mostrar o Login se ele existir!
        identificador = self.login_ixc if self.login_ixc else self.tipo
        return f"{identificador} - {self.cidade}/{self.estado} ({self.get_status_display()})"
    

class HistoricoSincronizacao(models.Model):
    STATUS_CHOICES = [
        ('rodando', 'Rodando...'),
        ('sucesso', 'Sucesso'),
        ('erro', 'Erro'),
    ]
    
    data_inicio = models.DateTimeField('Início', auto_now_add=True)
    data_fim = models.DateTimeField('Fim', null=True, blank=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='rodando')
    registros_processados = models.IntegerField('Registros Atualizados', default=0)
    detalhes = models.TextField('Detalhes / Mensagem de Erro', blank=True, null=True)

    class Meta:
        verbose_name = 'Histórico de Sincronização'
        verbose_name_plural = 'Histórico de Sincronizações'
        ordering = ['-data_inicio']

    def __str__(self):
        return f"Sync {self.data_inicio.strftime('%d/%m/%Y %H:%M')} - {self.get_status_display()}"