import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from decouple import config

# ============================================
#  CARREGA VARIÁVEIS DE AMBIENTE
# ============================================
load_dotenv()

# Forçamos False para ignorar a biblioteca LDAP que está dando erro
USE_AD_AUTH = False 

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Adiciona a pasta 'apps' ao PATH
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

SECRET_KEY = 'django-insecure-g*+p+x_hnds@(5j#v-=n6#5^+4-te5s*hn$0qw6ef2l5m$jo17'

# SEGURANÇA: Mude para False em produção para o WhiteNoise funcionar 100%
DEBUG = True # Voltei para True para você ver erros detalhados se ocorrerem

ALLOWED_HOSTS = ['*'] 

# ============================================
#  APLICAÇÕES (INSTALLED_APPS)
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Suas Apps
    'core',
    'leads',
    'partners',
    'clientes',
    'core_admin',
    'backoffice',
]

# ============================================
#  MIDDLEWARES
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'core.middleware.RestoreBackupUploadGuardMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ==========================================
# 💾 BANCO DE DADOS (MySQL)
# ==========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='speed_prod'),
        'USER': config('DB_USER', default='speed_app'),
        'PASSWORD': config('DB_PASSWORD', default='SpeedApp!2026#Prod'),
        'HOST': config('DB_HOST', default='speed_db'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# ============================================
# 🌐 CONFIGURAÇÃO DE AUTENTICAÇÃO (AD / LDAP)
# ============================================
# O Bloco de LDAP foi removido/desativado para evitar erro de importação
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# ==========================================
# 📁 ARQUIVOS ESTÁTICOS E MÍDIA
# ==========================================
# 1. Coloque a barra ANTES da palavra static
STATIC_URL = '/static/' 

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# 2. Desative o Manifest do WhiteNoise enquanto estiver desenvolvendo (DEBUG=True)
if DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==========================================
# 🌍 LOCALIZAÇÃO E SEGURANÇA
# ==========================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

SESSION_COOKIE_AGE = 3600 # Aumentado para 1 hora para facilitar seu teste
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8003",
    "http://127.0.0.1:8003",
    "http://192.168.90.202:8090",
    "http://192.168.90.202:8091",
    "http://192.168.90.203:8091",
]

# Permite uploads grandes para restauracao de backup sem o Django bloquear com 400.
DATA_UPLOAD_MAX_MEMORY_SIZE = None
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "core.middleware": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps.core.middleware": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
