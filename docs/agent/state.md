# FinHub — текущее состояние

> **Source of truth.** Обновляй при завершении задач. Формат: дата + суть в 1–3 строки.

**Обновлено:** 2026-07-09  
**Стадия:** Production-ready core + активная разработка voice input  
**Прогресс core:** ~85%

## Что работает

- [x] CRUD категорий, транзакций, бюджетов (API + admin)
- [x] Telegram-бот: текстовый ввод, категории, бюджеты, отчёты, Excel export
- [x] Цели (конверты): модели + bot flow (создание, deposit/withdraw)
- [x] Модульные settings dev/prod, Docker stack, Redis rate limit (prod)
- [x] Дефолтные категории для новых пользователей, тексты бота в admin (`BotText`)
- [x] Идемпотентный bootstrap Telegram-пользователя, resilient Telegram timeouts/proxy

## В работе

- [ ] ASK_ADVISOR extensions (category trends across months, goal ETA) — backlog

## Недавно завершено

- [x] **Fix ASK_ADVISOR year lookback** — «за год» / минус / справлялся → 12 мес + deficit stats
- [x] **ASK_ADVISOR richer** — cashflow + budget_health (overspent / at_risk / pace) ([PR #43](https://github.com/JustamanDev/finhub/pull/43))
- [x] **ASK_ADVISOR trends** — monthly_series 3–6 мес + trend summary ([PR #42](https://github.com/JustamanDev/finhub/pull/42))
- [x] **ASK_ADVISOR v2 periods** — прошлый месяц / named month / MoM в snapshot ([PR #41](https://github.com/JustamanDev/finhub/pull/41))
- [x] **Fix voice budget parse** — category-then-amount + spoken dialog amount ([PR #40](https://github.com/JustamanDev/finhub/pull/40))
- [x] **ASK_ADVISOR MVP** — grounded LLM по snapshot ([PR #38](https://github.com/JustamanDev/finhub/pull/38))
- [x] **Voice Phase 5** — hardening: spoken numbers, metrics, Whisper context ([PR #36](https://github.com/JustamanDev/finhub/pull/36))
- [x] **Voice Phase 4** — MANAGE_GOAL deposit/withdraw/create ([PR #34](https://github.com/JustamanDev/finhub/pull/34))
- [x] **Voice Phase 3** — SET_BUDGET create/update monthly limits ([PR #33](https://github.com/JustamanDev/finhub/pull/33))
- [x] **Voice Phase 2** — VoiceDialogManager (slot fill, timeout, category handoff)
- [x] **Voice Phase 1** — CategoryResolver + disambiguation UI
- [x] **Voice Phase 0** — bugfix baseline (description, wizards, income phrases)
- [x] **Fix: Message is not modified** — `safe_edit_message_text` / `send_or_edit_message`
- [x] **Voice input MVP** — голосовой ввод расходов/доходов (`VOICE_ENABLED=True`)

## Backlog

- [ ] Frontend (Next.js — в vision, не в repo)
- [ ] Модуль долгов, трейдинг
- [ ] Финансовый консультант (LLM + аналитика) — заложено в voice architecture
- [ ] HTTPS/nginx на prod (опционально, вне repo)

## Активные риски / tech debt

- `callback_handler.py`, `text_handler.py`, `settings_handler.py` — большие файлы

## Changelog (компактно)

### 2026-07-10
- Fix ASK_ADVISOR year lookback: «за год» → 12 months + deficit/surplus stats
- ASK_ADVISOR richer: cashflow + budget_health (overspent / at_risk / pace) in snapshot (PR #43)
- ASK_ADVISOR trends: monthly_series + trend summary for 3–6 months (PR #42)

### 2026-07-09
- ASK_ADVISOR v2 periods: period parser + MoM comparison in snapshot (PR #41)
- Fix voice budget parse: category-then-amount + spoken dialog amount (PR #40)
- ASK_ADVISOR MVP merged: snapshot + grounded LLM financial answers (PR #38)
- Voice Phase 5 merged: spoken numbers, voice metrics, Whisper category prompt (PR #36)
- Voice Phase 4 merged: MANAGE_GOAL deposit/withdraw/create via voice (PR #34)
- Voice Phase 3 merged: SET_BUDGET create/update monthly budget via voice (PR #33)
- Fix: повторный клик по inline-кнопкам не падает с `Message is not modified` (`safe_edit_message_text`, `send_or_edit_message`)

### 2026-06-30 (voice input)
- Feature: голосовой ввод транзакций (Whisper + LLM interpreter + CommandExecutor)
- Docs: git-workflow, doc-update rule in conventions

### 2026-06-30 (docs)
- Docs: структура `docs/agent/` + `docs/human/`, AGENTS.md, план voice input зафиксирован
- Docs: git workflow (ветки от main, atomic commits, PR-only merge)

### 2026-02-10
- Fix: idempotent Telegram user bootstrap (IntegrityError)
- Admin alerts: меньше шума (fingerprint traceback)

### 2026-01-14
- Default categories on first login; BotText in admin; DefaultCategoryTemplate

### 2026-01-10
- Excel report export; goal module MVP; transaction amount edit

### 2025-11-18
- Full Telegram bot MVP; Docker compose stack

### 2024-12-28
- MVP API, budgets, modular settings (dev/prod)
