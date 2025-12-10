# 🚀 Руководство по продакшн‑запуску Docker‑стека FinHub

Этот файл описывает **правильный способ работы с Docker‑контейнерами на продакшн‑сервере**.  
Цель — единый `.env`, предсказуемый старт/рестарт стека и минимум ручной магии.

---

## 1. Расположение ключевых файлов на сервере

- **Код проекта (read‑only):**
  - `/srv/www/finhub/` — корень проекта (git‑репозиторий, `manage.py`, `Dockerfile`, и т.д.)
- **Единый `.env` (источник правды для переменных окружения):**
  - `/srv/www/finhub/.env`
- **Продакшн‑compose файл:**
  - `/srv/compose/finhub.yml`

> **Важно:** `.env` не дублируем. Все сервисы (web, bot, db, redis) и `docker compose`
> получают переменные только из `/srv/www/finhub/.env`.

---

## 2. Структура `.env` для продакшна

Пример `/srv/www/finhub/.env`:

```env
# Django / БД
DJANGO_ENVIRONMENT=production
DEBUG=False
SECRET_KEY=your-strong-secret-key

DB_NAME=finhub
DB_USER=finhub_user
DB_PASSWORD=very-strong-db-password
DB_HOST=db

ALLOWED_HOSTS=your.domain,localhost

# Redis / Bot
REDIS_URL=redis://redis:6379/1
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# SSL к БД (опционально)
# DB_SSLMODE=disable    # по умолчанию: disable (контейнерный Postgres в одной сети)
# DB_SSLMODE=require    # если используем внешний managed Postgres с TLS
```

---

## 3. Требования к `finhub.yml` (prod‑docker‑compose)

Ключевые моменты (схематично):

```yaml
services:
  db:
    image: postgres:16
    env_file:
      - /srv/www/finhub/.env
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: /srv/www/finhub
    env_file:
      - /srv/www/finhub/.env
    environment:
      DJANGO_ENVIRONMENT: production
      DB_HOST: db
      REDIS_URL: redis://redis:6379/1
    # gunicorn или другой WSGI‑сервер на 8000
    # ports / reverse proxy настраиваются отдельно (nginx/traefik)

  bot:
    build: /srv/www/finhub
    env_file:
      - /srv/www/finhub/.env
    environment:
      DJANGO_ENVIRONMENT: production
      DB_HOST: db
      REDIS_URL: redis://redis:6379/1

  redis:
    image: redis:7

volumes:
  postgres_data:
```

> **Идея:** все сервисы читают один и тот же `.env`, а значения `DB_*` переиспользуются
> и Django, и Postgres‑контейнером.

---

## 4. Базовые команды управления стеком

Всегда используем **одну и ту же форму** команд с `--env-file`:

```bash
cd /srv/compose

# Первичный запуск / обновление образов
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  up -d --build

# Просмотр статуса
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  ps

# Перезапуск только web и bot
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  restart web bot

# Остановка стека
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  down
```

---

## 5. Типичные проверки после деплоя

1. **Статус контейнеров**

```bash
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  ps
```

Ожидаемое состояние: `Up` для `db`, `web`, `bot`, `redis`.

2. **Логи БД (пароль / доступность)**

```bash
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  logs db --since=2m
```

Не должно быть ошибок про `FATAL: password authentication failed` или пустой пароль.

3. **Логи web (подключение к БД / SSL)**

```bash
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  logs web --since=2m
```

- Нет ошибок `could not translate host name "db"`  
- Нет ошибок SSL к БД, если `DB_SSLMODE=disable` и используется внутренний Postgres.

4. **Логи бота**

```bash
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  logs bot --since=2m
```

- Бот пишет, что запущен и готов к работе  
- Нет циклических падений по подключению к БД.

---

## 6. Best practices для продакшн‑окружения

- **Один `.env` на проект** — `/srv/www/finhub/.env`, без копий и дублей.
- **Никаких секретов в git** — `.env` всегда в `.gitignore`.
- Все сервисы читают переменные из одного места (`env_file` + `--env-file`).
- Для SSL к БД:
  - В контейнерной сети по умолчанию используем `DB_SSLMODE=disable`.
  - При подключении к внешнему Postgres включаем `DB_SSLMODE=require` только в `.env`.
- Любые изменения в настройках сначала вносим в git‑репозиторий (код/compose/гайды),
  затем деплоим и обновляем `Summary.md`.


