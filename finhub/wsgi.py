"""
WSGI config for finhub project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Для production используем production настройки
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finhub.settings')
os.environ.setdefault('DJANGO_ENVIRONMENT', 'production')

application = get_wsgi_application()
