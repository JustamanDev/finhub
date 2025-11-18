# 🚀 PRODUCTION CHECKLIST - FinHub

## ⚠️ КРИТИЧНО: ВРЕМЕННЫЕ РЕШЕНИЯ ДЛЯ УСТРАНЕНИЯ

### 📋 ОБЯЗАТЕЛЬНЫЕ ДЕЙСТВИЯ ПЕРЕД ДЕПЛОЕМ (DEBUG=False)

#### 🔄 1. НАСТРОЙКА КЭША И RATE LIMITING

**Тригер:** Переход в production (DEBUG=False)

- [ ] **Установить Redis**
  ```bash
  # macOS
  brew install redis
  brew services start redis
  
  # Ubuntu/Debian
  sudo apt-get install redis-server
  sudo systemctl start redis
  ```

- [ ] **Добавить django-redis в зависимости**
  ```bash
  poetry add django-redis
  ```

- [ ] **Заменить DummyCache на Redis в settings.py**
  ```python
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
      }
  }
  ```

- [ ] **УДАЛИТЬ все заглушки django_ratelimit из settings.py**
  ```python
  # УДАЛИТЬ ВЕСЬ ЭТОТ БЛОК:
  if DEBUG:
      RATELIMIT_ENABLE = False
      # TODO: PRODUCTION - убрать заглушки django_ratelimit
      import sys
      from unittest.mock import MagicMock
      # ... весь блок с заглушками
  ```

- [ ] **Включить django_ratelimit в INSTALLED_APPS**
  ```python
  INSTALLED_APPS = [
      # ... другие приложения
      'django_ratelimit',  # Включить постоянно
      # ... остальные
  ]
  ```

- [ ] **Включить RateLimitLoggingMiddleware**
  ```python
  MIDDLEWARE = [
      'corsheaders.middleware.CorsMiddleware',
      'django.middleware.security.SecurityMiddleware',
      'core.middleware.RateLimitLoggingMiddleware',  # Включить постоянно
      # ... остальные
  ]
  ```

- [ ] **Настроить rate limiting**
  ```python
  RATELIMIT_ENABLE = True
  RATELIMIT_USE_CACHE = 'default'
  ```

#### 🔐 2. БЕЗОПАСНОСТЬ

- [ ] **Проверить SECRET_KEY**
  - [ ] Уникальный для production
  - [ ] Хранится в переменных окружения
  - [ ] Не в git репозитории

- [ ] **Настроить HTTPS**
  ```python
  SECURE_SSL_REDIRECT = True
  SECURE_HSTS_SECONDS = 31536000  # 1 год
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  SECURE_HSTS_PRELOAD = True
  ```

- [ ] **Проверить CORS настройки**
  ```python
  CORS_ALLOW_ALL_ORIGINS = False  # В production!
  CORS_ALLOWED_ORIGINS = [
      "https://yourdomain.com",
      # Только разрешенные домены
  ]
  ```

#### 🗄️ 3. БАЗА ДАННЫХ

- [ ] **Настроить production БД**
  - [ ] PostgreSQL с SSL
  - [ ] Пул соединений
  - [ ] Backup стратегия

- [ ] **Проверить миграции**
  ```bash
  python manage.py check --deploy
  python manage.py showmigrations
  ```

#### 📊 4. МОНИТОРИНГ И ЛОГИ

- [ ] **Настроить production логирование**
  ```python
  LOGGING = {
      'version': 1,
      'disable_existing_loggers': False,
      'handlers': {
          'file': {
              'level': 'INFO',
              'class': 'logging.handlers.RotatingFileHandler',
              'filename': '/var/log/finhub/django.log',
              'maxBytes': 1024*1024*15,  # 15MB
              'backupCount': 10,
          },
      },
      'root': {
          'level': 'INFO',
          'handlers': ['file'],
      },
  }
  ```

- [ ] **Настроить мониторинг**
  - [ ] Health check endpoints
  - [ ] Error tracking (Sentry)
  - [ ] Performance monitoring

#### ⚡ 5. ПРОИЗВОДИТЕЛЬНОСТЬ

- [ ] **Статические файлы**
  ```python
  STATIC_ROOT = '/var/www/finhub/static/'
  STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
  ```

- [ ] **Media файлы**
  ```python
  MEDIA_ROOT = '/var/www/finhub/media/'
  ```

- [ ] **Database optimization**
  - [ ] Connection pooling
  - [ ] Query optimization
  - [ ] Indexes проверены

## 🧪 ТЕСТИРОВАНИЕ ПЕРЕД ДЕПЛОЕМ

### 1. Локальное тестирование с production настройками

```bash
# 1. Создать .env.production
cp .env .env.production
# Настроить production переменные

# 2. Тестировать с DEBUG=False
export DJANGO_SETTINGS_MODULE=finhub.settings
export DEBUG=False
python manage.py check --deploy

# 3. Тестировать rate limiting
# Запустить нагрузочные тесты
```

### 2. Staging environment

- [ ] Развернуть на staging с production настройками
- [ ] Протестировать все API endpoints
- [ ] Проверить rate limiting
- [ ] Нагрузочное тестирование

## 🚨 КРИТИЧЕСКИЕ ПРОВЕРКИ

### Перед включением DEBUG=False:

```bash
# Этот скрипт ДОЛЖЕН пройти без ошибок:
export DEBUG=False
python manage.py check --deploy
python manage.py collectstatic --noinput
python manage.py migrate --check
```

### Проверка временных решений:

```bash
# Поиск всех TODO в коде:
grep -r "TODO.*PRODUCTION" .
grep -r "⚠️" .
grep -r "ВРЕМЕННЫЕ" .
```

## 📋 ФИНАЛЬНЫЙ ЧЕКЛИСТ

- [ ] ✅ Redis установлен и работает
- [ ] ✅ django-redis добавлен в зависимости  
- [ ] ✅ DummyCache заменен на RedisCache
- [ ] ✅ Все заглушки django_ratelimit удалены
- [ ] ✅ django_ratelimit включен в INSTALLED_APPS
- [ ] ✅ RateLimitLoggingMiddleware включен
- [ ] ✅ RATELIMIT_ENABLE = True
- [ ] ✅ `python manage.py check --deploy` проходит
- [ ] ✅ Rate limiting тестирован
- [ ] ✅ Все TODO удалены из кода
- [ ] ✅ Staging тестирование пройдено

## 🎯 ТЕКУЩИЙ СТАТУС

**Этап:** Development с временными решениями ✅  
**Следующий этап:** Pre-production подготовка  
**Готовность к production:** ❌ (требует выполнения чеклиста)

---

**⚠️ ВНИМАНИЕ:** Этот файл должен быть проверен перед каждым production деплоем! 