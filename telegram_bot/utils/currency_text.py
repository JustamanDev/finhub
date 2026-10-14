"""Как пользователь пишет валюту в тексте и голосе."""

import re

from transactions.currencies import RUB, VND

ENTRY_CURRENCY_KEY = 'entry_currency'

# Полные слова валюты. Одиночные «р»/«д» сюда не входят:
# иначе «ресторан» теряет первую букву.
CURRENCY_WORD = (
    r'(?:руб(?:лей|ля|ль)?|rub|rur|vnd|dong|донг(?:ов|а|и)?|₽|₫|đ)'
)

_LEADING_AMOUNT = re.compile(
    rf'^(?P<amount>[+-]?\d+(?:[.,]\d+)?)'
    rf'(?:'
    rf'(?P<glued>[рРдД₽₫đ])'
    rf'|(?:\s+(?P<word>{CURRENCY_WORD}|[рРдД])\b)'
    rf')?'
    rf'(?:\s+(?P<rest>.+))?$',
    re.IGNORECASE,
)

_DONG_MENTION = re.compile(
    r'(?i)(?:\b(?:vnd|dong|донг(?:ов|а|и)?)\b|[₫đ]|(?<=\d)д\b|(?<=\d)д(?=\s|$))',
)
_RUB_MENTION = re.compile(
    r'(?i)(?:\b(?:rub|rur|руб(?:лей|ля|ль)?)\b|₽|(?<=\d)р\b|(?<=\d)р(?=\s|$))',
)


def normalize_currency_token(token: str | None) -> str | None:
    """Слово или короткая пометка → RUB / VND. Неизвестное → None."""
    if not token:
        return None
    cleaned = token.strip().lower().rstrip('.')
    if cleaned.startswith('руб') or cleaned in {'р', '₽', 'rub', 'rur'}:
        return RUB
    if (
        cleaned.startswith('донг')
        or cleaned in {'д', '₫', 'đ', 'vnd', 'dong'}
    ):
        return VND
    return None


def detect_currency_mention(text: str | None) -> str | None:
    """
    Валюта, явно названная во фразе.

    Если названы обе или ни одной — None, пусть решает валюта по умолчанию.
    """
    if not text:
        return None
    has_dong = _DONG_MENTION.search(text) is not None
    has_rub = _RUB_MENTION.search(text) is not None
    if has_dong and not has_rub:
        return VND
    if has_rub and not has_dong:
        return RUB
    return None


def parse_leading_amount(text: str) -> dict | None:
    """
    «500 кофе», «50000д кофе», «1500 руб такси», «50000».

    Возвращает amount (строка как в тексте), currency (RUB/VND/None)
    и rest (хвост без валюты) либо None, если строка не про сумму.
    """
    match = _LEADING_AMOUNT.match((text or '').strip())
    if not match:
        return None
    token = match.group('glued') or match.group('word')
    rest = (match.group('rest') or '').strip()
    return {
        'amount': match.group('amount'),
        'currency': normalize_currency_token(token),
        'rest': rest,
    }


def stash_entry_currency(user_state, currency: str | None) -> None:
    """Запоминает валюту, пока пользователь выбирает категорию."""
    data = dict(user_state.context_data or {})
    data[ENTRY_CURRENCY_KEY] = currency or RUB
    user_state.context_data = data


def read_entry_currency(user_state) -> str:
    data = user_state.context_data or {}
    return data.get(ENTRY_CURRENCY_KEY) or RUB


def currency_suffix(currency: str | None) -> str:
    """Короткая пометка, чтобы не потерять валюту при сжатии фразы."""
    if currency == VND:
        return 'д'
    if currency == RUB:
        return 'р'
    return ''
