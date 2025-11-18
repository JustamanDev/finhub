"""
ASGI config for finhub project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Для production используем production настройки
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finhub.settings')
os.environ.setdefault('DJANGO_ENVIRONMENT', 'production')

application = get_asgi_application()
