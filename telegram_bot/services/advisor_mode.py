"""Одноразовый режим «следующее сообщение — вопрос финансисту»."""

from __future__ import annotations

import time
from typing import Any

ADVISOR_ARMED_KEY = 'advisor_armed_until'
ADVISOR_PENDING_KEY = 'advisor_pending_question'
ADVISOR_OPTIONS_KEY = 'advisor_clarify_options'
ADVISOR_ARM_SECONDS = 300
_PENDING_LIMIT = 2000
ADVISOR_ARM_CALLBACKS = frozenset({'ask_advisor', 'advisor_again'})

ADVISOR_PROMPT_TEXT = (
    'Пришлите вопрос голосом или текстом. '
    'Разберу его по вашим цифрам и не запишу как операцию.'
)
ADVISOR_EXPIRED_TEXT = 'Время вопроса вышло. Нажмите «Финансист» ещё раз.'
ADVISOR_ENTRY_TEXT = (
    'Это похоже на запись операции. '
    'Отправьте её обычным сообщением, без кнопки «Финансист».'
)


def arm_advisor_mode(context: Any, now: float | None = None) -> None:
    moment = time.time() if now is None else now
    context.user_data[ADVISOR_ARMED_KEY] = moment + ADVISOR_ARM_SECONDS
    context.user_data.pop(ADVISOR_PENDING_KEY, None)
    context.user_data.pop(ADVISOR_OPTIONS_KEY, None)


def hold_advisor_clarification(
    context: Any,
    question: str,
    now: float | None = None,
    *,
    options: list[str] | None = None,
) -> None:
    """Уточнение не закрывает вопрос: следующий ответ продолжает его."""
    data = getattr(context, 'user_data', None)
    if not isinstance(data, dict):
        return
    moment = time.time() if now is None else now
    data[ADVISOR_ARMED_KEY] = moment + ADVISOR_ARM_SECONDS
    data[ADVISOR_PENDING_KEY] = (question or '').strip()[:_PENDING_LIMIT]
    data[ADVISOR_OPTIONS_KEY] = list(options or [])


def advisor_option_label(context: Any, index: int) -> str | None:
    data = getattr(context, 'user_data', None)
    if not isinstance(data, dict):
        return None
    options = data.get(ADVISOR_OPTIONS_KEY) or []
    if not isinstance(options, list) or index < 0 or index >= len(options):
        return None
    label = str(options[index]).strip()
    return label or None


def callback_keeps_advisor(data: str) -> bool:
    """Нажатие не стирает незаконченное уточнение."""
    if data in ADVISOR_ARM_CALLBACKS:
        return True
    return data == 'advisor_choice_other' or data.startswith('advisor_choice:')


def drop_advisor_question(context: Any) -> None:
    data = getattr(context, 'user_data', None)
    if isinstance(data, dict):
        data.pop(ADVISOR_PENDING_KEY, None)
        data.pop(ADVISOR_OPTIONS_KEY, None)


def followup_question(context: Any, reply: str) -> str:
    """Склеивает исходный вопрос и ответ на уточнение."""
    data = getattr(context, 'user_data', None)
    text = (reply or '').strip()
    if not isinstance(data, dict):
        return text
    pending = str(data.pop(ADVISOR_PENDING_KEY, '') or '').strip()
    if not pending or pending == text:
        return text
    return f'{pending}\n\nУточнение пользователя: {text}'


def clear_advisor_mode(context: Any) -> None:
    data = getattr(context, 'user_data', None)
    if isinstance(data, dict):
        data.pop(ADVISOR_ARMED_KEY, None)
        data.pop(ADVISOR_PENDING_KEY, None)
        data.pop(ADVISOR_OPTIONS_KEY, None)


def take_advisor_mode(context: Any, now: float | None = None) -> str:
    """Снимает режим. «active», «expired» или «off»."""
    data = getattr(context, 'user_data', None)
    if not isinstance(data, dict) or ADVISOR_ARMED_KEY not in data:
        return 'off'
    until = data.pop(ADVISOR_ARMED_KEY)
    moment = time.time() if now is None else now
    try:
        alive = float(until) >= moment
    except (TypeError, ValueError):
        alive = False
    if not alive:
        data.pop(ADVISOR_PENDING_KEY, None)
        data.pop(ADVISOR_OPTIONS_KEY, None)
        return 'expired'
    return 'active'


def is_money_entry(text: str) -> bool:
    """Сообщение начинается с суммы — это ввод операции, не вопрос."""
    from telegram_bot.utils.currency_text import parse_leading_amount

    return parse_leading_amount(text or '') is not None
