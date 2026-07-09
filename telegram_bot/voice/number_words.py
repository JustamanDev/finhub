"""Convert Russian spoken number phrases to digits for voice fast path.

Examples:
  «триста» → «300»
  «пятьсот продукты» → «500 продукты»
  «50 тысяч» → «50000»
  «полтора миллиона» → «1500000»
  «две тысячи пятьсот» → «2500»
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

ONES = {
    'ноль': 0,
    'один': 1,
    'одна': 1,
    'одно': 1,
    'два': 2,
    'две': 2,
    'три': 3,
    'четыре': 4,
    'пять': 5,
    'шесть': 6,
    'семь': 7,
    'восемь': 8,
    'девять': 9,
}

TEENS = {
    'десять': 10,
    'одиннадцать': 11,
    'двенадцать': 12,
    'тринадцать': 13,
    'четырнадцать': 14,
    'пятнадцать': 15,
    'шестнадцать': 16,
    'семнадцать': 17,
    'восемнадцать': 18,
    'девятнадцать': 19,
}

TENS = {
    'двадцать': 20,
    'тридцать': 30,
    'сорок': 40,
    'пятьдесят': 50,
    'шестьдесят': 60,
    'семьдесят': 70,
    'восемьдесят': 80,
    'девяносто': 90,
}

HUNDREDS = {
    'сто': 100,
    'двести': 200,
    'триста': 300,
    'четыреста': 400,
    'пятьсот': 500,
    'шестьсот': 600,
    'семьсот': 700,
    'восемьсот': 800,
    'девятьсот': 900,
}

SCALES = {
    'тысяча': 1_000,
    'тысячи': 1_000,
    'тысяч': 1_000,
    'миллион': 1_000_000,
    'миллиона': 1_000_000,
    'миллионов': 1_000_000,
    'млн': 1_000_000,
}

FRACTIONS = {
    'полтора': Decimal('1.5'),
    'полторы': Decimal('1.5'),
}

_NUMBER_TOKEN = (
    r'(?:\d+(?:[.,]\d+)?)|'
    r'(?:полтора|полторы)|'
    r'(?:ноль|один|одна|одно|два|две|три|четыре|пять|шесть|семь|восемь|девять)|'
    r'(?:десять|одиннадцать|двенадцать|тринадцать|четырнадцать|пятнадцать|'
    r'шестнадцать|семнадцать|восемнадцать|девятнадцать)|'
    r'(?:двадцать|тридцать|сорок|пятьдесят|шестьдесят|семьдесят|'
    r'восемьдесят|девяносто)|'
    r'(?:сто|двести|триста|четыреста|пятьсот|шестьсот|семьсот|'
    r'восемьсот|девятьсот)|'
    r'(?:тысяча|тысячи|тысяч|миллион|миллиона|миллионов|млн)'
)

_PHRASE_RE = re.compile(
    rf'(?i)(?<!\w)(?:{_NUMBER_TOKEN})(?:\s+(?:{_NUMBER_TOKEN}))*(?!\w)',
)


def _normalize_token(token: str) -> str:
    return token.lower().replace('ё', 'е').strip('.,!')


def _parse_simple_chunk(tokens: list[str]) -> int | None:
    """Parse a chunk below one scale unit (0–999)."""
    total = 0
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in HUNDREDS:
            total += HUNDREDS[tok]
            i += 1
            continue
        if tok in TEENS:
            total += TEENS[tok]
            i += 1
            continue
        if tok in TENS:
            total += TENS[tok]
            i += 1
            if i < len(tokens) and tokens[i] in ONES:
                total += ONES[tokens[i]]
                i += 1
            continue
        if tok in ONES:
            total += ONES[tok]
            i += 1
            continue
        return None
    return total


def parse_number_words(phrase: str) -> Decimal | None:
    """Parse a spoken/mixed number phrase into Decimal, or None."""
    raw = phrase.strip()
    if not raw:
        return None

    cleaned = raw.replace(' ', '').replace(',', '.')
    try:
        value = Decimal(cleaned)
        if value >= 0:
            return value
    except (InvalidOperation, ValueError):
        pass

    tokens = [_normalize_token(t) for t in raw.split() if _normalize_token(t)]
    if not tokens:
        return None

    if tokens[0] in FRACTIONS:
        base = FRACTIONS[tokens[0]]
        if len(tokens) == 1:
            return base
        if len(tokens) == 2 and tokens[1] in SCALES:
            return base * SCALES[tokens[1]]
        return None

    total = Decimal('0')
    current_tokens: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if re.fullmatch(r'\d+(?:[.,]\d+)?', tok):
            if current_tokens:
                return None
            try:
                digit = Decimal(tok.replace(',', '.'))
            except (InvalidOperation, ValueError):
                return None
            if i + 1 < len(tokens) and tokens[i + 1] in SCALES:
                total += digit * SCALES[tokens[i + 1]]
                i += 2
                continue
            total += digit
            i += 1
            continue

        if tok in SCALES:
            chunk = _parse_simple_chunk(current_tokens) if current_tokens else 1
            if chunk is None:
                return None
            total += Decimal(chunk) * SCALES[tok]
            current_tokens = []
            i += 1
            continue

        current_tokens.append(tok)
        i += 1

    if current_tokens:
        chunk = _parse_simple_chunk(current_tokens)
        if chunk is None:
            return None
        total += Decimal(chunk)

    if total < 0:
        return None
    if total == 0 and 'ноль' not in tokens:
        return None
    return total


def _format_amount(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    formatted = format(value.normalize(), 'f')
    return formatted.rstrip('0').rstrip('.')


def replace_spoken_numbers(text: str) -> str:
    """Replace spoken number phrases in text with digit strings."""
    if not text or not text.strip():
        return text

    def _sub(match: re.Match[str]) -> str:
        phrase = match.group(0)
        if not re.search(r'[а-яА-ЯёЁ]', phrase):
            return phrase
        parsed = parse_number_words(phrase)
        if parsed is None:
            return phrase
        return _format_amount(parsed)

    return _PHRASE_RE.sub(_sub, text)
