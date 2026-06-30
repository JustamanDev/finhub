# Быстрый старт

## Требования

- Python 3.11
- Poetry
- Docker + Docker Compose (рекомендуется)
- PostgreSQL (если без Docker)

## Вариант A — Docker (рекомендуется)

### 1. Клонировать и создать `.env`

```env
SECRET_KEY=your-secret-key
DJANGO_ENVIRONMENT=development
DEBUG=True

DB_NAME=finhub_db
DB_USER=finhub_user
DB_PASSWORD=finhub_password
DB_HOST=db
DB_PORT=5432

ALLOWED_HOSTS=localhost,127.0.0.1
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
REDIS_URL=redis://redis:6379/1
```

Полный список переменных: [environment.md](environment.md).

### 2. Запуск

```bash
docker compose build
docker compose up -d
docker compose ps
```

Сервисы:
- `web` — http://localhost:8000
- `bot` — Telegram-бот
- `db` — PostgreSQL
- `redis` — Redis

### 3. Первичная настройка

```bash
docker compose exec web python manage.py createsuperuser
docker compose logs bot --tail=50
```

Админка: http://localhost:8000/admin/

## Вариант B — Poetry (без Docker)

```bash
poetry install
poetry shell
cp .env.example .env   # или создай .env вручную
# DB_HOST=localhost в .env

python manage.py migrate
python manage.py runserver
```

Бот — **отдельный процесс**:

```bash
python manage.py run_bot
```

## Проверка бота

1. Найди бота в Telegram по username из BotFather
2. `/start` — регистрация и дефолтные категории
3. Отправь `500 кофe` — должна создаться транзакция

## Полезные команды

```bash
# Логи
docker compose logs web --tail=100
docker compose logs bot --tail=100

# Тесты
python manage.py test

# Миграции
python manage.py makemigrations
python manage.py migrate
```

## API

- Документация: http://localhost:8000/api/docs/
- Примеры: [MVP_API_TESTING.md](../../MVP_API_TESTING.md)

## Деплой на сервер

См. [deploy.md](deploy.md).
