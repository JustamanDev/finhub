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


def _money_symbol(user) -> str:
    from transactions.currencies import base_for_user, symbol_of

    return symbol_of(base_for_user(user))


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
    sym = _money_symbol(entry.goal.user)
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

    need = abs(transaction.amount)
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
        sym = _money_symbol(user)
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
    available = goal_balance(entry.goal_id) + abs(entry.amount)
    if new_abs_amount > available:
        place = 'конверте' if entry.goal.is_envelope else 'цели'
        sym = _money_symbol(transaction.user)
        raise GoalSpendShortfall(
            f'На {place} «{entry.goal.title}» {available:,.0f} {sym}, '
            f'нужно {new_abs_amount:,.0f} {sym}.',
        )


def resize_linked_spend(transaction: Transaction) -> None:
    entry = _linked_spend(transaction.id)
    if entry is None:
        return
    entry.amount = -abs(transaction.amount)
    entry.save(update_fields=['amount', 'updated_at'])


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
