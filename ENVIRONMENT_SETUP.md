# 🔧 Environment Setup - FinHub

## Переменные окружения для разных этапов

### 📋 Основные переменные (.env файл)

Создайте `.env` файл в корне проекта:

```bash
# FinHub Environment Configuration

# Django Environment (development/production/testing)
DJANGO_ENVIRONMENT=development

# Security
SECRET_KEY=your-secret-key-here-change-in-production

# Debug Mode (True для development, False для production)
DEBUG=True

# Allowed Hosts (comma-separated)
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Configuration
DB_NAME=finhub
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration (for production cache and rate limiting)
REDIS_URL=redis://127.0.0.1:6379/1

# CORS Configuration (for production)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# SSL/Security Settings (for production)
SECURE_SSL_REDIRECT=False

# Email Configuration (for production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=noreply@finhub.com

# Static/Media Files (for production)
STATIC_ROOT=/var/www/finhub/static/
MEDIA_ROOT=/var/www/finhub/media/

# Error Tracking (optional)
SENTRY_DSN=

# Telegram Admin Alerts (optional)
# Comma-separated chat IDs that will receive bot error alerts.
# Example: TELEGRAM_ADMIN_CHAT_IDS=123456789,987654321
TELEGRAM_ADMIN_CHAT_IDS=
```

## 🔄 Переключение между окружениями

### Development (по умолчанию)
```bash
export DJANGO_ENVIRONMENT=development
# или в .env файле:
DJANGO_ENVIRONMENT=development
```

### Production
```bash
export DJANGO_ENVIRONMENT=production
# или в .env файле:
DJANGO_ENVIRONMENT=production
```

### Testing
```bash
export DJANGO_ENVIRONMENT=testing
# или в .env файле:
DJANGO_ENVIRONMENT=testing
```

## ⚙️ Автоматическое определение

Система автоматически определяет окружение:

1. **manage.py** - всегда использует `development`
2. **wsgi.py/asgi.py** - всегда использует `production` 
3. **Переменная DJANGO_ENVIRONMENT** переопределяет defaults

## 🚀 Быстрая настройка

### Для development:
```bash
# 1. Создать .env файл
cp ENVIRONMENT_SETUP.md .env  # скопируйте переменные из этого файла

# 2. Отредактировать под ваши настройки
nano .env

# 3. Запустить
python manage.py runserver
```

### Для production:
```bash
# 1. Установить Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# 2. Настроить .env для production
DJANGO_ENVIRONMENT=production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
# ... остальные production настройки

# 3. Собрать статику
python manage.py collectstatic

# 4. Запустить
gunicorn finhub.wsgi:application
```

## 🎯 Проверка настроек

```bash
# Проверить какие настройки загружены
python manage.py shell -c "from django.conf import settings; print(f'Environment: {settings.ENVIRONMENT if hasattr(settings, \"ENVIRONMENT\") else \"Unknown\"}')"

# Проверить production готовность
export DJANGO_ENVIRONMENT=production
python manage.py check --deploy
``` 