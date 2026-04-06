import os
import sys
from pathlib import Path

from decouple import config
from dotenv import load_dotenv

# ============================================
#  CARREGA VARIÁVEIS DE AMBIENTE
# ============================================
load_dotenv()
USE_AD_AUTH = os.getenv("USE_AD_AUTH", "false").lower() == "true"

if USE_AD_AUTH:
    try:
        import ldap
        from django_auth_ldap.config import LDAPSearch
    except ImportError:
        USE_AD_AUTH = False

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Adiciona a pasta 'apps' ao PATH
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

SECRET_KEY = 'django-insecure-g*+p+x_hnds@(5j#v-=n6#5^+4-te5s*hn$0qw6ef2l5m$jo17'

# SEGURANÇA: Mude para False em produção para o WhiteNoise funcionar 100%
DEBUG = False

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
    'whitenoise.middleware.WhiteNoiseMiddleware', # Essencial para arquivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
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
        'NAME': config('DB_NAME', default='speed_banco'),
        'USER': config('DB_USER', default='speed_user'),
        'PASSWORD': config('DB_PASSWORD', default='speed_password'),
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
if USE_AD_AUTH:
    AUTHENTICATION_BACKENDS = [
        "django_auth_ldap.backend.LDAPBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    AUTH_LDAP_SERVER_URI = os.getenv("AD_SERVER_URI")
    AUTH_LDAP_BIND_DN = os.getenv("AD_BIND_DN")
    AUTH_LDAP_BIND_PASSWORD = os.getenv("AD_BIND_PASSWORD")

    # Busca de usuários
    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        os.getenv("AD_USER_SEARCH_BASE"),
        ldap.SCOPE_SUBTREE,
        "(sAMAccountName=%(user)s)",
    )

    # --- TRAVA DE SEGURANÇA POR GRUPO ---
    # Somente usuários deste grupo no AD poderão logar no SGP Speed
# --- TRAVA DE SEGURANÇA POR GRUPO ---
    # Comente a linha abaixo para permitir que qualquer usuário do AD logue
    # Quando o grupo for criado, é só remover o '#' abaixo.
    
    # AUTH_LDAP_REQUIRE_GROUP = "CN=Acesso_SGP,OU=Grupos,DC=howbe,DC=local"

    # Configurações de Grupo
    #AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
    #    os.getenv("AD_GROUP_SEARCH_BASE"),
    #    ldap.SCOPE_SUBTREE,
    #    "(objectClass=group)",
    #)
    #AUTH_LDAP_GROUP_TYPE = ActiveDirectoryGroupType()

    # Mapeamento de atributos (Corrigido: displayName para pegar nome completo)
    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": "displayName", 
        "last_name": "sn",
        "email": "mail",
    }

    # DE:
    #AUTH_LDAP_ALWAYS_UPDATE_USER = True
    #AUTH_LDAP_MIRROR_GROUPS = True

    # PARA:
    AUTH_LDAP_ALWAYS_UPDATE_USER = False
    AUTH_LDAP_MIRROR_GROUPS = False

    AUTH_LDAP_USER_DOMAIN = os.getenv("AD_DEFAULT_DOMAIN")

    AUTH_LDAP_CONNECTION_OPTIONS = {
        ldap.OPT_REFERRALS: 0,
    }
else:
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]

# ==========================================
# 📁 ARQUIVOS ESTÁTICOS E MÍDIA
# ==========================================
STATIC_URL = 'static/'

# Onde o Django busca arquivos durante o desenvolvimento
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Onde o Django joga os arquivos para o servidor ler (Produção)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Armazenamento com compressão para performance
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

# Segurança de Sessão (10 minutos)
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8003",
    "http://127.0.0.1:8003",
    "http://192.168.90.202:8090",
]
