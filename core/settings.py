import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SEGURANÇA
# ============================================
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-dev-local-key')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*,localhost,127.0.0.1,.onrender.com,.vercel.app').split(',')

# ============================================
# APPS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Terceiros
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # Local
    'api.apps.ApiConfig',
]

# ============================================
# MIDDLEWARE OTIMIZADO
# ============================================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Primeiro!
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # 🔥 adiciona isto
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ============================================
# BANCO DE DADOS - OTIMIZADO
# ============================================
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR}/db.sqlite3'),
        conn_max_age=600,           # Pool de conexões (10 min)
        conn_health_checks=True,    # Verificar saúde da conexão
    )
}

# Configurar pool de conexões
if not DEBUG:
    DATABASES['default']['OPTIONS'] = {
        'sslmode': 'require',
        'connect_timeout': 10,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    }

# ============================================
# CACHE COM REDIS (OPCIONAL - MELHORA MUITO)
# ============================================
REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'PARSER_CLASS': 'redis.connection.HiredisParser',
                'CONNECTION_POOL_KWARGS': {
                    'max_connections': 100,
                    'retry_on_timeout': True,
                }
            },
            'KEY_PREFIX': 'secure_msg',
            'TIMEOUT': 300,  # 5 minutos default
        }
    }
    # Usar Redis para sessões também
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

# ============================================
# PASSWORD VALIDATION
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# INTERNACIONALIZAÇÃO
# ============================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ============================================
# ARQUIVOS ESTÁTICOS - OTIMIZADO
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Whitenoise - Cache para arquivos estáticos
WHITENOISE_MAX_AGE = 31536000  # 1 ano
WHITENOISE_ALLOW_ALL_ORIGINS = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# CORS - CORRIGIDO PARA PRODUÇÃO
# ============================================
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = True  # Permitir tudo (depois restrinja)
    CORS_ALLOWED_ORIGINS = [
        "https://secure-messaging-frontend.vercel.app",
        "https://*.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with',
]

CSRF_TRUSTED_ORIGINS = [
    "https://secure-messaging-frontend.vercel.app",
    "https://*.vercel.app",
    "https://*.onrender.com",
]

# ============================================
# REST FRAMEWORK - OTIMIZADO
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    # Paginação para listas grandes
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    # Throttling (rate limiting)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
    # Cache de respostas
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ============================================
# SEGURANÇA EM PRODUÇÃO
# ============================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ============================================
# LOGGING - MONITORAMENTO
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'api': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ============================================
# CONFIGURAÇÕES DE PERFORMANCE
# ============================================
# Tamanho máximo de upload
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Número máximo de parâmetros GET/POST
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Conexões simultâneas
CONN_MAX_AGE = 600

# Desabilitar middleware desnecessário em produção
if not DEBUG:
    SILENCED_SYSTEM_CHECKS = ['security.W001', 'security.W008']
