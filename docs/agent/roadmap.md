# FinHub — roadmap

## Фаза 0 — Core (done)

MVP API, categories, transactions, budgets, modular settings, Docker.

## Фаза 1 — Telegram bot (done)

Text input, budgets, reports, Excel, goals MVP, default categories, prod resilience.

## Фаза 2 — Voice input (done MVP)

Голосом заносить расходы/доходы: Whisper + LLM + CommandExecutor. Feature flag `VOICE_ENABLED`.

Details: [voice-input.md](voice-input.md)

## Фаза 3 — Voice expansion

- State-aware voice (edit transaction, budget amount, goals)
- Voice: budgets, goals (intents SET_BUDGET, MANAGE_GOAL)
- Whisper prompt tuning per user categories

## Фаза 4 — Analytics & advisor

- Rich analytics (cashflow, trends)
- ASK_ADVISOR intent: LLM + ReportService recommendations
- Optional: push notifications on budget exceed

## Фаза 5 — Platform

- Frontend dashboard (Next.js — planned, not in repo)
- Debts module, trading module (vision in old TECHNICAL_ARCHITECTURE)
- Mobile-friendly web

## Приоритеты (Q3 2026)

1. Voice expansion (Phase 3): budgets/goals voice, prompt tuning
2. Refactor large handlers
3. Goal module polish + budget recommendations
4. Frontend — after voice stable

## Out of scope (пока)

- Multi-currency
- Bank sync / Open Banking
- Mobile native apps
