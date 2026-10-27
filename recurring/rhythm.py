"""Сдвиг даты следующего раза. От «сегодня» ритм заново не строится."""

from datetime import date, timedelta
from decimal import Decimal

from recurring.models import RecurringTemplate

_MONTHS = (
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
)


def add_months(day: date, months: int) -> date:
    """Та же дата через несколько месяцев. 31-е сдвигается на последний день."""
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return date(year, month, min(day.day, last.day))


def advance(day: date, periodicity: str) -> date:
    """Один шаг ритма вперёд от якорной даты."""
    if periodicity == RecurringTemplate.WEEKLY:
        return day + timedelta(days=7)
    if periodicity == RecurringTemplate.YEARLY:
        return add_months(day, 12)
    if periodicity == RecurringTemplate.MONTHLY:
        return add_months(day, 1)
    raise ValueError(periodicity)


def roll_forward(day: date, periodicity: str, today: date) -> date:
    """Следующая дата после проведённого раза. Если она уже прошла, шаг повторяется."""
    nxt = advance(day, periodicity)
    while nxt <= today:
        nxt = advance(nxt, periodicity)
    return nxt


def format_due(day: date) -> str:
    return f'{day.day} {_MONTHS[day.month - 1]}'


def expectation_phrase(template: RecurringTemplate, money) -> str:
    """Как сказать про ожидаемую сумму. money(amount) -> строка."""
    if template.amount_kind == RecurringTemplate.EXACT:
        return f'обычно {money(template.amount)}'
    if template.amount_kind == RecurringTemplate.RANGE:
        return f'обычно {money(template.amount_min)}–{money(template.amount_max)}'
    return 'сумма каждый раз своя'


def due_templates(user, today: date):
    """Активные шаблоны, по которым сегодня пора напомнить один раз.

    Пустая отметка напоминания тоже считается «ещё не слали»: сравнение
    с NULL в SQL само по себе строку не оставляет.
    """
    from django.db.models import F, Q

    return (
        RecurringTemplate.objects.filter(
            user=user,
            is_active=True,
            next_due__lte=today,
            category__is_active=True,
        )
        .filter(Q(reminded_for__isnull=True) | ~Q(reminded_for=F('next_due')))
        .select_related('category')
        .order_by('next_due', 'name')
    )


def mark_reminded(template: RecurringTemplate) -> None:
    template.reminded_for = template.next_due
    template.save(update_fields=['reminded_for', 'updated_at'])


def expectation_lines(user, today: date) -> list[str]:
    """Строки блока «Повторяющиеся». Долгов здесь нет."""
    from transactions.currencies import base_for_user, symbol_of

    currency = base_for_user(user)

    def money(amount: Decimal) -> str:
        whole = int(Decimal(amount).quantize(Decimal('1')))
        grouped = f'{abs(whole):,}'.replace(',', ' ')
        return f'{grouped} {symbol_of(currency)}'

    lines = []
    templates = RecurringTemplate.objects.filter(
        user=user,
        is_active=True,
    ).select_related('category').order_by('next_due', 'name')
    for template in templates:
        lines.append(
            f'{template.name} — {format_due(template.next_due)}, '
            f'{expectation_phrase(template, money)}'
        )
    return lines
