"""Срок цели по фактическому темпу отложений и дедлайну.

Числа считает код. Консультант только пересказывает готовые поля.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING

ETA_MONTH_CAP = 120

STATUS_REACHED = 'reached'
STATUS_OVERDUE = 'overdue'
STATUS_ON_TRACK = 'on_track'
STATUS_BEHIND = 'behind'
STATUS_NO_PACE = 'no_pace'
STATUS_NO_DEADLINE = 'no_deadline'

_MONTHS = (
    'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
)


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal('0.01')))


def _month_label(value: date) -> str:
    return f'{_MONTHS[value.month - 1]} {value.year}'


def _add_months(anchor: date, months: int) -> date:
    index = anchor.month - 1 + months
    year = anchor.year + index // 12
    month = index % 12 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _months_inclusive(today: date, deadline: date) -> int:
    return (deadline.year - today.year) * 12 + (deadline.month - today.month) + 1


@dataclass(frozen=True)
class GoalEta:
    status: str
    remaining: Decimal
    pace_per_month: Decimal | None
    pace_months: int
    required_per_month: Decimal | None
    months_until_deadline: int | None
    eta_months: int | None
    eta_date: date | None
    deposited_this_month: Decimal
    still_needed_this_month: Decimal | None
    free_funds: Decimal
    pace_too_slow: bool = False

    def as_dict(self) -> dict:
        return {
            'status': self.status,
            'remaining': _money(self.remaining),
            'pace_per_month': (
                None if self.pace_per_month is None else _money(self.pace_per_month)
            ),
            'pace_months': self.pace_months,
            'required_per_month': (
                None
                if self.required_per_month is None
                else _money(self.required_per_month)
            ),
            'months_until_deadline': self.months_until_deadline,
            'eta_months': self.eta_months,
            'eta_date': self.eta_date.isoformat() if self.eta_date else None,
            'eta_label': _month_label(self.eta_date) if self.eta_date else None,
            'deposited_this_month': _money(self.deposited_this_month),
            'still_needed_this_month': (
                None
                if self.still_needed_this_month is None
                else _money(self.still_needed_this_month)
            ),
            'free_funds': _money(self.free_funds),
            'free_funds_cover_rest': (
                None
                if self.still_needed_this_month is None
                else self.free_funds >= self.still_needed_this_month
            ),
            'pace_too_slow': self.pace_too_slow,
        }


def build_goal_eta(
    *,
    today: date,
    target: Decimal,
    balance: Decimal,
    deadline: date | None,
    monthly_nets: list[Decimal],
    deposited_this_month: Decimal,
    free_funds: Decimal,
) -> GoalEta:
    """
    monthly_nets — нетто отложений за завершённые месяцы, от старых к новым.
    Текущий неполный месяц в темп не входит.
    """
    remaining = max(Decimal(target) - Decimal(balance), Decimal('0'))
    deposited = Decimal(deposited_this_month or 0)
    free = Decimal(free_funds or 0)

    pace: Decimal | None = None
    pace_months = len(monthly_nets)
    if monthly_nets:
        pace = (
            sum((Decimal(item) for item in monthly_nets), Decimal('0'))
            / Decimal(pace_months)
        ).quantize(Decimal('0.01'))

    months_until: int | None = None
    required: Decimal | None = None
    if deadline is not None and deadline >= today and remaining > 0:
        months_until = _months_inclusive(today, deadline)
        if months_until > 0:
            required = (remaining / Decimal(months_until)).quantize(Decimal('0.01'))

    eta_months: int | None = None
    eta_date: date | None = None
    pace_too_slow = False
    if remaining == 0:
        eta_months = 0
        eta_date = today
    elif pace is not None and pace > 0:
        raw = (remaining / pace).to_integral_value(rounding=ROUND_CEILING)
        if raw > ETA_MONTH_CAP:
            pace_too_slow = True
        else:
            eta_months = int(raw)
            eta_date = _add_months(today, eta_months)

    if remaining == 0:
        status = STATUS_REACHED
    elif deadline is not None and deadline < today:
        status = STATUS_OVERDUE
    elif deadline is None:
        status = STATUS_NO_DEADLINE
    elif pace is None or pace <= 0:
        status = STATUS_NO_PACE
    elif required is not None and pace + Decimal('0.01') >= required:
        status = STATUS_ON_TRACK
    else:
        status = STATUS_BEHIND

    still_needed: Decimal | None = None
    if required is not None:
        still_needed = max(required - deposited, Decimal('0'))

    return GoalEta(
        status=status,
        remaining=remaining.quantize(Decimal('0.01')),
        pace_per_month=pace,
        pace_months=pace_months,
        required_per_month=required,
        months_until_deadline=months_until,
        eta_months=eta_months,
        eta_date=eta_date,
        deposited_this_month=deposited.quantize(Decimal('0.01')),
        still_needed_this_month=still_needed,
        free_funds=free.quantize(Decimal('0.01')),
        pace_too_slow=pace_too_slow,
    )


def format_goal_eta_lines(eta: GoalEta) -> list[str]:
    """Короткие строки для карточки цели. Те же числа, что у консультанта."""
    if eta.status == STATUS_REACHED:
        return ['Цель собрана.']
    if eta.status == STATUS_OVERDUE:
        return [f'Дедлайн прошёл. Осталось {eta.remaining:,.0f} ₽.']

    lines: list[str] = []
    if eta.pace_per_month is not None and eta.pace_months and eta.pace_per_month > 0:
        pace = f'{eta.pace_per_month:,.0f} ₽'
        if eta.pace_too_slow and eta.status != STATUS_ON_TRACK:
            lines.append(
                f'За последние {eta.pace_months} мес. в цель уходило около {pace} '
                'в месяц. При таком темпе она не закроется в ближайшие 10 лет.',
            )
        elif eta.pace_too_slow:
            lines.append(
                f'За последние {eta.pace_months} мес. в цель уходило около {pace} '
                'в месяц. Дата закрытия дальше 10 лет, к дедлайну темп успевает.',
            )
        elif eta.eta_date is not None:
            lines.append(
                f'За последние {eta.pace_months} мес. в цель уходило около {pace} '
                f'в месяц. Так она закроется примерно в {_month_label(eta.eta_date)}.',
            )
    elif eta.pace_months and eta.pace_per_month is not None and eta.pace_per_month <= 0:
        lines.append(
            f'За последние {eta.pace_months} мес. цель почти не пополнялась.',
        )
    elif eta.deposited_this_month > 0:
        lines.append(
            f'В этом месяце уже внесено {eta.deposited_this_month:,.0f} ₽. '
            'Темп посчитается, когда закроется хотя бы один полный месяц.',
        )
    else:
        lines.append('За прошлые месяцы отложений ещё нет — темп посчитать не из чего.')

    if eta.required_per_month is not None:
        required = f'{eta.required_per_month:,.0f} ₽'
        if eta.status == STATUS_ON_TRACK and not eta.pace_too_slow:
            lines.append(
                f'К дедлайну нужно {required} в месяц. Текущий темп успевает.',
            )
        elif eta.status == STATUS_ON_TRACK:
            lines.append(f'К дедлайну нужно {required} в месяц.')
        elif eta.status == STATUS_BEHIND:
            lines.append(
                f'К дедлайну нужно {required} в месяц. Текущий темп не успевает.',
            )
        else:
            lines.append(
                f'Чтобы успеть к дедлайну, нужно откладывать {required} в месяц.',
            )
    elif eta.status == STATUS_NO_DEADLINE and eta.eta_date is None and not eta.pace_too_slow:
        lines.append('Дедлайна нет, поэтому «успеть к дате» посчитать нельзя.')
    return lines
