"""Как пользователь пишет валюту в тексте и голосе."""

import re

from transactions.currencies import (
    BY_CODE,
    CATALOG,
    RUB,
    VND,
    is_known,
    normalize_currency_token,
)

ENTRY_CURRENCY_KEY = 'entry_currency'

# Полные слова валюты. Одиночные «р»/«д» сюда не входят:
# иначе «ресторан» теряет первую букву.
_WORD_ALIASES = sorted(
    (
        alias
        for spec in CATALOG
        for alias in spec.aliases
        if len(alias) > 1
    ),
    key=len,
    reverse=True,
)
CURRENCY_WORD = '(?:' + '|'.join(re.escape(alias) for alias in _WORD_ALIASES) + ')'
_CODES = '|'.join(
    sorted((spec.code for spec in CATALOG if spec.code != RUB), key=len, reverse=True)
)
_SYMBOLS = ''.join(
    dict.fromkeys(
        alias
        for spec in CATALOG
        for alias in spec.aliases
        if len(alias) == 1 and not alias.isalpha()
    )
)

_LEADING_AMOUNT = re.compile(
    rf'^(?P<amount>[+-]?\d+(?:[.,]\d+)?)'
    rf'(?:'
    rf'(?P<glued>[{re.escape(_SYMBOLS)}рд])'
    rf'|(?P<code>{_CODES})'
    rf'|(?:\s+(?P<word>{CURRENCY_WORD}|[рд])\b)'
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


def explicit_entry_currency(
    parsed_command: dict | None,
    transcript: str | None = None,
    allowed: list[str] | tuple[str, ...] | None = None,
) -> str | None:
    """
    Валюта, которую пользователь назвал сам.

    Нет пометки — None: бот должен спросить, а не подставлять валюту молча.
    Если передан allowed, код вне этого списка тоже считается непомеченным.
    """
    parsed_command = parsed_command or {}
    explicit = parsed_command.get('currency')
    if not is_known(explicit):
        explicit = detect_currency_mention(
            transcript or parsed_command.get('raw_text') or '',
        )
    if not is_known(explicit):
        return None
    if allowed is not None and explicit not in allowed:
        return None
    return explicit


def detect_currency_mention(text: str | None) -> str | None:
    """
    Валюта, явно названная во фразе.

    Если названы обе или ни одной — None.
    """
    if not text:
        return None
    found: set[str] = set()
    if _DONG_MENTION.search(text) is not None:
        found.add(VND)
    if _RUB_MENTION.search(text) is not None:
        found.add(RUB)
    for spec in CATALOG:
        if spec.code in {RUB, VND}:
            continue
        mention = _mention_pattern(spec)
        if mention.search(text):
            found.add(spec.code)
    if len(found) == 1:
        return next(iter(found))
    return None


def _mention_pattern(spec) -> re.Pattern[str]:
    cached = _MENTION_PATTERNS.get(spec.code)
    if cached is not None:
        return cached
    parts = []
    for alias in spec.aliases:
        if len(alias) == 1 and alias.isalpha():
            continue
        if len(alias) == 1:
            parts.append(re.escape(alias))
        else:
            parts.append(rf'\b{re.escape(alias)}\b')
    parts.sort(key=len, reverse=True)
    compiled = re.compile('|'.join(parts) or r'(?!)', re.IGNORECASE)
    _MENTION_PATTERNS[spec.code] = compiled
    return compiled


_MENTION_PATTERNS: dict[str, re.Pattern[str]] = {}


def parse_leading_amount(text: str) -> dict | None:
    """
    «500 кофе», «50000д кофе», «1500 руб такси», «50000».

    Возвращает amount (строка как в тексте), currency (код каталога или None)
    и rest (хвост без валюты) либо None, если строка не про сумму.
    """
    match = _LEADING_AMOUNT.match((text or '').strip())
    if not match:
        return None
    token = match.group('glued') or match.group('code') or match.group('word')
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
    spec = BY_CODE.get(currency or '')
    if spec is None:
        return ''
    return spec.code.lower()
