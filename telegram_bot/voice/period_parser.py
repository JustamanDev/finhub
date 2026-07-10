"""Parse Russian period phrases for ASK_ADVISOR questions."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

MONTH_FULL: dict[str, int] = {
    'январь': 1,
    'января': 1,
    'январе': 1,
    'февраль': 2,
    'февраля': 2,
    'феврале': 2,
    'март': 3,
    'марта': 3,
    'марте': 3,
    'апрель': 4,
    'апреля': 4,
    'апреле': 4,
    'май': 5,
    'мая': 5,
    'мае': 5,
    'июнь': 6,
    'июня': 6,
    'июне': 6,
    'июль': 7,
    'июля': 7,
    'июле': 7,
    'август': 8,
    'августа': 8,
    'августе': 8,
    'сентябрь': 9,
    'сентября': 9,
    'сентябре': 9,
    'октябрь': 10,
    'октября': 10,
    'октябре': 10,
    'ноябрь': 11,
    'ноября': 11,
    'ноябре': 11,
    'декабрь': 12,
    'декабря': 12,
    'декабре': 12,
}

# Cap multi-month series length for ASK_ADVISOR latency.
MAX_TREND_MONTHS = 12
DEFAULT_TREND_MONTHS = 6
MIN_TREND_MONTHS = 3


@dataclass(frozen=True)
class ParsedPeriod:
    year: int
    month: int
    label: str
    is_current: bool = False
    wants_comparison: bool = False
    trend_months: int | None = None
    category_hint: str | None = None


def _shift_month(anchor: date, delta: int) -> date:
    month = anchor.month + delta
    year = anchor.year
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_label(year: int, month: int) -> str:
    names = [
        'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
        'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
    ]
    return f'{names[month - 1]} {year}'


def _clamp_trend_months(value: int) -> int:
    return max(MIN_TREND_MONTHS, min(MAX_TREND_MONTHS, value))


def parse_trend_months(question: str) -> int | None:
    """Return multi-month window length if the question asks for a trend."""
    text = (question or '').lower().replace('ё', 'е')

    if re.search(r'за\s+(?:последн\w*\s+)?год(?:\s|$|[?.!,])', text):
        return 12
    if re.search(r'за\s+(?:последн\w*\s+)?12\s+месяц', text):
        return 12
    if re.search(r'за\s+полгода', text):
        return 6
    if re.search(r'за\s+квартал', text):
        return 3

    digit = re.search(
        r'за\s+(?:последн\w*\s+)?(\d{1,2})\s+месяц',
        text,
    )
    if digit:
        return _clamp_trend_months(int(digit.group(1)))

    # «как менялись расходы», «динамика», «тренд» — default window
    if re.search(r'(как\s+менял\w*|динамик\w*|тренд\w*)', text):
        return DEFAULT_TREND_MONTHS

    # Coping / deficit overview without explicit window → year lookback
    if re.search(
        r'(справлял\w*|часто\s+.*\s+минус|был\s+минус|в\s+минусе|'
        r'отрицательн\w*\s+баланс|более[- ]менее\s+нормальн)',
        text,
    ):
        return 12

    return None


_CATEGORY_STOP = (
    r'за|в|с|по|как|растут|падают|растёт|растет|падает|месяц\w*|год\w*|'
    r'полгода|квартал|прошл\w*|предыдущ\w*|этот|этом|этого|динамик\w*|'
    r'тренд\w*|сравн\w*|часто|был|была|было|ли|или|и|а|но'
)


def parse_category_hint(question: str) -> str | None:
    """Extract a spoken category fragment from an advisor question."""
    text = (question or '').lower().replace('ё', 'е')
    patterns = (
        r'по\s+категории\s+([а-яa-z0-9][а-яa-z0-9\s\-]{1,40})',
        r'(?:трат\w*|расход\w*|тратил\w*|потратил\w*|потрачен\w*|'
        r'динамик\w*|тренд\w*|менял\w*)'
        r'.{0,30}?\s+на\s+([а-яa-z0-9][а-яa-z0-9\s\-]{1,40})',
        r'\sна\s+([а-яa-z0-9][а-яa-z0-9\s\-]{1,40})',
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1).strip(' .,!?')
        raw = re.split(rf'\s+(?:{_CATEGORY_STOP})\b', raw, maxsplit=1)[0]
        raw = raw.strip(' .,!?-')
        if len(raw) < 2:
            continue
        # Skip pure time words mistaken for categories
        if re.fullmatch(
            r'(год|месяц|квартал|полгода|прошлый|предыдущий|этот)',
            raw,
        ):
            continue
        return raw
    return None


def parse_advisor_period(question: str, today: date | None = None) -> ParsedPeriod:
    """Extract target calendar month from a Russian advisor question."""
    today = today or date.today()
    text = (question or '').lower().replace('ё', 'е')
    trend_months = parse_trend_months(text)
    category_hint = parse_category_hint(text)
    # Category + growth/decline wording implies a multi-month lookback
    if category_hint and trend_months is None and re.search(
        r'(растут|падают|растёт|растет|падает|менял\w*|динамик\w*|тренд\w*)',
        text,
    ):
        trend_months = DEFAULT_TREND_MONTHS
    wants_comparison = bool(
        re.search(
            r'(сравн|против|чем\s+в\s+прошл|динамика|тренд|разниц|'
            r'растут|падают|растёт|растет|падает)',
            text,
        ),
    ) or trend_months is not None
    month_start = date(today.year, today.month, 1)

    # «сравни прошлый месяц с …» — previous is the subject (before позапрошлый)
    if re.search(r'сравн\w*\s+(прошл\w*|предыдущ\w*)\s+месяц', text):
        target = _shift_month(month_start, -1)
        return ParsedPeriod(
            year=target.year,
            month=target.month,
            label=_month_label(target.year, target.month),
            wants_comparison=True,
            trend_months=trend_months,
            category_hint=category_hint,
        )

    if re.search(r'позапрошл\w*\s+месяц', text):
        # «с позапрошлым» is a baseline, not the primary period
        if not re.search(r'с\s+позапрошл', text):
            target = _shift_month(month_start, -2)
            return ParsedPeriod(
                year=target.year,
                month=target.month,
                label=_month_label(target.year, target.month),
                wants_comparison=True,
                trend_months=trend_months,
                category_hint=category_hint,
            )

    if re.search(r'(прошл\w*|предыдущ\w*)\s+месяц', text):
        # «сравни с прошлым» / «чем в прошлом» — keep current as primary;
        # previous month is always available via previous_period / MoM.
        used_as_comparison_baseline = bool(
            re.search(
                r'(с\s+(?:прошл\w*|предыдущ\w*)\s+месяц|'
                r'чем\s+в\s+(?:прошл|предыдущ)|'
                r'против\s+(?:прошл|предыдущ)|'
                r'относительно\s+(?:прошл|предыдущ))',
                text,
            )
        )
        if not used_as_comparison_baseline:
            target = _shift_month(month_start, -1)
            return ParsedPeriod(
                year=target.year,
                month=target.month,
                label=_month_label(target.year, target.month),
                wants_comparison=wants_comparison,
                trend_months=trend_months,
                category_hint=category_hint,
            )

    # Explicit month name + optional year: «в январе», «за март 2025»
    # Longer names first so «сентября» wins over shorter collisions.
    for name in sorted(MONTH_FULL.keys(), key=len, reverse=True):
        if not re.search(rf'(?<![а-я]){re.escape(name)}(?![а-я])', text):
            continue
        month = MONTH_FULL[name]
        year = today.year
        year_match = re.search(r'(20\d{2})', text)
        if year_match:
            year = int(year_match.group(1))
        elif month > today.month:
            year = today.year - 1
        return ParsedPeriod(
            year=year,
            month=month,
            label=_month_label(year, month),
            is_current=(year == today.year and month == today.month),
            wants_comparison=wants_comparison,
            trend_months=trend_months,
            category_hint=category_hint,
        )

    return ParsedPeriod(
        year=today.year,
        month=today.month,
        label=_month_label(today.year, today.month),
        is_current=True,
        wants_comparison=wants_comparison,
        trend_months=trend_months,
        category_hint=category_hint,
    )
