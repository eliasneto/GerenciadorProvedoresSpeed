import os
import sys
import ldap
from pathlib import Path
from dotenv import load_dotenv
from decouple import config
from django_auth_ldap.config import (
    LDAPSearch,
    ActiveDirectoryGroupType,
    LDAPGroupQuery,
)

# ============================================
# 🔧 VARIÁVEIS DE AMBIENTE
# ============================================
load_dotenv()
USE_AD_AUTH = os.getenv("USE_AD_AUTH", "false").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

SECRET_KEY = 'django-insecure-CHANGE-ME'
DEBUG = False
ALLOWED_HOSTS = ['*']

# ============================================
# 📦 APPS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'core',
    'leads',
    'partners',
    'clientes',
    'core_admin',
    'backoffice',
]

# ============================================
# 🧱 MIDDLEWARE
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
# 💾 DATABASE
# ==========================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}

# ============================================
# 🌐 LDAP / ACTIVE DIRECTORY
# ============================================
if USE_AD_AUTH:
    AUTHENTICATION_BACKENDS = [
        "django_auth_ldap.backend.LDAPBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    AUTH_LDAP_SERVER_URI = os.getenv("AD_SERVER_URI")
    AUTH_LDAP_BIND_DN = os.getenv("AD_BIND_DN")
    AUTH_LDAP_BIND_PASSWORD = os.getenv("AD_BIND_PASSWORD")

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        os.getenv("AD_USER_SEARCH_BASE"),
        ldap.SCOPE_SUBTREE,
        "(sAMAccountName=%(user)s)",
    )

    AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
        os.getenv("AD_GROUP_SEARCH_BASE"),
        ldap.SCOPE_SUBTREE,
        "(objectClass=group)",
    )

    AUTH_LDAP_GROUP_TYPE = ActiveDirectoryGroupType()

    # 🔐 Grupos permitidos
    grupo_sistema = os.getenv("AD_GROUP_SGP_SISTEMA")
    grupo_lastmile = os.getenv("AD_GROUP_SGP_LASTMILE")
    grupo_backoffice = os.getenv("AD_GROUP_SGP_BACKOFFICE")

    queries = []
    for g in [grupo_sistema, grupo_lastmile, grupo_backoffice]:
        if g:
            queries.append(LDAPGroupQuery(g))

    if queries:
        grupos_permitidos = queries[0]
        for q in queries[1:]:
            grupos_permitidos = grupos_permitidos | q

        AUTH_LDAP_REQUIRE_GROUP = grupos_permitidos

        AUTH_LDAP_USER_FLAGS_BY_GROUP = {
            "is_staff": grupos_permitidos,
        }

    AUTH_LDAP_USER_ATTR_MAP = {
        "first_name": "givenName",
        "last_name": "sn",
        "email": "mail",
    }

    AUTH_LDAP_ALWAYS_UPDATE_USER = True
    AUTH_LDAP_MIRROR_GROUPS = True
    AUTH_LDAP_CONNECTION_OPTIONS = {ldap.OPT_REFERRALS: 0}

else:
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]

# ==========================================
# 📁 STATIC / MEDIA
# ==========================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ==========================================
# 🌍 LOCALE
# ==========================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Fortaleza'
USE_I18N = True
USE_TZ = False

# ==========================================
# 🔐 AUTH
# ==========================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.User'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'

SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ==========================================
# 🛡️ CSRF
# ==========================================
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8003",
    "http://127.0.0.1:8003",
    "http://192.168.90.202:8090",
]

# ==========================================
# 🪵 LOGS (LDAP DEBUG)
# ==========================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django_auth_ldap": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "ldap": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}