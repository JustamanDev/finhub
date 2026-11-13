"""Одноразовый режим «следующее сообщение — вопрос финансисту»."""

from __future__ import annotations

import time
from typing import Any

ADVISOR_ARMED_KEY = 'advisor_armed_until'
ADVISOR_ARM_SECONDS = 300
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


def clear_advisor_mode(context: Any) -> None:
    data = getattr(context, 'user_data', None)
    if isinstance(data, dict):
        data.pop(ADVISOR_ARMED_KEY, None)


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
    return 'active' if alive else 'expired'


def is_money_entry(text: str) -> bool:
    """Сообщение начинается с суммы — это ввод операции, не вопрос."""
    from telegram_bot.utils.currency_text import parse_leading_amount

    return parse_leading_amount(text or '') is not None
