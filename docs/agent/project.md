# FinHub — проект (agent reference)

## Назначение

Личный финансовый хаб: учёт доходов/расходов, бюджеты, цели, отчёты. Основной UX — Telegram-бот (`500 кофе`, меню, inline-клавиатуры). REST API для будущего фронтенда.

## Стек

| Слой | Технология |
|------|------------|
| Backend | Django 4.2, Python 3.11 |
| DB | PostgreSQL 16 |
| Cache / rate limit | Redis 7 (prod) |
| API | DRF, djoser, drf-spectacular |
| Bot | python-telegram-bot 22 (async polling) |
| Deps | Poetry (`pyproject.toml`) |
| Deploy | Docker Compose: web, bot, db, redis |

## Django apps

| App | Модели / роль |
|-----|---------------|
| `core` | `TimestampedModel`, middleware (API version, rate limit logging) |
| `categories` | `Category`, `DefaultCategoryTemplate`; дефолты в `default_categories.py` |
| `transactions` | `Transaction` (amount ±, category, date, description) |
| `budgets` | `Budget` (plan/fact, лимиты по категории/месяцу) |
| `goals` | `Goal`, `GoalLedgerEntry` (конверты, deposit/withdraw) |
| `telegram_bot` | `TelegramUser`, `UserState`, `BotText`, handlers, services |
| `api` | URL routing v1 |

**Не реализовано:** `accounts`, `debts`, `trading`, `analytics`, frontend.

## Entry points

| Команда | Файл |
|---------|------|
| Web | `manage.py runserver` / gunicorn (prod) |
| Bot | `manage.py run_bot` → `telegram_bot/management/commands/run_bot.py` |
| Migrations | `manage.py migrate` |
| Admin | `/admin/` |
| API docs | `/api/docs/`, `/api/redoc/` |

## Settings

```
finhub/settings/
  base.py          # общее
  development.py   # DummyCache, no ratelimit
  production.py    # Redis, django_ratelimit
```

Переключение: `DJANGO_ENVIRONMENT=development|production`

## Docker

`docker-compose.yml`: `web`, `bot`, `db`, `redis`. Единый `.env` в корне.

## API v1 (кратко)

- `GET/POST /api/v1/categories/`
- `GET/POST /api/v1/transactions/`
- `GET/POST /api/v1/budgets/` (+ `current/`)
- Auth: `/api/v1/auth/token/login/`

## Telegram bot — handlers

| Handler | Файл |
|---------|------|
| Commands | `handlers/command_handler.py` |
| Text | `handlers/text_handler.py` |
| Voice | `handlers/voice_handler.py` |
| Callbacks | `handlers/callback_handler.py` (~1600 строк) |
| Budgets | `handlers/budget_handler.py` |
| Goals | `handlers/goals_handler.py` |
| Reports | `handlers/report_handler.py` |
| Settings | `handlers/settings_handler.py` |

Парсер текста: `utils/text_parser.py` — regex `500 кофe`, `+1000 зарплата`.

Сервисы: `services/transaction_service.py`, `report_service.py`, `goal_service.py`.

## Связанные репозитории

- **AudioToText** (`../AudioToText`) — Whisper-транскрибация; код переносится в FinHub для voice feature, не как dependency.
