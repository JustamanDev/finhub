# FinHub — инструкция для AI-агентов

> Читай этот файл первым. Документация оптимизирована под агентскую работу: плотный формат, явные пути, без дублирования.

## Быстрый старт (что читать)

| Приоритет | Файл | Когда |
|-----------|------|-------|
| 1 | [docs/agent/state.md](docs/agent/state.md) | Текущий статус, активная работа, блокеры |
| 2 | [docs/agent/project.md](docs/agent/project.md) | Стек, приложения, entry points |
| 3 | [docs/agent/architecture.md](docs/agent/architecture.md) | Потоки данных, ключевые модули |
| 4 | [docs/agent/conventions.md](docs/agent/conventions.md) | Куда класть код, паттерны |
| 5 | [docs/agent/roadmap.md](docs/agent/roadmap.md) | Фазы и приоритеты |
| 6 | [docs/agent/voice-input.md](docs/agent/voice-input.md) | Текущая фича в разработке |
| — | [docs/agent/git-workflow.md](docs/agent/git-workflow.md) | Только при ветках / коммитах / PR |

Полная карта: [docs/README.md](docs/README.md)

## Суть проекта (30 секунд)

**FinHub** — Django-приложение для личных финансов + Telegram-бот для быстрого ввода операций.

- **Стек:** Python 3.11, Django 4.2, PostgreSQL, Redis, python-telegram-bot 22, Poetry, Docker
- **Сервисы Docker:** `web` (Django), `bot` (Telegram), `db` (Postgres 16), `redis`
- **Источник правды о статусе:** `docs/agent/state.md` (не устаревший `Summary.md`)

## Активная разработка

**Фаза:** voice input MVP завершён; следующий шаг — расширение voice + analytics.

План voice: [docs/agent/voice-input.md](docs/agent/voice-input.md).

## Правила для агентов

1. **Минимальный diff** — не рефакторить несвязанный код.
2. **Следовать conventions** — [docs/agent/conventions.md](docs/agent/conventions.md).
3. **Обновлять docs** — после каждого логического блока: `state.md`, feature-plan, env/architecture по необходимости (см. [conventions.md](docs/agent/conventions.md#документация)).
4. **Не коммитить** `.env`, секреты, `.DS_Store`.
5. **Settings:** `finhub/settings/{base,development,production}.py`; окружение через `DJANGO_ENVIRONMENT`.
6. **Бот async:** blocking I/O только через `asyncio.to_thread` или ORM async (`aget`, `acreate`).
7. **Тесты:** SQLite in-memory при `manage.py test`.

## Ключевые команды

```bash
poetry install && poetry shell
python manage.py migrate
python manage.py runserver          # web
python manage.py run_bot            # bot (отдельный процесс)
docker compose up -d                # полный стек
python manage.py test
```

## Человекочитаемая документация

[docs/human/README.md](docs/human/README.md) — обзор, локальный запуск, деплой на VPS.
