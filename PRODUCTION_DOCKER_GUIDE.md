# PRODUCTION_DOCKER_GUIDE.md (redirect)

> **Краткий гайд:** [docs/human/deploy.md](docs/human/deploy.md)

> Ниже — полный детальный reference (оригинал).

---



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

### 4.1. Типовой сценарий: деплой нового кода (после `git pull`)

**Сценарий:** ты поменял код в Git (или смержил pull request) и хочешь, чтобы на проде поехала новая версия.

#### 4.1.0. Важно про миграции (чтобы не ловить сюрпризы на проде)

**Правило:** если ты менял `models.py` (добавил поля/таблицы/индексы/constraints) — миграции должны быть **созданы и закоммичены** вместе с кодом.

- **Перед пушем / перед деплоем (локально или в CI):**

  ```bash
  # Должно быть пусто. Если Django предлагает миграции — значит ты забыл их создать/закоммитить
  python manage.py makemigrations --check --dry-run
  ```

- **Если команда выше показывает, что есть изменения (значит миграций не хватает):**

  ```bash
  # 1) Сгенерировать миграции локально
  python manage.py makemigrations

  # 2) Убедиться, что миграции создались и попали в git
  git status

  # 3) Закоммитить и запушить миграции вместе с кодом
  git add .
  git commit -m "Add migrations"
  git push
  ```

- **Почему это критично:** Django сравнивает **состояние моделей** и **состояние миграций**.  
  Если они расходятся, на проде можно получить предупреждения вида:
  - `Your models in app(s) ... have changes that are not yet reflected in a migration`

- **Как избежать ложных “изменений” без реальной смены схемы:**
  - **Не редактируй миграции вручную** (если это не осознанная операция с пониманием последствий).
  - Для `models.Index(...)` и `UniqueConstraint(...)` **задавай `name=` явно**.  
    Иначе Django может “по‑разному” сериализовать/именовать объект, и он будет считать, что модели “изменились”, хотя таблица та же.

1. **Подключиться к серверу по SSH**

   ```bash
   ssh your-user@your-server
   ```

2. **Обновить код проекта из Git**

   ```bash
   cd /srv/www/finhub
   git pull origin main      # или другая нужная ветка
   ```

3. **Пересобрать образ и перезапустить только `web` и `bot`**

   ```bash
   cd /srv/compose

   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     up -d --build web bot
   ```

   - `--build` гарантирует, что образ будет пересобран с новым кодом.
   - `web` и `bot` перезапускаются, **БД и Redis не трогаем**.

4. **Применить миграции (если менялась схема БД)**

   > Этот шаг безопасен: Django применяет только отсутствующие миграции.

   ```bash
   cd /srv/compose

   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     exec web python manage.py migrate
   ```

   Полезные проверки, если есть сомнения:

   ```bash
   # Посмотреть план миграций
   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     exec web python manage.py showmigrations --plan

   # Проверить, что у Django нет “неотраженных” изменений моделей (должно быть No changes detected)
   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     exec web python manage.py makemigrations --check --dry-run
   ```

5. **Проверить статус контейнеров**

   ```bash
   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     ps
   ```

6. **(Опционально) посмотреть логи, если что‑то пошло не так**

   ```bash
   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     logs web --since=2m

   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     logs bot --since=2m
   ```

### 4.2. Если изменился только `.env` (настройки, токены и т.п.)

**Сценарий:** ты поправил `/srv/www/finhub/.env`, но код не менял.

1. Убедиться, что `.env` сохранён.
2. Перезапустить нужные сервисы **без пересборки образа**:

   - Если поменялись только переменные для Django/бота:

     ```bash
     cd /srv/compose

     docker compose \
       --env-file /srv/www/finhub/.env \
       -f finhub.yml \
       restart web bot
     ```

   - Если поменялись переменные БД (пароль и т.п.):

     ```bash
     cd /srv/compose

     docker compose \
       --env-file /srv/www/finhub/.env \
       -f finhub.yml \
       restart db web bot
     ```

### 4.3. Полная перезагрузка всего стека

**Сценарий:** нужно “перезапустить всё” (редко, но бывает).

1. Остановить стек:

   ```bash
   cd /srv/compose

   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     down
   ```

2. Запустить заново (с пересборкой образов):

   ```bash
   docker compose \
     --env-file /srv/www/finhub/.env \
     -f finhub.yml \
     up -d --build
   ```

3. Проверить статус и логи (как в разделах 4.1 и 5).

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

## 7. Как убедиться, что не запущены старые контейнеры

**Цель:** чтобы работал только новый стек (`compose-*`), а старые контейнеры (`finhub-*`) не мешали.

1. **Посмотреть все контейнеры, связанные с проектом**

   ```bash
   docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'finhub|compose' || true
   ```

2. **Убедиться, что активны только контейнеры вида `compose-web-1`, `compose-bot-1`, `compose-db-1`, `compose-redis-1`.**

   - Если видишь контейнеры вида `finhub-web-1`, `finhub-bot-1` и т.п. — это старый стек.

3. **Остановить старые контейнеры и отключить автозапуск**

   Пример (названия подставить по факту вывода `docker ps`):

   ```bash
   # остановить старые контейнеры
   docker stop finhub-web-1 finhub-bot-1 finhub-db-1 finhub-redis-1 2>/dev/null || true

   # запретить им автоматически стартовать
   docker update --restart=no finhub-web-1 finhub-bot-1 finhub-db-1 finhub-redis-1 2>/dev/null || true
   ```

4. **Если старый стек запускался через отдельный compose‑файл**

   Если ты знаешь путь к старому `docker-compose.yml` / `finhub-old.yml`:

   ```bash
   cd /path/to/old/compose

   docker compose down
   ```

5. **Проверить, нет ли systemd‑юнитов для старого стека**

   ```bash
   systemctl list-units | grep -i finhub || true
   ```

   Если найдутся старые сервисы, их можно выключить:

   ```bash
   sudo systemctl disable --now finhub-bot.service    # пример имени
   sudo systemctl disable --now finhub-web.service
   ```

После этого при перезагрузке сервера должен автоматически подниматься только стек, который ты управляешь через `/srv/compose/finhub.yml`.


