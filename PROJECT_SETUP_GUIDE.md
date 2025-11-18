# 🚀 ПОЛНАЯ ИНСТРУКЦИЯ: Создание нового Django проекта из стартера

## 📋 ЧЕК-ЛИСТ СОЗДАНИЯ НОВОГО ПРОЕКТА

### 1. 🐍 НАСТРОЙКА POETRY ОКРУЖЕНИЯ

```bash
# Деактивировать старое окружение (если активно)
exit  # или deactivate

# Скопировать стартер
cp -r django-starter NEW_PROJECT_NAME
cd NEW_PROJECT_NAME

# Безопасная очистка окружения
rm poetry.lock
poetry install
poetry shell
```

### 2. 🔧 ПЕРЕИМЕНОВАНИЕ ПРОЕКТА (8 мест)

#### 2.1 pyproject.toml
```toml
# ЗАМЕНИТЬ:
name = "trueself"
# НА:
name = "NEW_PROJECT_NAME"
```

#### 2.2 manage.py
```python
# ЗАМЕНИТЬ:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trueself.settings')
# НА:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NEW_PROJECT_NAME.settings')
```

#### 2.3 settings.py (3 места)
```python
# 1. Комментарий в начале файла:
"""
Django settings for NEW_PROJECT_NAME project.

# 2. ROOT_URLCONF:
ROOT_URLCONF = 'NEW_PROJECT_NAME.urls'

# 3. WSGI_APPLICATION:
WSGI_APPLICATION = 'NEW_PROJECT_NAME.wsgi.application'
```

#### 2.4 wsgi.py (2 места)
```python
# 1. Комментарий:
"""
WSGI config for NEW_PROJECT_NAME project.

# 2. Settings:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NEW_PROJECT_NAME.settings')
```

#### 2.5 asgi.py (2 места)
```python
# 1. Комментарий:
"""
ASGI config for NEW_PROJECT_NAME project.

# 2. Settings:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NEW_PROJECT_NAME.settings')
```

#### 2.6 Физическое переименование папки
```bash
# Переименовать основную папку проекта
mv old_project_name NEW_PROJECT_NAME
```

### 3. 🔐 ОБНОВЛЕНИЕ .env ФАЙЛА (КРИТИЧНО!)

#### 3.1 Генерация нового SECRET_KEY
```bash
# Сгенерировать новый ключ
poetry run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### 3.2 Обновление .env файла
```env
# ОБЯЗАТЕЛЬНО ИЗМЕНИТЬ:
SECRET_KEY=your-new-generated-secret-key
DB_NAME=new_project_db
DB_USER=new_project_user

# МОЖНО ОСТАВИТЬ БЕЗ ИЗМЕНЕНИЙ:
DEBUG=True
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 4. ✅ ПРОВЕРКА НАСТРОЙКИ

```bash
# Проверить корректность настроек
poetry run python manage.py check

# Проверить версию Python
poetry run python --version
poetry env info
```

### 5. 🗄️ НАСТРОЙКА БАЗЫ ДАННЫХ

```bash
# Создать и применить миграции
poetry run python manage.py makemigrations
poetry run python manage.py migrate

# Создать суперпользователя (опционально)
poetry run python manage.py createsuperuser
```

### 6. 🚀 ЗАПУСК ПРОЕКТА

```bash
# Запустить сервер разработки
poetry run python manage.py runserver
```

## ⚡ БЫСТРАЯ КОМАНДА (автоматизация)

```bash
# Универсальная замена имени проекта одной командой
find . -name "*.py" -o -name "*.toml" | xargs sed -i 's/OLD_PROJECT_NAME/NEW_PROJECT_NAME/g'
```

## 🛡️ ВАЖНЫЕ ПРАВИЛА БЕЗОПАСНОСТИ

- ✅ **ВСЕГДА** генерируйте новый SECRET_KEY
- ✅ **ВСЕГДА** используйте уникальное имя БД 
- ✅ **ВСЕГДА** используйте уникального пользователя БД
- ✅ **НИКОГДА** не используйте один .env для разных проектов

## 📋 ФИНАЛЬНЫЙ ЧЕК-ЛИСТ

- [ ] 1. Скопировать стартер в новую папку
- [ ] 2. Удалить poetry.lock и переустановить
- [ ] 3. Переименовать проект в 8 местах
- [ ] 4. Сгенерировать новый SECRET_KEY
- [ ] 5. Обновить DB_NAME и DB_USER в .env
- [ ] 6. Выполнить `poetry run python manage.py check`
- [ ] 7. Создать и применить миграции
- [ ] 8. Запустить сервер

**При следовании этой инструкции вы получите полностью готовый к работе Django проект!** 