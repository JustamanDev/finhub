"""Create / deposit / withdraw goals for voice MANAGE_GOAL."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from goals.models import Goal, GoalLedgerEntry
from telegram_bot.services.goal_service import GoalService

logger = logging.getLogger(__name__)

GOAL_ACTION_DEPOSIT = 'deposit'
GOAL_ACTION_WITHDRAW = 'withdraw'
GOAL_ACTION_CREATE = 'create'
VALID_GOAL_ACTIONS = {
    GOAL_ACTION_DEPOSIT,
    GOAL_ACTION_WITHDRAW,
    GOAL_ACTION_CREATE,
}


@dataclass
class GoalActionResult:
    goal: Goal
    action: str
    entry: GoalLedgerEntry | None = None
    balance: Decimal | None = None


async def execute_goal_create(
    user: User,
    title: str,
    target_amount: Decimal,
) -> GoalActionResult:
    title = (title or '').strip()
    if not title:
        raise ValueError('Укажите название цели.')
    amount = Decimal(str(target_amount)).copy_abs()
    if amount <= 0:
        raise ValueError('Целевая сумма должна быть больше нуля.')

    existing = await Goal.objects.filter(
        user=user,
        title__iexact=title,
        status=Goal.ACTIVE,
    ).afirst()
    if existing:
        raise ValueError(f'Цель «{existing.title}» уже существует.')

    goal = await GoalService(user).create_goal(title, amount)
    return GoalActionResult(goal=goal, action=GOAL_ACTION_CREATE)


async def execute_goal_deposit(
    user: User,
    goal: Goal,
    amount: Decimal,
) -> GoalActionResult:
    amount = Decimal(str(amount)).copy_abs()
    if amount <= 0:
        raise ValueError('Сумма пополнения должна быть больше нуля.')
    service = GoalService(user)
    entry = await service.add_deposit(goal.id, amount)
    if entry is None:
        raise ValueError('Цель не найдена.')
    balance = await service.get_goal_balance(goal.id)
    return GoalActionResult(
        goal=goal,
        action=GOAL_ACTION_DEPOSIT,
        entry=entry,
        balance=balance,
    )


async def execute_goal_withdraw(
    user: User,
    goal: Goal,
    amount: Decimal,
) -> GoalActionResult:
    amount = Decimal(str(amount)).copy_abs()
    if amount <= 0:
        raise ValueError('Сумма снятия должна быть больше нуля.')
    service = GoalService(user)
    balance = await service.get_goal_balance(goal.id)
    if amount > balance:
        raise ValueError(
            f'Недостаточно средств на цели (доступно {balance:,.0f}₽).',
        )
    entry = await service.add_withdraw(goal.id, amount)
    if entry is None:
        raise ValueError('Цель не найдена.')
    new_balance = await service.get_goal_balance(goal.id)
    return GoalActionResult(
        goal=goal,
        action=GOAL_ACTION_WITHDRAW,
        entry=entry,
        balance=new_balance,
    )


async def list_active_goals_async(user: User) -> list[Goal]:
    return await sync_to_async(list)(
        Goal.objects.filter(user=user, status=Goal.ACTIVE).order_by('-created_at'),
    )
