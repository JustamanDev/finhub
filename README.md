# FinHub – личный финансовый хаб с Telegram‑ботом

FinHub — это Django‑приложение для учёта личных финансов с поддержкой бюджетов, аналитики и удобным Telegram‑ботом для быстрого ввода операций.

Проект ориентирован на чистую архитектуру, production‑ready настройки и деплой через Docker.

---

## Основные возможности

- **Учёт финансов**
  - Доходы и расходы с категориями
  - История транзакций, суммы, даты, комментарии

- **Бюджеты и лимиты**
  - Месячные бюджеты по категориям
  - План/факт, остаток, проценты выполнения
  - Отображение превышения бюджета

- **Telegram‑бот**
  - Быстрый ввод сумм: `500 кофе`, `+10000 зарплата` и т.п.
  - Выбор категорий, переключение между доходами и расходами
  - Редактирование даты и комментария транзакции
  - Навигация по меню: «Главное меню», «Назад», действия с транзакцией

- **API (Django REST Framework)**
  - Категории, транзакции, бюджеты
  - Документация (drf‑spectacular / OpenAPI)

- **Production‑ready архитектура**
  - Разделённые настройки: `base.py`, `development.py`, `production.py`
  - Поддержка Redis для кэша и rate limiting (в продакшене)
  - Docker‑стек: `web` (Django), `bot` (Telegram‑бот), `db` (Postgres), `redis`

Подробное состояние проекта и история изменений — в `Summary.md`.

---

## Технологический стек

- **Backend**: Python 3.11, Django 4.2
- **База данных**: PostgreSQL
- **API**: Django REST Framework, drf‑spectacular
- **Кэш / Rate limiting**: Redis, django‑redis, django‑ratelimit (в продакшене)
- **Бот**: python‑telegram‑bot
- **Управление зависимостями**: Poetry
- **Контейнеризация**: Docker, docker‑compose

---

## Локальная разработка (через Poetry, без Docker)

Требования:
- Python 3.11
- Poetry
- Локальный PostgreSQL (или корректно настроенный `.env`)

### Шаги

```bash
git clone <URL_репозитория> finhub
cd finhub

poetry install
poetry shell
```

Создай `.env` в корне проекта (см. также `ENVIRONMENT_SETUP.md`):

```env
SECRET_KEY=your-secret-key
DEBUG=True
DJANGO_ENVIRONMENT=development

DB_NAME=finhub_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

ALLOWED_HOSTS=localhost,127.0.0.1
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

Применить миграции и запустить сервер разработки:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Создать суперпользователя:

```bash
python manage.py createsuperuser
```

Админка будет доступна по адресу `http://localhost:8000/admin/`.

> **Важно:** Telegram‑бот в dev‑режиме запускается отдельной командой:
>
> ```bash
> python manage.py run_bot
> ```

---

## Локальный запуск через Docker (рекомендуемый способ)

Требования:
- Docker + docker compose

### 1. Создать `.env`

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

### 2. Собрать и запустить контейнеры

```bash
docker compose build
docker compose up -d
docker compose ps
```

Будут подняты сервисы:
- `web` – Django (`runserver` в dev‑режиме)
- `bot` – Telegram‑бот (`manage.py run_bot`)
- `db` – PostgreSQL
- `redis` – Redis

### 3. Доступы

- Приложение: `http://localhost:8000`
- Админка: `http://localhost:8000/admin/`

Создание суперпользователя (из контейнера `web`):

```bash
docker compose exec web python manage.py createsuperuser
```

Просмотр логов:

```bash
docker compose logs web --tail=100
docker compose logs bot --tail=100
```

---

## Ключевые переменные окружения

Основные переменные `.env` (подробнее см. `ENVIRONMENT_SETUP.md`):

- `SECRET_KEY` — секретный ключ Django.
- `DEBUG` — режим отладки (`True/False`).
- `DJANGO_ENVIRONMENT` — окружение (`development` или `production`).
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — параметры PostgreSQL.
- `ALLOWED_HOSTS` — список хостов, с которых разрешён доступ.
- `TELEGRAM_BOT_TOKEN` — токен Telegram‑бота.
- `REDIS_URL` — URL Redis для кэша/limiting (особенно в продакшене).

---

## Деплой на VPS (очень кратко)

Полная детальная инструкция по деплою (от `git clone` до `docker compose up`) описана в `Summary.md`. Общая схема:

1. **Локально**
   - Настроить проект, убедиться, что всё работает.
   - Закоммитить в git и отправить на GitHub/GitLab.
2. **На VPS**
   - Установить Docker и docker compose.
   - Клонировать репозиторий в `~/projects/finhub`.
   - Создать `.env` с продакшн‑переменными (`DJANGO_ENVIRONMENT=production`, данные БД, `TELEGRAM_BOT_TOKEN`, `REDIS_URL`).
   - Запустить стек: `docker compose build && docker compose up -d`.
   - Создать суперпользователя: `docker compose exec web python manage.py createsuperuser`.
3. **При необходимости**
   - Повесить домен и настроить nginx + HTTPS (Let’s Encrypt).

---

## Полезные файлы документации

- `Summary.md` — текущее состояние проекта, история изменений, roadmap.
- `PROJECT_SETUP_GUIDE.md` — запуск проекта из стартового шаблона.
- `MVP_API_TESTING.md` / `BUDGET_API_TESTING.md` — примеры запросов к API.
- `ENVIRONMENT_SETUP.md` — описание переменных окружения и вариантов конфигурации.

Эти файлы помогут быстро вкатиться в проект, понять архитектуру и повторить настройку окружения.