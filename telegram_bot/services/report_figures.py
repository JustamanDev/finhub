"""Цифры Excel-отчётов. Без ORM и без записи в файл.

Свободно = доходы − расходы − отложено.
Отложено — чистое движение в цели и конверты: взносы минус снятия и покупки из резерва.
Покупка из резерва уже сидит в расходах, поэтому в «отложено» она со знаком минус
и свободно второй раз не уменьшает.
"""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


MONTHS = (
    'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
    'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
)
MONTHS_SHORT = (
    'янв', 'фев', 'мар', 'апр', 'май', 'июн',
    'июл', 'авг', 'сен', 'окт', 'ноя', 'дек',
)
MONTHS_OF = (
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
)
MONTHS_IN = (
    'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне',
    'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре',
)

ZERO = Decimal('0')
ACTIVE = 'active'


@dataclass(frozen=True)
class Flow:
    income: Decimal = ZERO
    expenses: Decimal = ZERO
    allocated: Decimal = ZERO

    @property
    def balance(self) -> Decimal:
        return self.income - self.expenses

    @property
    def free(self) -> Decimal:
        return self.balance - self.allocated

    def savings_ratio(self) -> Decimal | None:
        if self.income == 0:
            return None
        return self.balance / self.income


@dataclass(frozen=True)
class Tx:
    id: int
    day: date
    amount: Decimal
    category_id: int
    label: str
    description: str
    currency: str
    original_amount: Decimal


@dataclass(frozen=True)
class LedgerTx:
    day: date
    goal_id: int
    title: str
    is_envelope: bool
    entry_type: str
    amount: Decimal
    comment: str


@dataclass(frozen=True)
class GoalSnap:
    id: int
    title: str
    is_envelope: bool
    status: str
    target_amount: Decimal | None
    deadline: date | None


@dataclass(frozen=True)
class BudgetSnap:
    category_id: int
    label: str
    amount: Decimal
    start: date
    end: date
    is_active: bool


@dataclass(frozen=True)
class DayRow:
    day: date
    future: bool
    income: Decimal
    expenses: Decimal
    allocated: Decimal
    day_free: Decimal
    running_free: Decimal | None


@dataclass(frozen=True)
class WeekRow:
    start: date
    end: date
    future: bool
    flow: Flow


@dataclass(frozen=True)
class CategoryRow:
    label: str
    amount: Decimal
    share: Decimal | None
    limit: Decimal | None
    remaining: Decimal | None
    limit_ratio: Decimal | None


@dataclass(frozen=True)
class GoalRow:
    title: str
    status: str
    deadline: date | None
    target: Decimal
    committed: Decimal
    spent_total: Decimal
    balance: Decimal
    remaining: Decimal
    progress: Decimal | None
    plan_per_month: Decimal | None
    period_deposited: Decimal
    period_withdrawn: Decimal
    period_spent: Decimal


@dataclass(frozen=True)
class EnvelopeRow:
    title: str
    status: str
    deposited: Decimal
    spent: Decimal
    withdrawn: Decimal
    balance: Decimal
    period_deposited: Decimal
    period_spent: Decimal
    period_withdrawn: Decimal


@dataclass(frozen=True)
class MonthSlot:
    """Один месяц в годовой таблице. flow is None — месяц ещё не начался."""

    year: int
    month: int
    state: str
    flow: Flow | None
    daily_expense: Decimal | None
    expense_delta: Decimal | None


@dataclass(frozen=True)
class CategoryYearRow:
    label: str
    months: tuple[Decimal | None, ...]
    total: Decimal
    share: Decimal | None


@dataclass(frozen=True)
class MonthReport:
    year: int
    month: int
    today: date
    unit: str
    currency_phrase: str
    generated_label: str
    is_current: bool
    days_in_month: int
    days_elapsed: int
    flow: Flow
    previous: Flow
    previous_month: int
    comparison: str
    pace: str | None
    days: tuple[DayRow, ...]
    weeks: tuple[WeekRow, ...]
    expenses: tuple[CategoryRow, ...]
    incomes: tuple[CategoryRow, ...]
    goals: tuple[GoalRow, ...]
    envelopes: tuple[EnvelopeRow, ...]
    transactions: tuple[Tx, ...]
    ledger: tuple[LedgerTx, ...]


