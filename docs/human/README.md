# Документация FinHub (для людей)

FinHub — личный финансовый хаб с Telegram-ботом. Эта секция — для разработчиков и владельца проекта.

## С чего начать

1. [Обзор проекта](overview.md) — что умеет FinHub сейчас
2. [Быстрый старт](getting-started.md) — локальный запуск
3. [Переменные окружения](environment.md) — `.env`
4. [Деплой на сервер](deploy.md) — production Docker на VPS

## Текущая разработка

Голосовой ввод расходов/доходов в Telegram — см. [../agent/voice-input.md](../agent/voice-input.md).

Актуальный статус: [../agent/state.md](../agent/state.md).

## API

- Swagger: `http://localhost:8000/api/docs/`
- Примеры запросов: [MVP_API_TESTING.md](../../MVP_API_TESTING.md), [BUDGET_API_TESTING.md](../../BUDGET_API_TESTING.md)

## Git / GitHub

Ветки от `main`, merge через PR: [../agent/git-workflow.md](../agent/git-workflow.md)

## Для AI-агентов

См. [AGENTS.md](../../AGENTS.md) и каталог [../agent/](../agent/).
