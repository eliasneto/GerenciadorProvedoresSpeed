from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O e-mail é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField('Endereço de E-mail', unique=True) # O unique=True é obrigatório aqui
    
    # Adicione os campos que você deseja usar no lugar dos antigos
    is_gestor = models.BooleanField('É Gestor?', default=False)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()

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