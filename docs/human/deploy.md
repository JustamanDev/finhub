# Деплой FinHub на VPS

Production-стек: **Docker Compose** — `web` (Django/gunicorn), `bot` (Telegram), `db` (PostgreSQL 16), `redis`.

## Расположение на сервере

| Что | Путь |
|-----|------|
| Код (git) | `/srv/www/finhub/` |
| `.env` (единый источник правды) | `/srv/www/finhub/.env` |
| Compose-файл prod | `/srv/compose/finhub.yml` |

Все сервисы читают **один** `.env`. Не дублировать.

## Первичная установка

### 1. Подготовка сервера

```bash
# Docker + docker compose plugin
# git clone в /srv/www/finhub
```

### 2. Создать `.env`

Пример `/srv/www/finhub/.env`:

```env
DJANGO_ENVIRONMENT=production
DEBUG=False
SECRET_KEY=your-strong-secret-key

DB_NAME=finhub
DB_USER=finhub_user
DB_PASSWORD=very-strong-db-password
DB_HOST=db

ALLOWED_HOSTS=your.domain,localhost
REDIS_URL=redis://redis:6379/1
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
DB_SSLMODE=disable
```

Переменные: [environment.md](environment.md).

### 3. Compose-файл

`finhub.yml` должен:
- `env_file: /srv/www/finhub/.env` для всех сервисов
- `web`: gunicorn на :8000 (или runserver только для dev)
- `bot`: `python manage.py run_bot`
- volumes для postgres_data

Схема — в [PRODUCTION_DOCKER_GUIDE.md](../../PRODUCTION_DOCKER_GUIDE.md) (детальный reference).

### 4. Первый запуск

```bash
cd /srv/compose

docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  up -d --build

docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  exec web python manage.py migrate

docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  exec web python manage.py createsuperuser
```

### 5. Reverse proxy (опционально)

Nginx/Traefik перед `web:8000`, HTTPS через Let's Encrypt. Не входит в репозиторий — настраивается на сервере.

---

## Обновление после `git pull`

**Всегда** используй `--env-file`:

```bash
cd /srv/www/finhub && git pull origin main

cd /srv/compose

docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  up -d --build web bot
```

`db` и `redis` не пересобираются. `--build` подтягивает новый код в образ.

### Миграции

Перед деплоем локально:

```bash
python manage.py makemigrations --check --dry-run
# должно быть "No changes detected"
```

На сервере после deploy:

```bash
docker compose \
  --env-file /srv/www/finhub/.env \
  -f finhub.yml \
  exec web python manage.py migrate
```

Проверки:

```bash
docker compose ... exec web python manage.py showmigrations --plan
docker compose ... exec web python manage.py makemigrations --check --dry-run
```

---

## Типовые операции

### Статус

```bash
cd /srv/compose
docker compose --env-file /srv/www/finhub/.env -f finhub.yml ps
```

### Логи

```bash
docker compose --env-file /srv/www/finhub/.env -f finhub.yml logs web --tail=100
docker compose --env-file /srv/www/finhub/.env -f finhub.yml logs bot --tail=100
docker compose --env-file /srv/www/finhub/.env -f finhub.yml logs bot --since=2m
```

### Перезапуск web + bot (без rebuild)

```bash
docker compose --env-file /srv/www/finhub/.env -f finhub.yml restart web bot
```

Используй после изменения только `.env`.

### Полный restart стека

```bash
docker compose --env-file /srv/www/finhub/.env -f finhub.yml down
docker compose --env-file /srv/www/finhub/.env -f finhub.yml up -d --build
```

---

## Checklist перед production

- [ ] `DEBUG=False`, `DJANGO_ENVIRONMENT=production`
- [ ] Сильный `SECRET_KEY` и пароль БД
- [ ] `ALLOWED_HOSTS` содержит домен
- [ ] `REDIS_URL` настроен (rate limiting в prod)
- [ ] `TELEGRAM_BOT_TOKEN` валиден
- [ ] Миграции закоммичены вместе с изменениями моделей
- [ ] `createsuperuser` создан
- [ ] Логи bot/web без ошибок после старта
- [ ] (Опционально) HTTPS через nginx
- [ ] (Опционально) `TELEGRAM_ADMIN_CHAT_IDS` для алертов

---

## Troubleshooting

| Проблема | Действие |
|----------|----------|
| Bot TimedOut | Увеличить `TELEGRAM_*_TIMEOUT` в `.env`, см. [environment.md](environment.md) |
| DB connection refused | Проверить `DB_HOST=db`, статус контейнера `db` |
| Миграции не применены | `exec web python manage.py migrate` |
| Models have unapplied changes | Создать миграции локально, commit, redeploy |
| SSL к внешней БД | `DB_SSLMODE=require` |

---

## Локальный Docker vs prod

Локально: `docker-compose.yml` в корне репозитория, `.env` в корне, `DJANGO_ENVIRONMENT=development`.

Prod: отдельный `finhub.yml` в `/srv/compose/`, абсолютные пути к `.env`.

Детальный reference с edge cases: [PRODUCTION_DOCKER_GUIDE.md](../../PRODUCTION_DOCKER_GUIDE.md).
