# FinHub – личный финансовый хаб с Telegram‑ботом

FinHub — Django‑приложение для учёта личных финансов с бюджетами, целями и Telegram‑ботом для быстрого ввода операций.

## Документация

| Аудитория | Ссылка |
|-----------|--------|
| **AI-агенты** | [AGENTS.md](AGENTS.md) → [docs/agent/](docs/agent/) |
| **Люди** | [docs/human/README.md](docs/human/README.md) |
| **Деплой на VPS** | [docs/human/deploy.md](docs/human/deploy.md) |
| **Текущий статус** | [docs/agent/state.md](docs/agent/state.md) |

## Быстрый старт (Docker)

```bash
cp .env.example .env   # заполнить TELEGRAM_BOT_TOKEN и др.
docker compose up -d
docker compose exec web python manage.py createsuperuser
```

Подробнее: [docs/human/getting-started.md](docs/human/getting-started.md)

## Стек

Python 3.11 · Django 4.2 · PostgreSQL · Redis · python-telegram-bot · Poetry · Docker

## Основные возможности

- Учёт доходов/расходов с категориями
- Бюджеты и лимиты (план/факт)
- Telegram‑бот: `500 кофe`, меню, отчёты, Excel; **голосовой ввод** (см. `VOICE_ENABLED`)
- Цели (конверты)
- REST API + OpenAPI docs

**Голосовой ввод:** [docs/agent/voice-input.md](docs/agent/voice-input.md) (`VOICE_ENABLED=True` + `OPENAI_API_KEY`)

## Сервисы Docker

`web` · `bot` · `db` · `redis` — см. [docker-compose.yml](docker-compose.yml)

## API

- Swagger: `/api/docs/`
- Примеры: [MVP_API_TESTING.md](MVP_API_TESTING.md), [BUDGET_API_TESTING.md](BUDGET_API_TESTING.md)
