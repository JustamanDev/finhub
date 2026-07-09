"""Create/update monthly budgets for voice SET_BUDGET."""

from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from budgets.models import Budget
from categories.models import Category

logger = logging.getLogger(__name__)


@dataclass
class BudgetUpsertResult:
    budget: Budget
    created: bool
    previous_amount: Decimal | None = None


def current_month_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = date(today.year, today.month, 1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = date(today.year, today.month, last_day)
    return start, end


def find_current_month_budget(
    user: User,
    category: Category,
    today: date | None = None,
) -> Budget | None:
    start, end = current_month_bounds(today)
    return (
        Budget.objects.filter(
            user=user,
            category=category,
            start_date=start,
            end_date=end,
            is_active=True,
        )
        .order_by('-id')
        .first()
    )


def upsert_monthly_budget(
    user: User,
    category: Category,
    amount: Decimal,
    today: date | None = None,
) -> BudgetUpsertResult:
    """Create or update active monthly budget for the current calendar month."""
    if category.type != 'expense':
        raise ValueError('Бюджет можно задать только для категории расходов.')

    amount = Decimal(str(amount)).copy_abs()
    if amount <= 0:
        raise ValueError('Сумма бюджета должна быть больше нуля.')

    start, end = current_month_bounds(today)
    existing = find_current_month_budget(user, category, today)
    if existing:
        previous = existing.amount
        existing.amount = amount
        existing.save(update_fields=['amount', 'updated_at'])
        return BudgetUpsertResult(
            budget=existing,
            created=False,
            previous_amount=previous,
        )

    budget = Budget.objects.create(
        user=user,
        category=category,
        amount=amount,
        period_type=Budget.MONTHLY,
        start_date=start,
        end_date=end,
        is_active=True,
    )
    return BudgetUpsertResult(budget=budget, created=True)


async def upsert_monthly_budget_async(
    user: User,
    category: Category,
    amount: Decimal,
) -> BudgetUpsertResult:
    return await sync_to_async(upsert_monthly_budget)(user, category, amount)


async def find_current_month_budget_async(
    user: User,
    category: Category,
) -> Budget | None:
    return await sync_to_async(find_current_month_budget)(user, category)
