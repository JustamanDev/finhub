"""Утренние напоминания по целям. Суммы не двигает."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.db.models import Sum
from django.db.models.functions import Coalesce

from goals.ledger import ledger_totals
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.models import TelegramUser, UserState
from telegram_bot.services.goal_eta import build_goal_eta
from telegram_bot.services.weekly_digest import VIETNAM, format_rub, vietnam_today

logger = logging.getLogger(__name__)

MARKERS_KEY = 'goal_watch_markers'
WEEK_WINDOW = 7
LATE_WINDOW = 7
PACE_FROM_DAY = 20
MAX_PER_MORNING = 3
_MARKER_KEEP = 80


def _days_phrase(days: int) -> str:
    number = abs(days)
    tail = number % 100
    if 11 <= tail <= 14:
        word = 'дней'
    elif number % 10 == 1:
        word = 'день'
    elif number % 10 in (2, 3, 4):
        word = 'дня'
    else:
        word = 'дней'
    return f'{number} {word}'


def _deposited_this_month(goal: Goal, today: date) -> Decimal:
    start = datetime(today.year, today.month, 1, tzinfo=VIETNAM)
    if today.month == 12:
        end = datetime(today.year + 1, 1, 1, tzinfo=VIETNAM)
    else:
        end = datetime(today.year, today.month + 1, 1, tzinfo=VIETNAM)
    total = GoalLedgerEntry.objects.filter(
        goal=goal,
        entry_type=GoalLedgerEntry.DEPOSIT,
        occurred_at__gte=start,
        occurred_at__lt=end,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    return Decimal(total or 0)


def _notice(goal: Goal, today: date) -> tuple[str, str] | None:
    deadline = goal.deadline
    if deadline is None:
        return None
    totals = ledger_totals(goal.pk)
    target = Decimal(goal.target_amount or 0)
    if target <= 0:
        return None
    deposited = _deposited_this_month(goal, today)
    eta = build_goal_eta(
        today=today,
        target=target,
        balance=totals.committed,
        deadline=deadline,
        monthly_nets=[],
        deposited_this_month=deposited,
        free_funds=Decimal('0'),
    )
    if eta.remaining <= 0:
        return None
    days_left = (deadline - today).days
    when = deadline.strftime('%d.%m.%Y')
    left = format_rub(eta.remaining, goal.currency)
    if days_left == 0:
        kind = 'day'
        body = f'Срок сегодня, {when}. Осталось {left}.'
    elif 1 <= days_left <= WEEK_WINDOW:
        kind = 'week'
        body = f'До срока {_days_phrase(days_left)}, {when}. Осталось {left}.'
    elif -LATE_WINDOW <= days_left <= -1:
        kind = 'late'
        body = f'Срок был {when}. Осталось {left}.'
    elif (
        days_left > WEEK_WINDOW
        and today.day >= PACE_FROM_DAY
        and eta.still_needed_this_month
        and eta.still_needed_this_month > 0
    ):
        kind = 'pace'
        gap = format_rub(eta.still_needed_this_month, goal.currency)
        body = f'В этом месяце до темпа не хватает {gap}. Срок {when}.'
    else:
        return None
    marker = (
        f'{kind}:{goal.pk}:{today:%Y-%m}'
        if kind == 'pace'
        else f'{kind}:{goal.pk}:{deadline.isoformat()}'
    )
    text = f'🎯 {goal.title}\n{body}\nОтложить можно в карточке цели.'
    return marker, text


def _saved_markers(telegram_user: TelegramUser) -> set[str]:
    state = UserState.objects.filter(telegram_user=telegram_user).first()
    if state is None:
        return set()
    raw = (state.context_data or {}).get(MARKERS_KEY) or []
    if not isinstance(raw, list):
        return set()
    return {item for item in raw if isinstance(item, str)}


def collect_goal_watches(
    telegram_user: TelegramUser,
    today: date | None = None,
) -> list[tuple[str, str]]:
    """До трёх ещё не отправленных напоминаний, ближайший срок первым."""
    moment = today or vietnam_today()
    seen = _saved_markers(telegram_user)
    goals = Goal.objects.filter(
        user=telegram_user.user,
        kind=Goal.SAVINGS,
        status=Goal.ACTIVE,
        deadline__isnull=False,
    ).order_by('deadline', 'id')
    notices: list[tuple[str, str]] = []
    for goal in goals:
        notice = _notice(goal, moment)
        if notice is None or notice[0] in seen:
            continue
        notices.append(notice)
        if len(notices) >= MAX_PER_MORNING:
            break
    return notices


def remember_goal_watch(telegram_user: TelegramUser, marker: str) -> None:
    state, _created = UserState.objects.get_or_create(telegram_user=telegram_user)
    data = dict(state.context_data or {})
    raw = data.get(MARKERS_KEY) or []
    markers = [item for item in raw if isinstance(item, str)] if isinstance(raw, list) else []
    if marker not in markers:
        markers.append(marker)
    data[MARKERS_KEY] = markers[-_MARKER_KEEP:]
    state.context_data = data
    state.save(update_fields=['context_data', 'updated_at'])


def forget_goal_watch(telegram_user: TelegramUser, marker: str) -> None:
    state = UserState.objects.filter(telegram_user=telegram_user).first()
    if state is None:
        return
    data = dict(state.context_data or {})
    raw = data.get(MARKERS_KEY) or []
    if not isinstance(raw, list):
        return
    data[MARKERS_KEY] = [item for item in raw if item != marker]
    state.context_data = data
    state.save(update_fields=['context_data', 'updated_at'])


async def deliver_goal_watches(bot) -> int:
    """Одно и то же напоминание не повторяется, пока не сменится срок или месяц."""
    today = vietnam_today()
    users = await sync_to_async(list)(
        TelegramUser.objects.select_related('user').all(),
    )
    sent = 0
    for telegram_user in users:
        notices = await sync_to_async(collect_goal_watches)(telegram_user, today)
        for marker, text in notices:
            try:
                await bot.send_message(chat_id=telegram_user.telegram_id, text=text)
            except Exception:
                logger.exception(
                    'Не удалось напомнить про цель user=%s marker=%s',
                    telegram_user.pk,
                    marker,
                )
                continue
            await sync_to_async(remember_goal_watch)(telegram_user, marker)
            sent += 1
    return sent


async def goal_watch_loop(bot) -> None:
    """Тот же час, что у сводки и повторов: 09:00 по Вьетнаму."""
    import asyncio

    from telegram_bot.services.weekly_digest import seconds_until_next_send

    await asyncio.sleep(30)
    while True:
        try:
            sent = await deliver_goal_watches(bot)
            if sent:
                logger.info('Напоминаний по целям: %s', sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Проверка целей упала')
        await asyncio.sleep(seconds_until_next_send())
