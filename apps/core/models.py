from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('O nome de usuário é obrigatório')
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
    username = models.CharField('Usuário', max_length=150, unique=True)
    email = models.EmailField('Endereço de E-mail', unique=True, blank=True, null=True) 
    is_gestor = models.BooleanField('É Gestor?', default=False)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email'] 
    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)

class RegistroHistorico(models.Model):
    TIPO_CHOICES = [
        ('comentario', 'Comentário Manual'),
        ('anexo', 'Documento Anexado'),
        ('sistema', 'Log Automático do Sistema'),
    ]

    arquivado = models.BooleanField(default=False)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='comentario')
    
    # AJUSTADOS PARA O ADMIN:
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.TextField('Ação/Descrição', blank=True, null=True) 
    data = models.DateTimeField('Data', auto_now_add=True)
    
    arquivo = models.FileField(upload_to='historicos_anexos/%Y/%m/', blank=True, null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-data']
        verbose_name = 'Registro de Histórico'
        verbose_name_plural = 'Registros de Histórico'