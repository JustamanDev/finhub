# FinHub — conventions (agent reference)

## Общие принципы

- Минимальный scope diff; match existing style
- Async bot: `await Model.objects.aget()`, `acreate()`; sync ORM → `sync_to_async`
- Blocking calls (OpenAI, file I/O) → `asyncio.to_thread`
- User-facing bot texts — русский; code/docstrings — как в surrounding file
- Коммиты только по запросу пользователя
- Git: ветки только от `main`, merge через PR — [git-workflow.md](git-workflow.md)

## Где добавлять код

| Задача | Куда |
|--------|------|
| Новая bot-команда | `handlers/command_handler.py` + register in `run_bot.py` |
| Текстовый ввод / state | `handlers/text_handler.py` |
| Голосовой ввод | `handlers/voice_handler.py` + `voice/*` |
| Inline callback | `handlers/callback_handler.py` + keyboard in `keyboards/` |
| Бизнес-логика | `telegram_bot/services/` или app-level `services/` |
| Парсинг текста / голоса | `utils/text_parser.py`, `voice/interpreter.py` |
| Модели бота | `telegram_bot/models.py` + migration |
| API endpoint | `{app}/views.py`, `serializers.py`, register in `api/urls.py` |
| Env vars | `finhub/settings/base.py` or prod/dev + `docs/human/environment.md` |
| Промпты LLM | `telegram_bot/prompts/*.txt` |

## Naming

- Handlers: `*Handler` classes, methods `handle_*`
- Services: `*Service` classes, async where called from bot
- Callback data: prefix pattern `action_param` e.g. `edit_amount_123`
- Django users from Telegram: username `tg_{telegram_id}`

## Telegram patterns

- Retry transient errors: `telegram_bot/utils/telegram_resilience.py`
- Admin errors: `telegram_bot/utils/admin_alerts.py`
- Navigation: `keyboards/navigation.py` → persistent «Главное меню» / «Назад»
- After transaction: `ActionKeyboard.get_transaction_actions_keyboard(id)`

## Тесты

- Location: `{app}/tests.py` or `telegram_bot/tests.py`
- Run: `python manage.py test`
- DB: SQLite in-memory (auto in `base.py` when `'test' in sys.argv`)

## Документация

После **каждого завершённого логического блока** (коммит/PR-шаг) обновляй релевантные docs:

- Статус / changelog → `docs/agent/state.md`
- Фича in progress → чеклист в `docs/agent/<feature>.md` (напр. `voice-input.md`)
- Roadmap phase done → `docs/agent/roadmap.md`
- Новая env var → `docs/human/environment.md`
- Архитектура / новый модуль → `docs/agent/architecture.md` (кратко)
- Публичные возможности → `docs/human/overview.md`, `README.md` (если user-facing)

Не дублировать: один факт — один canonical файл, остальные — ссылки.

## Не делать

- Не добавлять Celery без явного запроса (в TECHNICAL_ARCHITECTURE vision, не deployed)
- Не подключать AudioToText как runtime dependency — переносить модули
- Не хардкодить bot texts — использовать `BotText` slug где уместно
- Не коммитить secrets / `.env`
