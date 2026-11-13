"""Списание расхода из цели одним шагом.

Расход остаётся в своей категории. На цели пишется такая же сумма
со знаком минус, поэтому «свободно» не уменьшается второй раз.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from goals.models import Goal, GoalLedgerEntry
from transactions.models import Transaction


class GoalSpendShortfall(Exception):
    """На выбранной цели не хватает на новую сумму расхода."""


@dataclass(frozen=True)
class GoalSpendResult:
    ok: bool
    message: str
    goal_title: str = ''
    remaining: Decimal = Decimal('0')


def list_goals_for_spend(user: User) -> list[tuple[Goal, Decimal]]:
    """Активные цели и сколько на каждой лежит сейчас."""
    goals = list(
        Goal.objects.filter(user=user, status=Goal.ACTIVE).order_by('title', 'id'),
    )
    return [(goal, goal_balance(goal.id)) for goal in goals]


def _money_symbol(goal: Goal) -> str:
    from transactions.currencies import RUB, symbol_of

    return symbol_of(goal.currency or RUB)


def _spend_parts(transaction: Transaction, goal: Goal) -> tuple[Decimal, Decimal, str]:
    """Сколько списать в валюте цели и сколько это в валюте отчёта."""
    from transactions.booking import book_positive
    from transactions.currencies import RUB, base_for_user, is_known

    base = base_for_user(transaction.user)
    source = transaction.report_currency if is_known(transaction.report_currency) else base
    native_code = goal.currency if is_known(goal.currency) else RUB
    booked = book_positive(abs(transaction.amount), source, native_code, base)
    return booked.native, booked.report, base


def goal_spend_note(transaction_id: int) -> str:
    """Строка для карточки, если расход уже списан с цели."""
    entry = (
        GoalLedgerEntry.objects.filter(
            linked_transaction_id=transaction_id,
            entry_type=GoalLedgerEntry.SPEND,
        )
        .select_related('goal')
        .order_by('-id')
        .first()
    )
    if entry is None:
        return ''
    remaining = goal_balance(entry.goal_id)
    sym = _money_symbol(entry.goal)
    if entry.goal.is_envelope:
        return (
            f'\nИз конверта «{entry.goal.title}». '
            f'На конверте осталось {remaining:,.0f} {sym}.'
        )
    return (
        f'\nИз цели «{entry.goal.title}». '
        f'На цели осталось {remaining:,.0f} {sym}.'
    )


def spend_expense_from_goal(
    user: User,
    transaction_id: int,
    goal_id: int,
) -> GoalSpendResult:
    """Списывает весь расход с цели. Прежняя привязка снимается только если новой цели хватает."""
    try:
        transaction = Transaction.objects.select_related('category').get(
            id=transaction_id,
            user=user,
        )
    except Transaction.DoesNotExist:
        return GoalSpendResult(False, 'Операция не найдена.')
    if transaction.amount >= 0:
        return GoalSpendResult(False, 'Из цели можно списать только расход.')
    try:
        goal = Goal.objects.get(id=goal_id, user=user, status=Goal.ACTIVE)
    except Goal.DoesNotExist:
        return GoalSpendResult(False, 'Цель не найдена.')

    need, report, base = _spend_parts(transaction, goal)
    existing = list(
        GoalLedgerEntry.objects.filter(
            linked_transaction=transaction,
            entry_type=GoalLedgerEntry.SPEND,
        ),
    )
    already_here = sum(
        (abs(entry.amount) for entry in existing if entry.goal_id == goal.id),
        Decimal('0'),
    )
    available = goal_balance(goal.id) + already_here
    if need > available:
        place = 'конверте' if goal.is_envelope else 'цели'
        sym = _money_symbol(goal)
        return GoalSpendResult(
            False,
            (
                f'На {place} «{goal.title}» {available:,.0f} {sym}, '
                f'для этой траты нужно {need:,.0f} {sym}.'
            ),
        )

    if existing:
        GoalLedgerEntry.objects.filter(pk__in=[entry.pk for entry in existing]).delete()
    GoalLedgerEntry.objects.create(
        goal=goal,
        amount=-need,
        report_amount=-report,
        report_currency=base,
        entry_type=GoalLedgerEntry.SPEND,
        occurred_at=noon_on(transaction.date),
        linked_transaction=transaction,
        comment=transaction.category.name,
    )
    return GoalSpendResult(
        True,
        '',
        goal_title=goal.title,
        remaining=goal_balance(goal.id),
    )


def ensure_spend_fits(transaction: Transaction, new_abs_amount: Decimal) -> None:
    """Не даёт увеличить расход выше того, что ещё есть на привязанной цели."""
    entry = _linked_spend(transaction.id)
    if entry is None:
        return
    held = transaction.amount
    transaction.amount = -abs(new_abs_amount)
    try:
        need, _, _ = _spend_parts(transaction, entry.goal)
    finally:
        transaction.amount = held
    available = goal_balance(entry.goal_id) + abs(entry.amount)
    if need > available:
        place = 'конверте' if entry.goal.is_envelope else 'цели'
        sym = _money_symbol(entry.goal)
        raise GoalSpendShortfall(
            f'На {place} «{entry.goal.title}» {available:,.0f} {sym}, '
            f'нужно {need:,.0f} {sym}.',
        )


def resize_linked_spend(transaction: Transaction) -> None:
    entry = _linked_spend(transaction.id)
    if entry is None:
        return
    native, report, base = _spend_parts(transaction, entry.goal)
    entry.amount = -native
    entry.report_amount = -report
    entry.report_currency = base
    entry.save(update_fields=['amount', 'report_amount', 'report_currency', 'updated_at'])


def move_linked_spend(transaction: Transaction) -> None:
    entry = _linked_spend(transaction.id)
    if entry is None:
        return
    entry.occurred_at = noon_on(transaction.date)
    entry.save(update_fields=['occurred_at', 'updated_at'])


def release_linked_spend(transaction_id: int) -> None:
    GoalLedgerEntry.objects.filter(
        linked_transaction_id=transaction_id,
        entry_type=GoalLedgerEntry.SPEND,
    ).delete()


def goal_balance(goal_id: int) -> Decimal:
    total = GoalLedgerEntry.objects.filter(goal_id=goal_id).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0')),
    )['total']
    return Decimal(total or 0)


def noon_on(day) -> datetime:
    moment = datetime.combine(day, time(12, 0))
    if timezone.is_naive(moment):
        return timezone.make_aware(moment)
    return moment


def _linked_spend(transaction_id: int) -> GoalLedgerEntry | None:
    return (
        GoalLedgerEntry.objects.filter(
            linked_transaction_id=transaction_id,
            entry_type=GoalLedgerEntry.SPEND,
        )
        .select_related('goal')
        .order_by('-id')
        .first()
    )
