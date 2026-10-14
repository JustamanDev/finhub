"""Недельная сводка: цифры в рублях и статья Telegram с таблицами.

Неделя считается по календарю Вьетнама (Asia/Ho_Chi_Minh): с понедельника
по воскресенье. По понедельникам в 09:00 бот сам присылает итог прошедшей
недели. Команда /week показывает неделю, которая ещё идёт.

Статья уходит через sendRichMessage (Bot API: html с <table>). Если метод
недоступен, то же содержание уходит обычным HTML без таблиц.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from budgets.models import Budget
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.models import TelegramUser, UserState
from telegram_bot.services.goal_eta import build_goal_eta
from transactions.models import Transaction

logger = logging.getLogger(__name__)

VIETNAM = ZoneInfo('Asia/Ho_Chi_Minh')
SEND_HOUR = 9
DIGEST_CONTEXT_KEY = 'weekly_digest_week'
_MAX_CATEGORY_ROWS = 8
_MAX_GOAL_ROWS = 6

_MONTHS_GENITIVE = (
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
)


@dataclass(frozen=True)
class MoneyRow:
    label: str
    amount: Decimal


@dataclass(frozen=True)
class BudgetRow:
    category: str
    spent: Decimal
    limit: Decimal
    remaining: Decimal


@dataclass(frozen=True)
class GoalRow:
    title: str
    balance: Decimal
    target: Decimal
    note: str


@dataclass(frozen=True)
class WeeklyDigest:
    start: date
    end: date
    in_progress: bool
    income: Decimal
    expenses: Decimal
    allocations: Decimal
    expense_rows: tuple[MoneyRow, ...]
    expense_rest_count: int
    expense_rest_amount: Decimal
    income_rows: tuple[MoneyRow, ...]
    budget_rows: tuple[BudgetRow, ...]
    goal_rows: tuple[GoalRow, ...]

    @property
    def balance(self) -> Decimal:
        return self.income - self.expenses

    @property
    def free_funds(self) -> Decimal:
        return self.income - self.expenses - self.allocations


def vietnam_today(now: datetime | None = None) -> date:
    current = now or datetime.now(VIETNAM)
    return current.astimezone(VIETNAM).date()


def completed_week(today: date) -> tuple[date, date]:
    """Прошедшие понедельник–воскресенье относительно today."""
    this_monday = today - timedelta(days=today.weekday())
    start = this_monday - timedelta(days=7)
    end = this_monday - timedelta(days=1)
    return start, end


def current_week(today: date) -> tuple[date, date]:
    """Понедельник текущей недели и today включительно."""
    start = today - timedelta(days=today.weekday())
    return start, today


def seconds_until_next_send(now: datetime | None = None) -> float:
    """Секунды до ближайших 09:00 по Вьетнаму."""
    current = (now or datetime.now(VIETNAM)).astimezone(VIETNAM)
    target = current.replace(hour=SEND_HOUR, minute=0, second=0, microsecond=0)
    if current >= target:
        target += timedelta(days=1)
    return max((target - current).total_seconds(), 1.0)


def format_rub(value: Decimal) -> str:
    whole = int(Decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    sign = '−' if whole < 0 else ''
    grouped = f'{abs(whole):,}'.replace(',', ' ')
    return f'{sign}{grouped} ₽'


def period_label(start: date, end: date) -> str:
    if start == end:
        return f'{start.day} {_MONTHS_GENITIVE[start.month - 1]}'
    if start.month == end.month and start.year == end.year:
        return f'{start.day}–{end.day} {_MONTHS_GENITIVE[end.month - 1]}'
    if start.year == end.year:
        return (
            f'{start.day} {_MONTHS_GENITIVE[start.month - 1]}'
            f' – {end.day} {_MONTHS_GENITIVE[end.month - 1]}'
        )
    return (
        f'{start.day} {_MONTHS_GENITIVE[start.month - 1]} {start.year}'
        f' – {end.day} {_MONTHS_GENITIVE[end.month - 1]} {end.year}'
    )


def build_weekly_digest(
    user,
    start: date,
    end: date,
    *,
    today: date,
    in_progress: bool,
) -> WeeklyDigest:
    """Собирает сводку. Вызывать из синхронного контекста (ORM)."""
    income, expenses, expense_rows, income_rows, rest_count, rest_amount = _cashflow(
        user,
        start,
        end,
    )
    allocations = _goal_allocations(user, start, end)
    return WeeklyDigest(
        start=start,
        end=end,
        in_progress=in_progress,
        income=income,
        expenses=expenses,
        allocations=allocations,
        expense_rows=expense_rows,
        expense_rest_count=rest_count,
        expense_rest_amount=rest_amount,
        income_rows=income_rows,
        budget_rows=_budget_rows(user, start, end),
        goal_rows=_goal_rows(user, today),
    )


def already_sent(telegram_user: TelegramUser, week_start: date) -> bool:
    state = UserState.objects.filter(telegram_user=telegram_user).first()
    if state is None:
        return False
    stored = (state.context_data or {}).get(DIGEST_CONTEXT_KEY)
    return stored == week_start.isoformat()


def mark_sent(telegram_user: TelegramUser, week_start: date) -> None:
    state, _created = UserState.objects.get_or_create(telegram_user=telegram_user)
    data = dict(state.context_data or {})
    data[DIGEST_CONTEXT_KEY] = week_start.isoformat()
    state.context_data = data
    state.save(update_fields=['context_data', 'updated_at'])


def render_rich_html(digest: WeeklyDigest) -> str:
    """HTML для sendRichMessage: заголовки и таблицы."""
    title = period_label(digest.start, digest.end)
    if digest.in_progress:
        heading = f'Эта неделя, {title}'
        lead = 'Неделя ещё идёт. Цифры с понедельника по сегодня, всё в рублях.'
    else:
        heading = f'Неделя {title}'
        lead = 'Итог прошедшей недели. Всё в рублях.'

    parts = [
        f'<h1>{escape(heading)}</h1>',
        f'<p>{escape(lead)}</p>',
        _rich_table(
            'Движение денег',
            ('Статья', 'Сумма'),
            [
                ('Доход', format_rub(digest.income), False),
                ('Расход', format_rub(digest.expenses), False),
                ('Баланс', format_rub(digest.balance), True),
                ('В цели', format_rub(digest.allocations), False),
                ('Свободно', format_rub(digest.free_funds), True),
            ],
        ),
    ]
    parts.append('<h2>Куда ушли деньги</h2>')
    if digest.expense_rows:
        rows = [
            (row.label, format_rub(row.amount), False)
            for row in digest.expense_rows
        ]
        if digest.expense_rest_count:
            rows.append((
                f'Ещё {digest.expense_rest_count}',
                format_rub(digest.expense_rest_amount),
                False,
            ))
        parts.append(_rich_table('Расходы по категориям', ('Категория', 'Сумма'), rows))
    else:
        parts.append('<p>За эту неделю расходов не было.</p>')

    if digest.income_rows:
        parts.append('<h2>Откуда пришли деньги</h2>')
        parts.append(_rich_table(
            'Доходы по категориям',
            ('Категория', 'Сумма'),
            [(row.label, format_rub(row.amount), False) for row in digest.income_rows],
        ))

    parts.append('<h2>Лимиты</h2>')
    if digest.budget_rows:
        parts.append(
            '<p>Факт посчитан за весь срок лимита, не только за эту неделю.</p>',
        )
        parts.append(_rich_table(
            'Лимиты',
            ('Категория', 'Факт', 'Лимит', 'Осталось'),
            [
                (
                    row.category,
                    format_rub(row.spent),
                    format_rub(row.limit),
                    format_rub(row.remaining),
                )
                for row in digest.budget_rows
            ],
        ))
    else:
        parts.append('<p>Активных лимитов на эту неделю нет.</p>')

    parts.append('<h2>Цели</h2>')
    if digest.goal_rows:
        parts.append(_rich_table(
            'Цели',
            ('Цель', 'Собрано', 'К сроку'),
            [
                (
                    row.title,
                    f'{format_rub(row.balance)} / {format_rub(row.target)}',
                    row.note,
                )
                for row in digest.goal_rows
            ],
        ))
    else:
        parts.append('<p>Активных целей нет.</p>')

    if digest.in_progress:
        footer = (
            'По понедельникам в 9:00 по времени Вьетнама приходит итог '
            'прошедшей недели.'
        )
    else:
        footer = 'Текущую неделю можно открыть командой /week или кнопкой «Неделя».'
    parts.append(f'<p><i>{escape(footer)}</i></p>')
    return '\n'.join(parts)


def render_legacy_html(digest: WeeklyDigest) -> str:
    """Обычный HTML Telegram, если статья недоступна."""
    title = period_label(digest.start, digest.end)
    heading = f'Эта неделя, {title}' if digest.in_progress else f'Неделя {title}'
    lines = [
        f'<b>{escape(heading)}</b>',
        '',
        f'Доход: <b>{escape(format_rub(digest.income))}</b>',
        f'Расход: <b>{escape(format_rub(digest.expenses))}</b>',
        f'Баланс: <b>{escape(format_rub(digest.balance))}</b>',
        f'В цели: {escape(format_rub(digest.allocations))}',
        f'Свободно: <b>{escape(format_rub(digest.free_funds))}</b>',
        '',
        '<b>Куда ушли деньги</b>',
    ]
    if digest.expense_rows:
        for row in digest.expense_rows:
            lines.append(f'• {escape(row.label)} — {escape(format_rub(row.amount))}')
        if digest.expense_rest_count:
            lines.append(
                f'• Ещё {digest.expense_rest_count} — '
                f'{escape(format_rub(digest.expense_rest_amount))}',
            )
    else:
        lines.append('За эту неделю расходов не было.')

    if digest.income_rows:
        lines.append('')
        lines.append('<b>Откуда пришли деньги</b>')
        for row in digest.income_rows:
            lines.append(f'• {escape(row.label)} — {escape(format_rub(row.amount))}')

    lines.append('')
    lines.append('<b>Лимиты</b>')
    if digest.budget_rows:
        lines.append('Факт за весь срок лимита.')
        for row in digest.budget_rows:
            lines.append(
                f'• {escape(row.category)}: {escape(format_rub(row.spent))} '
                f'из {escape(format_rub(row.limit))}, '
                f'осталось {escape(format_rub(row.remaining))}',
            )
    else:
        lines.append('Активных лимитов на эту неделю нет.')

    lines.append('')
    lines.append('<b>Цели</b>')
    if digest.goal_rows:
        for row in digest.goal_rows:
            lines.append(
                f'• {escape(row.title)}: {escape(format_rub(row.balance))} '
                f'из {escape(format_rub(row.target))} — {escape(row.note)}',
            )
    else:
        lines.append('Активных целей нет.')
    return '\n'.join(lines)


async def send_weekly_digest(bot, chat_id: int, digest: WeeklyDigest) -> None:
    """Шлёт статью. При ошибке API — обычное HTML-сообщение."""
    from telegram_bot.keyboards.actions import ActionKeyboard

    menu = ActionKeyboard.get_main_menu_keyboard()
    rich_message = {
        'html': render_rich_html(digest),
        'skip_entity_detection': True,
    }
    try:
        await bot.do_api_request(
            'sendRichMessage',
            api_kwargs={
                'chat_id': chat_id,
                'rich_message': rich_message,
                'reply_markup': menu.to_dict(),
            },
        )
        return
    except Exception:
        logger.exception('sendRichMessage с меню не прошёл, повторяю без клавиатуры')
    try:
        await bot.do_api_request(
            'sendRichMessage',
            api_kwargs={
                'chat_id': chat_id,
                'rich_message': rich_message,
            },
        )
        await bot.send_message(
            chat_id=chat_id,
            text='Главное меню:',
            reply_markup=menu,
        )
    except Exception:
        logger.exception('sendRichMessage не прошёл, отправляю обычный HTML')
        await bot.send_message(
            chat_id=chat_id,
            text=render_legacy_html(digest),
            parse_mode='HTML',
            reply_markup=menu,
        )


async def push_current_week(bot, telegram_user: TelegramUser, chat_id: int) -> None:
    """Сводка текущей недели по запросу пользователя."""
    from asgiref.sync import sync_to_async

    user = await sync_to_async(lambda: telegram_user.user)()
    today = vietnam_today()
    start, end = current_week(today)
    digest = await sync_to_async(build_weekly_digest)(
        user,
        start,
        end,
        today=today,
        in_progress=True,
    )
    await send_weekly_digest(bot, chat_id, digest)


async def deliver_due_weekly_digests(bot, today: date | None = None) -> int:
    """Шлёт итог прошедшей недели тем, кому он ещё не уходил. Возвращает число чатов."""
    from asgiref.sync import sync_to_async

    today = today or vietnam_today()
    start, end = completed_week(today)
    users = await sync_to_async(list)(
        TelegramUser.objects.filter(is_active=True).select_related('user'),
    )
    sent = 0
    for telegram_user in users:
        if await sync_to_async(already_sent)(telegram_user, start):
            continue
        digest = await sync_to_async(build_weekly_digest)(
            telegram_user.user,
            start,
            end,
            today=today,
            in_progress=False,
        )
        try:
            await send_weekly_digest(bot, telegram_user.telegram_id, digest)
        except Exception:
            logger.exception(
                'Не удалось отправить недельную сводку user=%s',
                telegram_user.pk,
            )
            continue
        await sync_to_async(mark_sent)(telegram_user, start)
        sent += 1
    return sent


async def weekly_digest_loop(bot) -> None:
    """Раз в сутки в 09:00 по Вьетнаму проверяет, не пора ли прислать итог недели."""
    import asyncio

    await asyncio.sleep(20)
    while True:
        try:
            sent = await deliver_due_weekly_digests(bot)
            if sent:
                logger.info('Недельная сводка отправлена в %s чат(ов)', sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Проверка недельной сводки упала')
        await asyncio.sleep(seconds_until_next_send())


def _cashflow(user, start: date, end: date):
    base = Transaction.objects.filter(user=user, date__gte=start, date__lte=end)
    income = _sum_amount(base.filter(amount__gt=0))
    expenses = abs(_sum_amount(base.filter(amount__lt=0)))
    expense_rows, rest_count, rest_amount = _category_rows(
        base.filter(amount__lt=0),
        absolute=True,
    )
    income_rows, income_rest_count, income_rest_amount = _category_rows(
        base.filter(amount__gt=0),
        absolute=False,
    )
    if income_rest_count:
        income_rows = income_rows + (
            MoneyRow(label=f'Ещё {income_rest_count}', amount=income_rest_amount),
        )
    return income, expenses, expense_rows, income_rows, rest_count, rest_amount


def _sum_amount(queryset) -> Decimal:
    total = queryset.aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return Decimal(total or 0)


def _category_rows(queryset, *, absolute: bool):
    grouped = (
        queryset
        .values('category__name')
        .annotate(total=Coalesce(Sum('amount'), Decimal('0')))
        .order_by('total' if absolute else '-total')
    )
    rows: list[MoneyRow] = []
    rest_count = 0
    rest_amount = Decimal('0')
    for index, item in enumerate(grouped):
        amount = abs(Decimal(item['total'] or 0)) if absolute else Decimal(item['total'] or 0)
        label = item['category__name'] or 'Без категории'
        if index < _MAX_CATEGORY_ROWS:
            rows.append(MoneyRow(label=label, amount=amount))
        else:
            rest_count += 1
            rest_amount += amount
    return tuple(rows), rest_count, rest_amount


def _vietnam_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start, time.min, tzinfo=VIETNAM)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=VIETNAM)
    return start_dt, end_dt


def _goal_allocations(user, start: date, end: date) -> Decimal:
    start_dt, end_dt = _vietnam_bounds(start, end)
    total = GoalLedgerEntry.objects.filter(
        goal__user=user,
        occurred_at__gte=start_dt,
        occurred_at__lt=end_dt,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return Decimal(total or 0)


def _budget_rows(user, start: date, end: date) -> tuple[BudgetRow, ...]:
    budgets = (
        Budget.objects.filter(
            user=user,
            is_active=True,
            category__is_active=True,
            start_date__lte=end,
            end_date__gte=start,
        )
        .select_related('category')
        .order_by('category__name')
    )
    rows = []
    for budget in budgets:
        spent = Decimal(budget.spent_amount)
        limit = Decimal(budget.amount)
        rows.append(BudgetRow(
            category=budget.category.name,
            spent=spent,
            limit=limit,
            remaining=limit - spent,
        ))
    return tuple(rows)


def _goal_rows(user, today: date) -> tuple[GoalRow, ...]:
    goals = Goal.objects.filter(user=user, status=Goal.ACTIVE).order_by('title')
    month_free = _month_free_funds(user, today)
    rows = []
    for goal in goals[:_MAX_GOAL_ROWS]:
        balance = _goal_balance(goal)
        deposited = _month_deposits(goal, today)
        nets = _recent_complete_nets(goal, today)
        eta = build_goal_eta(
            today=today,
            target=Decimal(goal.target_amount),
            balance=balance,
            deadline=goal.deadline,
            monthly_nets=nets,
            deposited_this_month=deposited,
            free_funds=month_free,
        )
        rows.append(GoalRow(
            title=goal.title,
            balance=balance,
            target=Decimal(goal.target_amount),
            note=_goal_note(eta),
        ))
    return tuple(rows)


def _goal_note(eta) -> str:
    label = eta.as_dict().get('eta_label')
    if eta.status == 'reached':
        return 'собрана'
    if eta.status == 'overdue':
        return 'срок прошёл'
    if eta.status == 'on_track' and label:
        return f'успеваешь, ≈ {label}'
    if eta.status == 'behind' and label:
        return f'не успеваешь, ≈ {label}'
    if eta.status == 'no_deadline' and label:
        return f'без даты, ≈ {label}'
    if eta.status == 'no_deadline':
        return 'без даты'
    if eta.required_per_month is not None:
        return f'к сроку {format_rub(eta.required_per_month)}/мес'
    return 'темп пока неясен'


def _goal_balance(goal: Goal) -> Decimal:
    total = goal.entries.aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return max(Decimal(total or 0), Decimal('0'))


def _month_range(target: date) -> tuple[date, date]:
    start = date(target.year, target.month, 1)
    if target.month == 12:
        end = date(target.year + 1, 1, 1)
    else:
        end = date(target.year, target.month + 1, 1)
    return start, end


def _aware_month_bounds(target: date) -> tuple[datetime, datetime]:
    """Те же границы месяца, что у карточки цели: полночь TIME_ZONE."""
    start, end = _month_range(target)
    start_dt = timezone.make_aware(datetime(start.year, start.month, start.day))
    end_dt = timezone.make_aware(datetime(end.year, end.month, end.day))
    return start_dt, end_dt


def _month_deposits(goal: Goal, today: date) -> Decimal:
    start_dt, end_dt = _aware_month_bounds(today)
    total = goal.entries.filter(
        occurred_at__gte=start_dt,
        occurred_at__lt=end_dt,
        amount__gt=0,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return Decimal(total or 0)


def _month_net(goal: Goal, month: date) -> Decimal:
    start_dt, end_dt = _aware_month_bounds(month)
    total = goal.entries.filter(
        occurred_at__gte=start_dt,
        occurred_at__lt=end_dt,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return Decimal(total or 0)


def _recent_complete_nets(goal: Goal, today: date, limit: int = 3) -> list[Decimal]:
    created = timezone.localtime(goal.created_at).date()
    first_month = date(created.year, created.month, 1)
    cursor = date(today.year, today.month, 1)
    nets: list[Decimal] = []
    for _ in range(limit):
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
        if cursor < first_month:
            break
        nets.append(_month_net(goal, cursor))
    nets.reverse()
    return nets


def _month_free_funds(user, today: date) -> Decimal:
    start, end = _month_range(today)
    tx = Transaction.objects.filter(user=user, date__gte=start, date__lt=end)
    income = _sum_amount(tx.filter(amount__gt=0))
    expenses = abs(_sum_amount(tx.filter(amount__lt=0)))
    start_dt, end_dt = _aware_month_bounds(today)
    allocated = GoalLedgerEntry.objects.filter(
        goal__user=user,
        occurred_at__gte=start_dt,
        occurred_at__lt=end_dt,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return income - expenses - Decimal(allocated or 0)


def _rich_table(caption: str, headers: tuple[str, ...], rows) -> str:
    head = ''.join(
        f'<th align="{"left" if index == 0 else "right"}">{escape(header)}</th>'
        for index, header in enumerate(headers)
    )
    body = []
    for row in rows:
        emphasize = False
        texts = row
        if len(row) == len(headers) + 1 and isinstance(row[-1], bool):
            texts = row[:-1]
            emphasize = bool(row[-1])
        cells = []
        for index, text in enumerate(texts):
            align = 'left' if index == 0 else 'right'
            safe = escape(str(text))
            if emphasize:
                safe = f'<b>{safe}</b>'
            cells.append(f'<td align="{align}">{safe}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')
    return (
        '<table bordered striped>\n'
        f'<caption>{escape(caption)}</caption>\n'
        f'<tr>{head}</tr>\n'
        + '\n'.join(body)
        + '\n</table>'
    )
