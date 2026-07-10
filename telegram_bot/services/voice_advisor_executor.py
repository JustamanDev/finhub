"""LLM answer for ASK_ADVISOR grounded in AdvisorSnapshotService facts."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from django.contrib.auth.models import User

from telegram_bot.services.advisor_snapshot_service import AdvisorSnapshotService
from telegram_bot.voice.config import openai_api_key, voice_llm_model
from telegram_bot.voice.metrics import log_voice_event, timed_ms
from telegram_bot.voice.openai_client import format_openai_error, get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / 'prompts' / 'advisor_answer.txt'
MAX_RETRIES = 3
MAX_ANSWER_CHARS = 1200


def _format_empty_snapshot_reply(snapshot: dict[str, Any]) -> str:
    period = (snapshot.get('period') or {}).get('name') or 'этот месяц'
    return (
        f'За {period} пока мало данных для совета.\n'
        'Добавьте операции или бюджеты — и спросите снова '
        '(например: «сколько потратил в этом месяце?»).'
    )


def _snapshot_has_signal(snapshot: dict[str, Any]) -> bool:
    totals = snapshot.get('month_totals') or {}
    today = snapshot.get('today') or {}
    previous = snapshot.get('previous_period') or {}
    if any(
        float(totals.get(key) or 0) != 0
        for key in ('income', 'expenses', 'balance', 'free_funds')
    ):
        return True
    if any(float(today.get(key) or 0) != 0 for key in ('income', 'expenses')):
        return True
    if any(
        float(previous.get(key) or 0) != 0
        for key in ('income', 'expenses', 'balance', 'free_funds')
    ):
        return True
    if snapshot.get('budgets') or snapshot.get('goals'):
        return True
    if snapshot.get('top_expense_categories') or snapshot.get('top_income_categories'):
        return True
    if snapshot.get('suggestions'):
        return True
    series = snapshot.get('monthly_series') or []
    for row in series:
        if any(float(row.get(key) or 0) != 0 for key in ('income', 'expenses', 'balance')):
            return True
    return False


def _build_system_prompt(snapshot: dict[str, Any]) -> str:
    template = PROMPT_PATH.read_text(encoding='utf-8')
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)
    return template.replace('{{snapshot}}', snapshot_json)


def answer_from_snapshot(question: str, snapshot: dict[str, Any]) -> str:
    """Sync LLM call. Raises ValueError on config/API failure."""
    if not _snapshot_has_signal(snapshot):
        return _format_empty_snapshot_reply(snapshot)

    if not openai_api_key():
        raise ValueError('OPENAI_API_KEY не задан.')

    system_prompt = _build_system_prompt(snapshot)
    client = get_openai_client()
    model = voice_llm_model()
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with timed_ms() as timing:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': question.strip()},
                    ],
                    temperature=0.2,
                    max_tokens=500,
                )
            text = (response.choices[0].message.content or '').strip()
            log_voice_event(
                'advisor_answer',
                llm_ms=timing.get('ms'),
                chars=len(text),
                period=(snapshot.get('period') or {}).get('name'),
            )
            if not text:
                return (
                    'Не удалось сформулировать ответ. '
                    'Попробуйте спросить иначе.'
                )
            if len(text) > MAX_ANSWER_CHARS:
                text = text[: MAX_ANSWER_CHARS - 1].rstrip() + '…'
            return text
        except Exception as exc:
            last_error = exc
            logger.warning(
                'Advisor LLM attempt %s/%s failed: %s',
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(attempt)

    raise ValueError(
        f'Не удалось получить ответ консультанта: '
        f'{format_openai_error(last_error)}',
    )


async def answer_advisor_query(user: User, question: str) -> str:
    from asgiref.sync import sync_to_async
    from telegram_bot.voice.period_parser import parse_advisor_period

    period = parse_advisor_period(question)
    snapshot = await AdvisorSnapshotService(user).build(
        period=period,
        question=question,
    )
    return await sync_to_async(answer_from_snapshot)(question, snapshot)
