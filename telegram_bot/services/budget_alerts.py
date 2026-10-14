"""Уведомление, когда траты впервые переходят лимит.

Повторная трата в уже превышенном периоде молчит: сообщение только
на переходе «ещё влезало» → «уже больше плана».
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User

from budgets.models import Budget
from categories.models import Category

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BudgetBreach:
    category_icon: str
    category_name: str
    limit: Decimal
    spent: Decimal


def format_breach(breach: BudgetBreach) -> str:
    over = breach.spent - breach.limit
    return (
        f'⚠️ Лимит превышен: {breach.category_icon} {breach.category_name}\n'
        f'План {breach.limit:,.0f} ₽, факт {breach.spent:,.0f} ₽, '
        f'сверх лимита {over:,.0f} ₽.'
    )


def breaches_of(transaction) -> list[BudgetBreach]:
    found = getattr(transaction, '_budget_breaches', None)
    return list(found or [])


def snapshot_spent(user: User, category: Category, on_date: date) -> dict[int, Decimal]:
    """Сколько уже списано по каждому живому лимиту, который покрывает дату."""
    if category.type != 'expense' or not category.is_active:
        return {}
    return {
        budget.id: budget.spent_amount
        for budget in _covering(user, category, on_date)
    }


def breaches_after_spend(
    user: User,
    category: Category,
    on_date: date,
    before: dict[int, Decimal],
) -> list[BudgetBreach]:
    """Лимиты, которые эта трата перевела через план."""
    if category.type != 'expense' or not category.is_active:
        return []
    found: list[BudgetBreach] = []
    for budget in _covering(user, category, on_date):
        limit = Decimal(budget.amount)
        was = before.get(budget.id, Decimal('0'))
        now = budget.spent_amount
        if was <= limit < now:
            found.append(_breach(budget, now))
    return found


def breach_after_limit_change(
    budget: Budget,
    previous_limit: Decimal | None,
) -> BudgetBreach | None:
    """Лимит опустили ниже уже потраченного или новый лимит сразу меньше факта."""
    category = budget.category
    if (
        not budget.is_active
        or category.type != 'expense'
        or not category.is_active
    ):
        return None
    spent = budget.spent_amount
    new_limit = Decimal(budget.amount)
    if spent <= new_limit:
        return None
    if previous_limit is not None and spent > Decimal(previous_limit):
        return None
    return _breach(budget, spent)


async def send_budget_breaches(bot, chat_id: int, breaches: list[BudgetBreach]) -> None:
    """Отдельное сообщение с выходом в бюджеты. Ошибка отправки не роняет запись."""
    if not breaches:
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text='📋 Бюджеты',
                callback_data='show_budgets',
            ),
        ],
        [
            InlineKeyboardButton(
                text='🏠 Главное меню',
                callback_data='main_menu',
            ),
        ],
    ])
    try:
        await bot.send_message(
            chat_id=chat_id,
            text='\n\n'.join(format_breach(item) for item in breaches),
            reply_markup=keyboard,
        )
    except Exception:
        logger.exception('Не удалось отправить уведомление о лимите')


def _covering(user: User, category: Category, on_date: date):
    return Budget.objects.filter(
        user=user,
        category=category,
        is_active=True,
        start_date__lte=on_date,
        end_date__gte=on_date,
    ).select_related('category')


def _breach(budget: Budget, spent: Decimal) -> BudgetBreach:
    return BudgetBreach(
        category_icon=budget.category.icon,
        category_name=budget.category.name,
        limit=Decimal(budget.amount),
        spent=spent,
    )
