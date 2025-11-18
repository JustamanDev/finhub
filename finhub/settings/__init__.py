"""
Django settings для FinHub проекта.

Автоматическое определение окружения на основе DJANGO_SETTINGS_MODULE.
По умолчанию используется development настройки.
"""

import os

# Определяем окружение на основе DJANGO_SETTINGS_MODULE или переменной окружения
ENVIRONMENT = os.environ.get('DJANGO_ENVIRONMENT', 'development')

if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'testing':
    from .testing import *  # TODO: создать testing.py при необходимости
else:
    from .development import *

print(f"🚀 FinHub загружен с настройками: {ENVIRONMENT.upper()}") 