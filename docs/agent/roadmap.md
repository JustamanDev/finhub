# FinHub — roadmap

## Фаза 0 — Core (done)

MVP API, categories, transactions, budgets, modular settings, Docker.

## Фаза 1 — Telegram bot (done)

Text input, budgets, reports, Excel за месяц и за год, goals MVP, default categories, prod resilience.

## Фаза 2 — Voice input (done MVP)

Голосом заносить расходы/доходы: Whisper + LLM + CommandExecutor. Feature flag `VOICE_ENABLED`.

Details: [voice-input.md](voice-input.md)

## Фаза 3 — Voice expansion (done)

Голос умеет лимиты (`SET_BUDGET`) и цели (`MANAGE_GOAL`: создать, пополнить, снять).

## Фаза 4 — Analytics & advisor (done)

Консультант отвечает по снимку: периоды, тренды, категории, срок цели. Бот один раз пишет, когда трата переходит лимит.

## Фаза 5 — Дальше

Не начато. Когда вернёмся к коду, первыми идут повторяющиеся операции и долги. Остальной старый план и идеи на обсуждение: [ideas.md](ideas.md).

## Приоритеты

Живой продукт — учёт, отчёты, цели и конверты, голос, консультант. Новая работа не начата.

Следующие два, когда вернёмся к разработке:

1. Повторяющиеся операции
2. Долги

Крупные хендлеры бота по-прежнему стоит резать, когда их снова трогают.

## Out of scope (пока)

- Bank sync / Open Banking
- Mobile native apps
- Celery, пока его явно не попросят