@dataclass(frozen=True)
class YearReport:
    year: int
    today: date
    unit: str
    currency_phrase: str
    generated_label: str
    flow: Flow
    months: tuple[MonthSlot, ...]
    expenses: tuple[CategoryYearRow, ...]
    incomes: tuple[CategoryYearRow, ...]
    goals: tuple[GoalRow, ...]
    envelopes: tuple[EnvelopeRow, ...]
    transactions: tuple[Tx, ...]
    ledger: tuple[LedgerTx, ...]


def period_title(year: int, month: int) -> str:
    return f'{MONTHS[month - 1].capitalize()} {year}'


def period_caption(year: int, month: int) -> str:
    return f'Отчёт за {MONTHS[month - 1]} {year}'


def year_caption(year: int) -> str:
    return f'Отчёт за {year} год'


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Первое число месяца и первое число следующего (конец не входит)."""
    start = date(year, month, 1)
    if month == 12:
        return start, date(year + 1, 1, 1)
    return start, date(year, month + 1, 1)


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def format_money(value: Decimal) -> str:
    whole = int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return f'{whole:,}'.replace(',', ' ')


def build_month_report(
    *,
    year: int,
    month: int,
    today: date,
    unit: str,
    currency_phrase: str,
    generated_label: str,
    transactions: list[Tx],
    ledger: list[LedgerTx],
    goals: list[GoalSnap],
    budgets: list[BudgetSnap],
) -> MonthReport:
    start, end = month_bounds(year, month)
    last = end - timedelta(days=1)
    as_of = last if today < start else min(today, last)
    is_current = start <= today <= last
    days_in_month = monthrange(year, month)[1]
    days_elapsed = today.day if is_current else days_in_month

    period_tx = _between(transactions, start, as_of)
    period_ledger = _between_ledger(ledger, start, as_of)
    flow = _flow(period_tx, period_ledger)

    prev_year, prev_month = previous_month(year, month)
    prev_start, prev_end = month_bounds(prev_year, prev_month)
    previous = _flow(
        _between(transactions, prev_start, prev_end - timedelta(days=1)),
        _between_ledger(ledger, prev_start, prev_end - timedelta(days=1)),
    )

    days = _days(start, last, as_of, period_tx, period_ledger)
    pace = None
    if is_current and today.day < days_in_month and days_elapsed > 0:
        pace = _pace_text(flow, days_elapsed, days_in_month, unit)

    return MonthReport(
        year=year,
        month=month,
        today=today,
        unit=unit,
        currency_phrase=currency_phrase,
        generated_label=generated_label,
        is_current=is_current,
        days_in_month=days_in_month,
        days_elapsed=days_elapsed,
        flow=flow,
        previous=previous,
        previous_month=prev_month,
        comparison=_comparison_text(flow, previous, prev_month, unit),
        pace=pace,
        days=days,
        weeks=_weeks(start, last, days),
        expenses=_expense_categories(period_tx, budgets, start, as_of, today),
        incomes=_income_categories(period_tx),
        goals=_goal_rows(goals, ledger, start, as_of),
        envelopes=_envelope_rows(goals, ledger, start, as_of),
        transactions=tuple(sorted(period_tx, key=lambda item: (item.day, item.id))),
        ledger=tuple(sorted(period_ledger, key=lambda item: (item.day, item.title))),
    )


def build_year_report(
    *,
    year: int,
    today: date,
    unit: str,
    currency_phrase: str,
    generated_label: str,
    transactions: list[Tx],
    ledger: list[LedgerTx],
    goals: list[GoalSnap],
    budgets: list[BudgetSnap],
) -> YearReport:
    del budgets  # лимиты живут в файле месяца, годовая матрица — про факт
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    as_of = year_end if today < year_start else min(today, year_end)

    slots: list[MonthSlot] = []
    expense_maps: list[dict[int, Decimal]] = []
    income_maps: list[dict[int, Decimal]] = []
    labels: dict[int, str] = {}
    for month in range(1, 13):
        start, end = month_bounds(year, month)
        last = end - timedelta(days=1)
        if start > as_of:
            slots.append(MonthSlot(year, month, 'future', None, None, None))
            expense_maps.append({})
            income_maps.append({})
            continue
        cut = min(last, as_of)
        month_tx = _between(transactions, start, cut)
        month_ledger = _between_ledger(ledger, start, cut)
        flow = _flow(month_tx, month_ledger)
        state = 'current' if start <= today <= last else 'past'
        elapsed = today.day if state == 'current' else monthrange(year, month)[1]
        daily = (flow.expenses / Decimal(elapsed)) if elapsed else None
        slots.append(MonthSlot(year, month, state, flow, daily, None))
        expense_maps.append(_signed_totals(month_tx, negative=True))
        income_maps.append(_signed_totals(month_tx, negative=False))
        for item in month_tx:
            labels[item.category_id] = item.label

    dec_start = date(year - 1, 12, 1)
    dec_end = date(year - 1, 12, 31)
    december = _flow(
        _between(transactions, dec_start, dec_end),
        _between_ledger(ledger, dec_start, dec_end),
    )
    slots = _with_deltas(slots, december)
    visible = [slot.flow for slot in slots if slot.flow is not None]

    return YearReport(
        year=year,
        today=today,
        unit=unit,
        currency_phrase=currency_phrase,
        generated_label=generated_label,
        flow=_sum_flows(visible),
        months=tuple(slots),
        expenses=_year_categories(labels, expense_maps, tuple(slot.state for slot in slots)),
        incomes=_year_categories(labels, income_maps, tuple(slot.state for slot in slots)),
        goals=_goal_rows(goals, ledger, year_start, as_of),
        envelopes=_envelope_rows(goals, ledger, year_start, as_of),
        transactions=tuple(sorted(
            _between(transactions, year_start, as_of),
            key=lambda item: (item.day, item.id),
        )),
        ledger=tuple(sorted(
            _between_ledger(ledger, year_start, as_of),
            key=lambda item: (item.day, item.title),
        )),
    )


def _with_deltas(slots: list[MonthSlot], december: Flow) -> list[MonthSlot]:
    updated: list[MonthSlot] = []
    previous_expenses = december.expenses
    have_previous = True
    for slot in slots:
        if slot.flow is None:
            updated.append(slot)
            have_previous = False
            continue
        delta = slot.flow.expenses - previous_expenses if have_previous else None
        updated.append(MonthSlot(
            slot.year,
            slot.month,
            slot.state,
            slot.flow,
            slot.daily_expense,
            delta,
        ))
        previous_expenses = slot.flow.expenses
        have_previous = True
    return updated


def _comparison_text(current: Flow, previous: Flow, previous_month: int, unit: str) -> str:
    name = MONTHS_IN[previous_month - 1]
    parts = []
    for label, left, right in (
        ('Расходы', current.expenses, previous.expenses),
        ('Свободно', current.free, previous.free),
    ):
        delta = left - right
        if delta == 0:
            parts.append(f'{label} — как в {name}')
        else:
            word = 'больше' if delta > 0 else 'меньше'
            parts.append(
                f'{label} на {format_money(abs(delta))} {unit} {word}, чем в {name}'
            )
    return '. '.join(parts) + '.'


def _pace_text(flow: Flow, days_elapsed: int, days_in_month: int, unit: str) -> str:
    average = flow.expenses / Decimal(days_elapsed)
    forecast = average * Decimal(days_in_month)
    return (
        f'Прошло {days_elapsed} из {days_in_month} дней. '
        f'Траты в день — {format_money(average)} {unit}. '
        f'Если так пойдёт дальше, расходы за месяц будут около {format_money(forecast)} {unit}.'
    )


def _days(
    start: date,
    last: date,
    as_of: date,
    transactions: list[Tx],
    ledger: list[LedgerTx],
) -> tuple[DayRow, ...]:
    income: dict[date, Decimal] = defaultdict(lambda: ZERO)
    expenses: dict[date, Decimal] = defaultdict(lambda: ZERO)
    allocated: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for item in transactions:
        if item.amount > 0:
            income[item.day] += item.amount
        elif item.amount < 0:
            expenses[item.day] += -item.amount
    for entry in ledger:
        allocated[entry.day] += entry.amount

    rows: list[DayRow] = []
    running = ZERO
    day = start
    while day <= last:
        if day > as_of:
            rows.append(DayRow(day, True, ZERO, ZERO, ZERO, ZERO, None))
        else:
            day_free = income[day] - expenses[day] - allocated[day]
            running += day_free
            rows.append(DayRow(
                day,
                False,
                income[day],
                expenses[day],
                allocated[day],
                day_free,
                running,
            ))
        day += timedelta(days=1)
    return tuple(rows)


def _weeks(start: date, last: date, days: tuple[DayRow, ...]) -> tuple[WeekRow, ...]:
    by_day = {row.day: row for row in days}
    cursor = start
    weeks: list[WeekRow] = []
    while cursor <= last:
        week_end = min(last, cursor + timedelta(days=(6 - cursor.weekday())))
        span = [
            by_day[cursor + timedelta(days=offset)]
            for offset in range((week_end - cursor).days + 1)
        ]
        active = [row for row in span if not row.future]
        if not active:
            weeks.append(WeekRow(cursor, week_end, True, Flow()))
        else:
            weeks.append(WeekRow(
                cursor,
                week_end,
                False,
                Flow(
                    sum((row.income for row in active), ZERO),
                    sum((row.expenses for row in active), ZERO),
                    sum((row.allocated for row in active), ZERO),
                ),
            ))
        cursor = week_end + timedelta(days=1)
    return tuple(weeks)


def _expense_categories(
    transactions: list[Tx],
    budgets: list[BudgetSnap],
    start: date,
    as_of: date,
    today: date,
) -> tuple[CategoryRow, ...]:
    totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
    labels: dict[int, str] = {}
    for item in transactions:
        if item.amount < 0:
            totals[item.category_id] += -item.amount
            labels[item.category_id] = item.label

    limits: dict[int, BudgetSnap] = {}
    for budget in budgets:
        if budget.start > as_of or budget.end < start:
            continue
        if not budget.is_active and budget.end >= today:
            continue
        current = limits.get(budget.category_id)
        if current is None or budget.start >= current.start:
            limits[budget.category_id] = budget
            labels.setdefault(budget.category_id, budget.label)

    total = sum(totals.values(), ZERO)
    rows: list[CategoryRow] = []
    for category_id, label in labels.items():
        amount = totals.get(category_id, ZERO)
        budget = limits.get(category_id)
        limit = remaining = ratio = None
        if budget is not None:
            limit = budget.amount
            remaining = limit - amount
            ratio = (amount / limit) if limit else None
        share = (amount / total) if total else None
        rows.append(CategoryRow(label, amount, share, limit, remaining, ratio))
    rows.sort(key=lambda row: (-row.amount, row.label))
    return tuple(rows)


def _income_categories(transactions: list[Tx]) -> tuple[CategoryRow, ...]:
    totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
    labels: dict[int, str] = {}
    for item in transactions:
        if item.amount > 0:
            totals[item.category_id] += item.amount
            labels[item.category_id] = item.label
    total = sum(totals.values(), ZERO)
    rows = [
        CategoryRow(
            labels[category_id],
            amount,
            (amount / total) if total else None,
            None,
            None,
            None,
        )
        for category_id, amount in totals.items()
    ]
    rows.sort(key=lambda row: (-row.amount, row.label))
    return tuple(rows)


def _year_categories(
    labels: dict[int, str],
    monthly: list[dict[int, Decimal]],
    states: tuple[str, ...],
) -> tuple[CategoryYearRow, ...]:
    totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for mapping in monthly:
        for category_id, amount in mapping.items():
            totals[category_id] += amount
    grand = sum(totals.values(), ZERO)
    rows: list[CategoryYearRow] = []
    for category_id, label in labels.items():
        cells: list[Decimal | None] = []
        for index, mapping in enumerate(monthly):
            if states[index] == 'future':
                cells.append(None)
            else:
                cells.append(mapping.get(category_id, ZERO))
        total = totals.get(category_id, ZERO)
        rows.append(CategoryYearRow(
            label,
            tuple(cells),
            total,
            (total / grand) if grand else None,
        ))
    rows.sort(key=lambda row: (-row.total, row.label))
    return tuple(rows)


def _goal_rows(
    goals: list[GoalSnap],
    ledger: list[LedgerTx],
    period_start: date,
    as_of: date,
) -> tuple[GoalRow, ...]:
    rows: list[GoalRow] = []
    for goal in goals:
        if goal.is_envelope:
            continue
        stock = _parts([entry for entry in ledger if entry.goal_id == goal.id and entry.day <= as_of])
        period = _parts([
            entry for entry in ledger
            if entry.goal_id == goal.id and period_start <= entry.day <= as_of
        ])
        if goal.status != ACTIVE and not _moved(stock) and not _moved(period):
            continue
        deposited, withdrawn, spent = stock
        committed = deposited - withdrawn
        balance = committed - spent
        target = goal.target_amount or ZERO
        remaining = max(target - committed, ZERO)
        progress = (committed / target) if target > 0 else None
        plan = None
        if (
            goal.deadline
            and goal.deadline >= as_of
            and goal.status == ACTIVE
            and target > 0
        ):
            months_left = (
                (goal.deadline.year - as_of.year) * 12
                + (goal.deadline.month - as_of.month)
                + 1
            )
            if months_left > 0:
                plan = (remaining / Decimal(months_left)).quantize(Decimal('0.01'))
        rows.append(GoalRow(
            title=goal.title,
            status=goal.status,
            deadline=goal.deadline,
            target=target,
            committed=committed,
            spent_total=spent,
            balance=balance,
            remaining=remaining,
            progress=progress,
            plan_per_month=plan,
            period_deposited=period[0],
            period_withdrawn=period[1],
            period_spent=period[2],
        ))
    rows.sort(key=lambda row: row.title)
    return tuple(rows)


def _envelope_rows(
    goals: list[GoalSnap],
    ledger: list[LedgerTx],
    period_start: date,
    as_of: date,
) -> tuple[EnvelopeRow, ...]:
    rows: list[EnvelopeRow] = []
    for goal in goals:
        if not goal.is_envelope:
            continue
        own = [entry for entry in ledger if entry.goal_id == goal.id and entry.day <= as_of]
        stock = _parts(own)
        period = _parts([
            entry for entry in own
            if period_start <= entry.day <= as_of
        ])
        if goal.status != ACTIVE and not _moved(stock) and not _moved(period):
            continue
        deposited, withdrawn, spent = stock
        rows.append(EnvelopeRow(
            title=goal.title,
            status=goal.status,
            deposited=deposited,
            spent=spent,
            withdrawn=withdrawn,
            balance=deposited - withdrawn - spent,
            period_deposited=period[0],
            period_spent=period[2],
            period_withdrawn=period[1],
        ))
    rows.sort(key=lambda row: row.title)
    return tuple(rows)


def _parts(entries: list[LedgerTx]) -> tuple[Decimal, Decimal, Decimal]:
    deposited = withdrawn = spent = ZERO
    for entry in entries:
        if entry.entry_type == 'deposit':
            deposited += entry.amount
        elif entry.entry_type == 'withdraw':
            withdrawn += abs(entry.amount)
        elif entry.entry_type == 'spend':
            spent += abs(entry.amount)
    return deposited, withdrawn, spent


def _moved(parts: tuple[Decimal, Decimal, Decimal]) -> bool:
    return any(part != 0 for part in parts)


def _signed_totals(transactions: list[Tx], *, negative: bool) -> dict[int, Decimal]:
    totals: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for item in transactions:
        if negative and item.amount < 0:
            totals[item.category_id] += -item.amount
        elif not negative and item.amount > 0:
            totals[item.category_id] += item.amount
    return totals


def _flow(transactions: list[Tx], ledger: list[LedgerTx]) -> Flow:
    income = sum((item.amount for item in transactions if item.amount > 0), ZERO)
    expenses = sum((-item.amount for item in transactions if item.amount < 0), ZERO)
    allocated = sum((entry.amount for entry in ledger), ZERO)
    return Flow(income, expenses, allocated)


def _sum_flows(flows: list[Flow]) -> Flow:
    return Flow(
        sum((item.income for item in flows), ZERO),
        sum((item.expenses for item in flows), ZERO),
        sum((item.allocated for item in flows), ZERO),
    )


def _between(transactions: list[Tx], start: date, end: date) -> list[Tx]:
    return [item for item in transactions if start <= item.day <= end and item.amount != 0]


def _between_ledger(ledger: list[LedgerTx], start: date, end: date) -> list[LedgerTx]:
    return [entry for entry in ledger if start <= entry.day <= end]
