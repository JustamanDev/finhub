# FinHub — проект (agent reference)

## Назначение

Личный финансовый хаб: учёт доходов/расходов, бюджеты, цели и конверты, отчёты. Основной UX — Telegram-бот (`500 кофе`, меню, inline-клавиатуры). REST API для будущего фронтенда. Один пользователь — свои деньги. Общих конвертов и подписки нет: это идеи в [ideas.md](ideas.md).

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
| `transactions` | `Transaction` (итог в базовой валюте + валюта ввода), `ExchangeRate` (курс к рублю, ЦБ) |
| `budgets` | `Budget` (plan/fact, лимиты по категории/месяцу) |
| `goals` | `Goal` (`kind`: цель `savings` или конверт `envelope`; `status` включая `archived`), `GoalLedgerEntry` (deposit / withdraw / spend) |
| `recurring` | `RecurringTemplate` — ритм и ожидание, якорь `next_due` |
| `debts` | `Debt`, `DebtPayment` — кому и сколько, без транзакции |
| `telegram_bot` | `TelegramUser` (`base_currency`, `input_currencies`), `UserState`, `BotText`, handlers, services |
| `api` | URL routing v1 |

**Не реализовано:** приложения `accounts`, `trading`, `analytics` и фронтенд. Повторы и долги есть. Список оставшихся идей: [ideas.md](ideas.md).

## Entry points

| Команда | Файл |
|---------|------|
| Web | `manage.py runserver` / gunicorn (prod) |
| Bot | `manage.py run_bot` → `telegram_bot/management/commands/run_bot.py` |
| Migrations | `manage.py migrate` |
| Курс VND→RUB | `manage.py fetch_exchange_rate` |
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

## API

Цели и конверты в REST нет. В `api/urls.py` зарегистрированы только `categories`, `transactions`, `budgets`. Модели `Goal` и `GoalLedgerEntry` в `goals/models.py` доступны из бота.

Тот же роутер висит дважды: `/api/v1/...` и без версии, `/api/...`. `GET /api/` — карточка API (`api_info` в `finhub/urls.py`), не список ресурсов. Документация: `/api/docs/`, `/api/redoc/`, `/api/schema/` и те же пути под `/api/v1/`.

Стандартный CRUD у всех трёх ViewSet (`ModelViewSet`): `GET` список, `POST` создание, `GET/PUT/PATCH/DELETE` по `{id}/`.

Категории — `categories/views.py`:

- `GET /api/v1/categories/income/` — активные доходы
- `GET /api/v1/categories/expense/` — активные расходы
- `GET /api/v1/categories/stats/` — счётчики категорий

Транзакции — `transactions/views.py`:

- `GET /api/v1/transactions/statistics/?period=month|week|year|all`
- `GET /api/v1/transactions/recent/?limit=10`
- `POST /api/v1/transactions/quick_add/`

Бюджеты — `budgets/views.py`:

- `GET /api/v1/budgets/current/` — активные на сегодня
- `GET /api/v1/budgets/overspent/`
- `POST /api/v1/budgets/quick_create/` — месячный бюджет
- `GET /api/v1/budgets/categories_overview/`
- `GET /api/v1/budgets/monthly_summary/?year=&month=`

Auth (djoser, `api/urls.py`): `POST /api/v1/auth/token/login/`, `POST /api/v1/auth/token/logout/`, пользователи на `/api/v1/auth/users/`. Те же пути есть без `v1`.

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
