"""
Production настройки для FinHub проекта.
Оптимизированы для production с Redis кэшем, rate limiting и enhanced безопасностью.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config(
    'DEBUG', 
    default=False, 
    cast=bool,
    )

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# Production-specific apps (с django_ratelimit)
INSTALLED_APPS = INSTALLED_APPS + [
    'django_ratelimit',
]

# Production-specific middleware (с rate limiting)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.RateLimitLoggingMiddleware',  # Rate limiting middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.APIVersioningMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Redis cache for production
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 20,
                'retry_on_timeout': True,
            },
        },
        'KEY_PREFIX': 'finhub',
        'VERSION': 1,
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Rate limiting enabled for production
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# CORS настройки для production (строгие)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://yourdomain.com',
    cast=lambda x: x.split(',')
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-api-version',
]

# Enhanced security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_HSTS_SECONDS = 31536000  # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Additional security headers
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Production logging
LOG_DIR = config('LOG_DIR', default='./logs')

# Создаем директорию для логов если не существует
import os
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
            'style': '%',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'django_errors.log'),
            'maxBytes': 1024*1024*15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'finhub': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file'],
    },
}

# Production email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@finhub.com')

# Static files for production
STATIC_ROOT = config('STATIC_ROOT', default='/var/www/finhub/static/')
MEDIA_ROOT = config('MEDIA_ROOT', default='/var/www/finhub/media/')
MEDIA_URL = '/media/'

# Performance settings for production
USE_TZ = True

# Database connection pooling and optional SSL for production
DB_SSLMODE = config('DB_SSLMODE', default='disable')

DATABASES['default'].update({
    'CONN_MAX_AGE': 600,  # 10 minutes
    'OPTIONS': {
        'sslmode': DB_SSLMODE,
    },
})

# Error tracking (if using Sentry)
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), sentry_logging],
        traces_sample_rate=0.1,
        send_default_pii=True
    )

print("🚀 Production settings loaded successfully!") 