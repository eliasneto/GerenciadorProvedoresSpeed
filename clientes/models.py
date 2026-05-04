from django.db import models
from django.conf import settings

class Cliente(models.Model):
    id_ixc = models.CharField('ID IXC', max_length=50, unique=True, blank=True, null=True)
    razao_social = models.CharField('Razão Social', max_length=200, default='')
    nome_fantasia = models.CharField('Nome Fantasia', max_length=200, blank=True, null=True, default='')
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20, default='')
    contato_nome = models.CharField('Nome do Contato', max_length=100, blank=True, null=True, default='')
    email = models.EmailField('E-mail Principal', blank=True, null=True, default='contato@exemplo.com')
    telefone = models.CharField('Telefone', max_length=20, blank=True, null=True, default='')
    
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.nome_fantasia or self.razao_social


class Endereco(models.Model):
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
    tipo = models.CharField('Tipo', max_length=50, default='Matriz')
    cep = models.CharField('CEP', max_length=20, default='')
    logradouro = models.CharField('Endereço', max_length=255, default='')
    numero = models.CharField('Número', max_length=20, default='S/N')
    bairro = models.CharField('Bairro', max_length=100, default='')
    cidade = models.CharField('Cidade', max_length=100, default='Fortaleza')
    cidade_id_ixc = models.CharField('Cidade ID IXC', max_length=50, blank=True, null=True)
    estado = models.CharField('UF', max_length=2, choices=ESTADO_CHOICES, default='CE')

    login_ixc = models.CharField('Login IXC (PPPoE)', max_length=150, blank=True, null=True)
    login_id_ixc = models.CharField('Login ID IXC', max_length=50, blank=True, null=True, db_index=True)
    contrato_id_ixc = models.CharField('Contrato ID IXC', max_length=50, blank=True, null=True, db_index=True)
    filial_ixc = models.CharField('Filial (IXC)', max_length=100, blank=True, null=True)
    agente_id_ixc = models.CharField('Agente ID', max_length=50, blank=True, null=True)
    agent_circuit_id = models.CharField('ID do Circuito', max_length=100, null=True, blank=True)
    ticket_os_atual_ixc = models.CharField('Ticket/OS Atual IXC', max_length=50, blank=True, null=True)
    setor_os_atual_id_ixc = models.CharField('Setor Atual da OS ID IXC', max_length=50, blank=True, null=True)
    setor_os_atual_nome = models.CharField('Setor Atual da OS', max_length=150, blank=True, null=True)
    status_os_atual_nome = models.CharField('Status Atual da OS', max_length=100, blank=True, null=True)
    os_atual_aberta = models.BooleanField('OS Atual Aberta?', default=False, db_index=True)
    em_os_comercial_lastmile = models.BooleanField('Em OS Comercial | Lastmile?', default=False, db_index=True)

    velocidade = models.CharField('Velocidade (Mbps)', max_length=50, blank=True, null=True)
    tecnologia = models.CharField('Tecnologia de Acesso', max_length=50, blank=True, null=True)
    disponibilidade = models.CharField('Disponibilidade (%)', max_length=10, blank=True, null=True)
    mttr = models.IntegerField('MTTR (hs)', null=True, blank=True)
    perda_pacote = models.CharField('Perda de Pacote', max_length=10, blank=True, null=True)
    latencia = models.IntegerField('Latência (ms)', null=True, blank=True)
    interfaces = models.CharField('Interfaces', max_length=100, blank=True, null=True)
    tipo_acesso = models.CharField('Tipo de Acesso', max_length=100, blank=True, null=True)
    ipv4_bloco = models.CharField('Bloco IP', max_length=50, blank=True, null=True)
    dupla_abordagem = models.CharField('Dupla Abordagem', max_length=3, blank=True, null=True)
    entrega_rb = models.CharField('Entrega RB', max_length=3, blank=True, null=True)
    designador = models.CharField('Designador', max_length=100, blank=True, null=True)
    trunk = models.CharField('Interface em Trunk?', max_length=3, blank=True, null=True)
    dhcp = models.CharField('DHCP habilitado?', max_length=3, blank=True, null=True)
    prazo_ativacao = models.IntegerField('Prazo de Ativação (dias)', null=True, blank=True)
    contato_suporte = models.CharField('Contato para Suporte', max_length=100, blank=True, null=True)
    telefone_suporte = models.CharField('Número do Telefone', max_length=25, blank=True, null=True)

    status = models.CharField('Status', max_length=15, choices=STATUS_CHOICES, default='pendente')
    data_ativacao = models.DateField('Data de Ativação', null=True, blank=True)
    principal = models.BooleanField('Endereço Principal?', default=False)

    criado_em = models.DateTimeField('Criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Endereço/Login'
        verbose_name_plural = 'Endereços e Logins'
        ordering = ['status', 'logradouro']

    def __str__(self):
        # 1. Tenta pegar o Login IXC. Se estiver vazio, avisa que está pendente.
        login_str = f"Login: {self.login_ixc}" if self.login_ixc else "Login: [Pendente/Não Sincronizado]"
        
        # 2. Monta a rua e o número. Se a rua estiver vazia, usa o Tipo (ex: Matriz)
        rua_str = self.logradouro if self.logradouro else f"Unidade: {self.tipo}"
        numero_str = self.numero if self.numero else "S/N"
        
        # 3. Junta tudo num formato bonito e fácil de ler para o consultor
        return f"{login_str} ➔ {rua_str}, {numero_str} ({self.cidade}/{self.estado})"

# Em apps/clientes/models.py

class HistoricoSincronizacao(models.Model):
    TIPO_CHOICES = [
        ('incremental', 'Incremental'),
        ('total', 'Carga Total'),
        ('faxina', 'Faxina/Lixo'),
        ('os_comercial_lastmile', 'OS Comercial | Lastmile'),
        ('email_respostas_cotacao', 'Respostas de E-mail da Cotacao'),
        ('backup', 'Backup'),
    ]

    ORIGEM_CHOICES = [
        ('manual', 'Manual'),
        ('automatica', 'Automática'),
    ]
    
    tipo = models.CharField('Tipo de Sync', max_length=30, choices=TIPO_CHOICES, default='incremental')
    status = models.CharField('Status', max_length=20, choices=[('rodando', 'Rodando...'), ('sucesso', 'Sucesso'), ('erro', 'Erro')], default='rodando')
    
    # --- NOVOS CAMPOS ---
    origem = models.CharField('Origem', max_length=20, choices=ORIGEM_CHOICES, default='automatica')
    executado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Usuário Responsável'
    )
    # --------------------

    data_inicio = models.DateTimeField('Início', auto_now_add=True)
    data_fim = models.DateTimeField('Fim', null=True, blank=True)
    registros_processados = models.IntegerField('Registros', default=0)
    detalhes = models.TextField('Detalhes', blank=True, null=True)

    class Meta:
        verbose_name = 'Histórico de Sincronização'
        verbose_name_plural = 'Histórico de Sincronizações'
        ordering = ['-data_inicio']

    def __str__(self):
        executor = self.executado_por.get_full_name() if self.executado_por else "Sistema"
        return f"{self.get_tipo_display()} ({self.get_origem_display()}) - {executor} - {self.data_inicio.strftime('%d/%m/%Y %H:%M')}"

