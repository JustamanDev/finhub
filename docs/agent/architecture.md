# FinHub — архитектура (agent reference)

## Общая схема

```mermaid
flowchart TB
    subgraph clients [Clients]
        TG[Telegram]
        API[REST API / future web]
    end
    subgraph docker [Docker Compose]
        Bot[bot: run_bot]
        Web[web: Django]
        DB[(PostgreSQL)]
        Redis[(Redis)]
    end
    TG --> Bot
    API --> Web
    Bot --> DB
    Web --> DB
    Bot --> Redis
    Web --> Redis
```

## Telegram: ввод транзакции (текст)

```mermaid
sequenceDiagram
    participant U as User
    participant RB as run_bot
    participant TH as TextHandler
    participant TP as TextCommandParser
    participant TS as TransactionService
    participant DB as PostgreSQL

    U->>RB: "500 кофe"
    RB->>TH: handle_text_message
    TH->>TH: check UserState / context flags
    TH->>TP: parse(text)
    TP-->>TH: amount_category
    TH->>TS: create_transaction
    TS->>DB: Transaction.acreate
    TH->>U: confirm + ActionKeyboard
```

**State machine:** `UserState` + `context.user_data` — editing transaction, goal flow, budget input перехватывают текст до парсера.

## Telegram: handler registration

Файл: `telegram_bot/management/commands/run_bot.py`

| Filter | Handler |
|--------|---------|
| `/start`, `/help`, `/stats` | `CommandHandler` |
| `TEXT & ~COMMAND` | `TextHandler.handle_text_message` |
| all callbacks | `CallbackHandler.handle_callback_query` |
| `VOICE \| AUDIO` | `VoiceHandler.handle_voice_message` |

## Слои telegram_bot

```
telegram_bot/
  handlers/       # UI / routing (thin)
  services/       # business logic, DB
  keyboards/      # InlineKeyboard builders
  utils/          # text_parser, admin_alerts, telegram_resilience
  models.py       # TelegramUser, UserState, BotText
  voice/          # Whisper, interpreter, router
```

**Правило:** handlers вызывают services; не дублировать ORM-логику в handlers.

## Planned: voice pipeline

```mermaid
flowchart LR
    V[Voice] --> W[Whisper API]
    W --> T[Transcript]
    T --> R{Regex OK?}
    R -->|yes| CE[CommandExecutor]
    R -->|no| L[LLM JSON extract]
    L --> CE
    CE --> TS[TransactionService]
```

Детали: [voice-input.md](voice-input.md)

## Валюта: донги → рубли

Отчёты, бюджеты и цели считаются в **рублях**. `Transaction.amount` — всегда рублёвый итог со знаком.

Пользователь вводит сумму в рублях или донгах. Для донгов курс берётся из ежедневного XML ЦБ (`https://www.cbr.ru/scripts/XML_daily.asp`, без ключа), не чаще одного раза в сутки по Москве, и **замораживается на операции**. Исходная сумма лежит в `original_amount`. Если ЦБ недоступен, используется последний сохранённый курс.

Ввод: `50000д кофе`, `1500 руб такси`. Без пометки бот спрашивает рубли или донги и только потом пишет операцию (донги конвертируются). Кнопка «Отмена» на карточке операции — `delete_transaction_{id}`. Лимит или цель, сказанные явно в донгах, перед записью тоже переводятся в рубли.

Подробности: [currency.md](currency.md).

## Django models (связи)

```
User 1--* Category
User 1--* Transaction
User 1--* Budget
User 1--* Goal
Category 1--* Transaction
Category 1--* Budget
Goal 1--* GoalLedgerEntry
TelegramUser 1--1 User
TelegramUser 1--1 UserState
ExchangeRate — дневной курс VND→RUB, не привязан к пользователю
```

## API

- Versioning: `core/middleware.py` → header `X-API-Version`
- Auth: Token (djoser)
- Rate limit: `django-ratelimit` на views (prod)

## Production vs development

| | development | production |
|---|-------------|------------|
| Cache | DummyCache | Redis |
| Rate limit | off | on |
| DEBUG | True | False |
| DB SSL | — | `DB_SSLMODE` env |

## Файлы-«god objects» (осторожно при правках)

| Файл | ~строк | Примечание |
|------|--------|------------|
| `handlers/callback_handler.py` | 1600+ | inline callback routing |
| `handlers/text_handler.py` | 1250+ | text + state branches |
| `handlers/settings_handler.py` | 1170+ | categories/settings |

При voice work: выносить shared logic в `services/command_executor.py`.
