from pathlib import Path
import os
import sys

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Adiciona a pasta 'apps' ao PATH - Isso permite importar 'core' em vez de 'apps.core'
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

SECRET_KEY = 'django-insecure-g*+p+x_hnds@(5j#v-=n6#5^+4-te5s*hn$0qw6ef2l5m$jo17'

#DEBUG = False: Nunca suba para o servidor com DEBUG = True. Isso expõe todo o seu código e senhas se der qualquer erro de tela.
DEBUG = True

ALLOWED_HOSTS = ['*'] # O asterisco permite que rode no localhost e no IP do Servidor

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Se você usa sys.path.insert, o Django espera o nome definido no AppConfig.
    # Para evitar o erro "RuntimeError: Model class... doesn't declare an explicit app_label",
    # use o caminho completo aqui para casar com o que está no apps.py.
    'core',
    'leads',
    'partners',
    'clientes',
    'core_admin',
    'automacoes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Recomendado para templates globais
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

# A ponta do cabo de rede do Django conectando no MySQL do Docker
#DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.mysql',
#        'NAME': 'speed_banco',
#        'USER': 'speed_user',
#        'PASSWORD': 'speed_password',
#        'HOST': 'speed_db', # Nome exato do serviço no docker-compose
#        'PORT': '3306', # Porta interna do container MySQL
#        'OPTIONS': {
#            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#            'charset': 'utf8mb4',
#        }
#    }
#}

# Comente o MySQL temporariamente
# DATABASES = { ... }

# Adicione o SQLite só para criar o app
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- AJUSTES DE LOCALIZAÇÃO (IMPORTANTE) ---
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza' # Ajustado para sua localização
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- AUTENTICAÇÃO ---
AUTH_USER_MODEL = 'core.User'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

# ==========================================
# UPLOADS E ARQUIVOS DE MÍDIA (SPEED)
# ==========================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Diretório onde o Django vai juntar todo o CSS/JS para o Docker ler
STATIC_ROOT = BASE_DIR / 'staticfiles'
# (Opcional) Deixa os arquivos estáticos cacheados e comprimidos para o sistema voar!
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Permite que o Django aceite cookies e formulários vindo desses endereços
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8003",
    "http://127.0.0.1:8003",
    "http://192.168.18.65:8003", # Seu IP local (Ceará)
    "https://speed.ageis.com.br",  # <-- O seu domínio real no servidor
    "http://192.168.90.202:8003",  # <-- O IP da sua VPS/Servidor
]

# Garante que o cookie de sessão funcione no Docker
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# 1. Tempo de expiração em segundos (10 minutos = 600 segundos)
SESSION_COOKIE_AGE = 600

# 2. Faz o cronômetro resetar toda vez que o usuário mexer no sistema (Inatividade)
SESSION_SAVE_EVERY_REQUEST = True

# 3. Faz o cookie expirar assim que o usuário fechar o navegador (Segurança Extra)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True