class LogAlteracaoIXC(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='logs_alteracoes')
    login_ixc = models.CharField('Login IXC', max_length=150, blank=True, null=True) # ADICIONADO
    campo_alterado = models.CharField(max_length=100)
    valor_antigo = models.TextField(null=True, blank=True)
    valor_novo = models.TextField(null=True, blank=True)
    data_registro = models.DateTimeField('Data do Registro', auto_now_add=True) # RENOMEADO

    class Meta:
        verbose_name = "Log de Alteração IXC"
        ordering = ['-data_registro']

        

class ClienteExcluido(models.Model):
    id_ixc = models.CharField('ID IXC', max_length=50)
    razao_social = models.CharField('Razão Social', max_length=200)
    cnpj_cpf = models.CharField('CNPJ/CPF', max_length=20)
    dados_completos_json = models.JSONField('Dados Completos (Backup)') # Guarda tudo que tinha no original
    data_exclusao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lixo IXC - Cliente"

class EnderecoExcluido(models.Model):
    cliente_excluido = models.ForeignKey(ClienteExcluido, on_delete=models.CASCADE, related_name='enderecos')
    login_ixc = models.CharField('Login', max_length=150)
    agent_circuit_id = models.CharField('Circuito', max_length=150, null=True)
    detalhes_json = models.JSONField()        
