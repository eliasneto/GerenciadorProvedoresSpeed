from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class UserManager(BaseUserManager):
    # O create_user agora pede o 'username' primeiro
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('O nome de usuário (username) é obrigatório')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractUser):
    # 1. DEVOLVEMOS O USERNAME COMO CHAVE ÚNICA
    username = models.CharField('Usuário', max_length=150, unique=True)
    
    # 2. O e-mail continua existindo e sendo único, mas não é mais a chave de login
    email = models.EmailField('Endereço de E-mail', unique=True, blank=True, null=True) 
    
    is_gestor = models.BooleanField('É Gestor?', default=False)
    
    # 3. MUDANÇA DE PODER: O Login agora é pelo username
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email'] 
    
    objects = UserManager()

    # =================================================================
    # MÁGICA SPEED: Resolve o conflito de e-mails vazios ANTES da validação
    # =================================================================
    def clean(self):
        # Chama a limpeza padrão do Django
        super().clean()
        # Se o e-mail vier como texto vazio "", converte para NULL (None no Python)
        # Isso evita que o MySQL ache que "" é um valor duplicado
        if self.email == "":
            self.email = None

    def save(self, *args, **kwargs):
        # Garantimos a limpeza também no momento do save para segurança total
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)

# =========================================================
# MÓDULO SPEED: TIMELINE & AUDIT TRAIL (HISTÓRICO)
# =========================================================

class RegistroHistorico(models.Model):
    """
    Modelo Polimórfico: Conecta-se a qualquer tabela do sistema (Lead, Parceiro, OS, etc.)
    para registrar comentários, anexos e logs automáticos.
    """
    TIPO_CHOICES = [
        ('comentario', 'Comentário Manual'),
        ('anexo', 'Documento Anexado'),
        ('sistema', 'Log Automático do Sistema'),
    ]

    # NOVO CAMPO: Separa o histórico de ciclos passados
    arquivado = models.BooleanField(default=False)

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='comentario')
    descricao = models.TextField(blank=True, null=True, help_text="Texto do comentário ou descrição do log") 
    arquivo = models.FileField(upload_to='historicos_anexos/%Y/%m/', blank=True, null=True)
    
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    # --- A MÁGICA DA CHAVE GENÉRICA ---
    # Estes três campos formam a ponte universal para qualquer lugar da Speed
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-criado_em'] # O mais recente sempre aparece no topo
        verbose_name = 'Registro de Histórico'
        verbose_name_plural = 'Registros de Histórico'

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.criado_em.strftime('%d/%m/%Y')}"