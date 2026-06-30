# FinHub — документация

## Для AI-агентов

| Файл | Содержание |
|------|------------|
| [agent/state.md](agent/state.md) | **Живой статус:** стадия, прогресс, changelog (компактно) |
| [agent/project.md](agent/project.md) | Стек, Django apps, модели, API, Docker |
| [agent/architecture.md](agent/architecture.md) | Telegram bot flow, сервисы, диаграммы |
| [agent/conventions.md](agent/conventions.md) | Паттерны кода, naming, где что лежит |
| [agent/roadmap.md](agent/roadmap.md) | Roadmap по фазам |
| [agent/voice-input.md](agent/voice-input.md) | План голосового ввода (текущая работа) |
| [agent/git-workflow.md](agent/git-workflow.md) | Ветки, коммиты, PR (по необходимости) |

Точка входа для Cursor: [../AGENTS.md](../AGENTS.md)

## Для людей

| Файл | Содержание |
|------|------------|
| [human/README.md](human/README.md) | Навигация |
| [human/overview.md](human/overview.md) | Что такое FinHub, возможности |
| [human/getting-started.md](human/getting-started.md) | Локальный запуск (Poetry / Docker) |
| [human/deploy.md](human/deploy.md) | Деплой на VPS, prod Docker |
| [human/environment.md](human/environment.md) | Переменные окружения |

## Справочники (детали, реже нужны агенту)

| Файл | Содержание |
|------|------------|
| [../MVP_API_TESTING.md](../MVP_API_TESTING.md) | Примеры API-запросов |
| [../BUDGET_API_TESTING.md](../BUDGET_API_TESTING.md) | Тесты Budget API |

## Устаревшие файлы в корне

Перенесены в `docs/`. Корневые копии содержат redirect — не дублировать правки там.

- `Summary.md` → `docs/agent/state.md`
- `TECHNICAL_ARCHITECTURE.md` → `docs/agent/architecture.md`
- `MVP_DEVELOPMENT_PLAN.md` → `docs/agent/roadmap.md`
- `PROJECT_SETUP_GUIDE.md` → `docs/human/getting-started.md`
- `ENVIRONMENT_SETUP.md` → `docs/human/environment.md`
- `PRODUCTION_DOCKER_GUIDE.md` → `docs/human/deploy.md`
