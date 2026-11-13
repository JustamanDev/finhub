"""LLM answer for ASK_ADVISOR: JSON по снимку, без выдуманных сумм."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from django.contrib.auth.models import User

from telegram_bot.services.advisor_snapshot_service import AdvisorSnapshotService
from telegram_bot.voice.config import (
    advisor_llm_model,
    advisor_reasoning_effort,
    openai_api_key,
    voice_llm_model,
)
from telegram_bot.voice.metrics import log_voice_event, timed_ms
from telegram_bot.voice.openai_client import format_openai_error, get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / 'prompts' / 'advisor_analyst.txt'
MAX_RETRIES = 3
MAX_OUTPUT_TOKENS = 900
ADVICE_OUTPUT_TOKENS = 2500
FACT_PROFILE = 'fact'
ADVICE_PROFILE = 'advice'
MAX_ACTION_CHARS = 180
ALLOWED_KINDS = frozenset({'fact', 'advice', 'clarify', 'decline'})
ALLOWED_TABLES = frozenset({
    'movement',
    'categories',
    'budgets',
    'goals',
    'goal_focus',
    'trend',
    'category',
    'debts',
    'recurring',
})


@dataclass
class AdvisorAnswer:
    answer_kind: str
    title: str
    lead: str
    body: str = ''
    actions: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    clarify: str | None = None


@dataclass
class AdvisorResult:
    answer: AdvisorAnswer
    snapshot: dict[str, Any]


def _format_empty_answer(snapshot: dict[str, Any]) -> AdvisorAnswer:
    period = (snapshot.get('period') or {}).get('name') or 'этот месяц'
    return AdvisorAnswer(
        answer_kind='fact',
        title=str(period),
        lead=(
            f'За {period} пока мало данных для совета. '
            'Добавьте операции или бюджеты — и спросите снова.'
        ),
    )


def _fallback_answer() -> AdvisorAnswer:
    return AdvisorAnswer(
        answer_kind='fact',
        title='Финансист',
        lead='Не удалось сформулировать ответ. Попробуйте спросить иначе.',
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
    if snapshot.get('debts') or snapshot.get('recurring'):
        return True
    health = snapshot.get('budget_health') or {}
    if health.get('budget_count') or health.get('overspent') or health.get('at_risk'):
        return True
    cashflow = snapshot.get('cashflow') or {}
    if any(
        float(cashflow.get(key) or 0) != 0
        for key in ('income', 'expenses', 'balance', 'free_funds')
    ):
        return True
    series = snapshot.get('monthly_series') or []
    for row in series:
        if any(float(row.get(key) or 0) != 0 for key in ('income', 'expenses', 'balance')):
            return True
    cat_series = snapshot.get('category_series') or []
    for row in cat_series:
        if float(row.get('amount') or 0) != 0:
            return True
    focus = snapshot.get('category_focus') or {}
    if focus.get('status') in ('matched', 'ambiguous', 'unknown') and focus.get('hint'):
        return True
    return False


def _clip(text: str, limit: int) -> str:
    clean = ' '.join((text or '').split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + '…'


def parse_advisor_payload(raw: str) -> AdvisorAnswer:
    """Разбирает JSON модели. ValueError — повод повторить запрос, не показывать сырьё."""
    text = (raw or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError('Ответ модели не объект.')
    kind = str(data.get('answer_kind') or '').strip()
    if kind not in ALLOWED_KINDS:
        raise ValueError('Неизвестный answer_kind.')
    lead = _clip(str(data.get('lead') or ''), 700)
    clarify = data.get('clarify')
    clarify_text = _clip(str(clarify), 300) if clarify else ''
    if kind == 'clarify':
        lead = clarify_text or lead
    if not lead:
        raise ValueError('Пустой вывод.')
    actions = []
    for item in data.get('actions') or []:
        step = _clip(str(item), MAX_ACTION_CHARS)
        if step:
            actions.append(step)
    tables = []
    for item in data.get('tables') or []:
        name = str(item).strip()
        if name in ALLOWED_TABLES and name not in tables:
            tables.append(name)
    if kind == 'fact':
        actions = []
        tables = tables[:1]
    elif kind == 'clarify':
        actions = []
        tables = []
    elif kind == 'decline':
        actions = actions[:2]
        tables = tables[:1]
    else:
        actions = actions[:2]
        tables = tables[:3]
    return AdvisorAnswer(
        answer_kind=kind,
        title=_clip(str(data.get('title') or 'Финансист'), 80) or 'Финансист',
        lead=lead,
        body=_clip(str(data.get('body') or ''), 500),
        actions=actions,
        tables=tables,
        clarify=clarify_text or None,
    )


def _build_system_prompt(snapshot: dict[str, Any]) -> str:
    template = PROMPT_PATH.read_text(encoding='utf-8')
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, indent=2)
    return template.replace('{{snapshot}}', snapshot_json)


def _json_mode_rejected(exc: Exception) -> bool:
    message = str(exc).lower()
    return 'response_format' in message or 'json_object' in message


def resolve_advisor_call(profile: str) -> tuple[str, str]:
    """Короткий вопрос — быстрая модель. Кнопка «Финансист» — модель с рассуждением."""
    if profile == ADVICE_PROFILE:
        return advisor_llm_model(), advisor_reasoning_effort()
    return voice_llm_model(), 'none'


def completion_kwargs(
    *,
    model: str,
    effort: str,
    use_json: bool,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {'model': model}
    if effort and effort != 'none':
        kwargs['reasoning_effort'] = effort
        kwargs['max_completion_tokens'] = ADVICE_OUTPUT_TOKENS
    else:
        kwargs['temperature'] = 0.2
        kwargs['max_tokens'] = MAX_OUTPUT_TOKENS
    if use_json:
        kwargs['response_format'] = {'type': 'json_object'}
    return kwargs


def answer_from_snapshot(
    question: str,
    snapshot: dict[str, Any],
    *,
    profile: str = FACT_PROFILE,
) -> AdvisorAnswer:
    """Sync LLM call. Raises ValueError on config/API failure."""
    if not _snapshot_has_signal(snapshot):
        return _format_empty_answer(snapshot)

    if not openai_api_key():
        raise ValueError('OPENAI_API_KEY не задан.')

    system_prompt = _build_system_prompt(snapshot)
    client = get_openai_client()
    model, effort = resolve_advisor_call(profile)
    last_error: Exception | None = None
    use_json_mode = True
    invalid_json_attempts = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            kwargs = completion_kwargs(
                model=model,
                effort=effort,
                use_json=use_json_mode,
            )
            kwargs['messages'] = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': question.strip()},
            ]
            with timed_ms() as timing:
                response = client.chat.completions.create(**kwargs)
            text = (response.choices[0].message.content or '').strip()
            log_voice_event(
                'advisor_answer',
                llm_ms=timing.get('ms'),
                chars=len(text),
                model=model,
                profile=profile,
                period=(snapshot.get('period') or {}).get('name'),
            )
            if not text:
                invalid_json_attempts += 1
                if invalid_json_attempts > 1:
                    return _fallback_answer()
                continue
            try:
                return parse_advisor_payload(text)
            except (ValueError, json.JSONDecodeError) as exc:
                invalid_json_attempts += 1
                logger.warning('Advisor JSON rejected: %s', exc)
                if invalid_json_attempts > 1:
                    return _fallback_answer()
                continue
        except Exception as exc:
            message = str(exc).lower()
            if use_json_mode and _json_mode_rejected(exc):
                use_json_mode = False
                logger.warning('Advisor JSON mode unsupported, retrying plain')
                continue
            if effort != 'none' and 'reasoning' in message:
                effort = 'none'
                logger.warning('Advisor reasoning unsupported, retrying without it')
                continue
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


async def answer_advisor_query(
    user: User,
    question: str,
    *,
    profile: str = FACT_PROFILE,
) -> AdvisorResult:
    from asgiref.sync import sync_to_async
    from telegram_bot.voice.period_parser import parse_advisor_period

    period = parse_advisor_period(question)
    snapshot = await AdvisorSnapshotService(user).build(
        period=period,
        question=question,
    )
    answer = await sync_to_async(answer_from_snapshot)(
        question,
        snapshot,
        profile=profile,
    )
    return AdvisorResult(answer=answer, snapshot=snapshot)
