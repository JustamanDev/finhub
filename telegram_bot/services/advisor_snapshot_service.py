"""Build a grounded financial snapshot for ASK_ADVISOR (no LLM inventing numbers)."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone

from budgets.models import Budget
from telegram_bot.services.goal_service import GoalService
from telegram_bot.services.report_service import ReportService
from telegram_bot.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


def _money(value: Decimal | int | float | None) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal('0.01')))


class AdvisorSnapshotService:
    def __init__(self, user: User) -> None:
        self.user = user

    async def build(self, today: date | None = None) -> dict[str, Any]:
        today = today or timezone.localdate()
        year, month = today.year, today.month

        report = await ReportService(self.user).get_monthly_report(year, month)
        goal_service = GoalService(self.user)
        free_funds = await goal_service.get_free_funds_for_month(
            date(year, month, 1),
        )
        today_stats = await TransactionService(self.user).get_today_statistics()

        expense_categories: list[dict[str, Any]] = []
        income_categories: list[dict[str, Any]] = []
        for name, stat in (report.get('categories') or {}).items():
            expense = _money(stat.get('expense'))
            income = _money(stat.get('income'))
            count = int(stat.get('transaction_count') or 0)
            if expense > 0 or (stat.get('category') and getattr(
                stat['category'], 'type', None,
            ) == 'expense' and count):
                row = {
                    'name': name,
                    'spent': expense,
                    'transactions': count,
                    'budget_remaining': _money(stat.get('balance')),
                }
                if expense > 0 or row['budget_remaining'] != 0:
                    expense_categories.append(row)
            if income > 0:
                income_categories.append({
                    'name': name,
                    'received': income,
                    'transactions': count,
                })

        expense_categories.sort(key=lambda r: r['spent'], reverse=True)
        income_categories.sort(key=lambda r: r['received'], reverse=True)

        budgets = await self._active_month_budgets(today)
        goals = await self._goals_summary(goal_service)
        recommendations = await goal_service.get_budget_underuse_recommendations(
            today=today,
        )

        return {
            'as_of': today.isoformat(),
            'period': {
                'year': year,
                'month': month,
                'name': report.get('period_name') or f'{month}.{year}',
            },
            'month_totals': {
                'income': _money(report.get('total_income')),
                'expenses': _money(report.get('total_expenses')),
                'balance': _money(report.get('balance')),
                'free_funds': _money(free_funds),
            },
            'today': {
                'income': _money(today_stats.get('income')),
                'expenses': _money(today_stats.get('expenses')),
                'balance': _money(today_stats.get('balance')),
            },
            'top_expense_categories': expense_categories[:8],
            'top_income_categories': income_categories[:5],
            'budgets': budgets,
            'goals': goals,
            'suggestions': [
                {
                    'title': rec.title,
                    'description': rec.description,
                    'suggested_amount': _money(rec.suggested_amount),
                }
                for rec in recommendations[:5]
            ],
        }

    async def _active_month_budgets(self, today: date) -> list[dict[str, Any]]:
        start = date(today.year, today.month, 1)
        budgets = await sync_to_async(list)(
            Budget.objects.filter(
                user=self.user,
                is_active=True,
                start_date=start,
            ).select_related('category'),
        )
        rows: list[dict[str, Any]] = []
        for budget in budgets:
            spent = await sync_to_async(lambda b: b.spent_amount)(budget)
            remaining = await sync_to_async(lambda b: b.remaining_amount)(budget)
            pct = await sync_to_async(lambda b: b.spent_percentage)(budget)
            overspent = await sync_to_async(lambda b: b.is_overspent)(budget)
            rows.append({
                'category': budget.category.name,
                'limit': _money(budget.amount),
                'spent': _money(spent),
                'remaining': _money(remaining),
                'spent_percent': float(pct),
                'overspent': bool(overspent),
            })
        rows.sort(key=lambda r: r['spent_percent'], reverse=True)
        return rows

    async def _goals_summary(self, goal_service: GoalService) -> list[dict[str, Any]]:
        goals = await goal_service.list_goals()
        rows: list[dict[str, Any]] = []
        for goal in goals:
            if goal.status != goal.ACTIVE:
                continue
            balance = await goal_service.get_goal_balance(goal.id)
            target = Decimal(goal.target_amount)
            progress = float(
                (balance / target * 100).quantize(Decimal('0.1')),
            ) if target > 0 else 0.0
            rows.append({
                'title': goal.title,
                'target': _money(target),
                'balance': _money(max(balance, Decimal('0'))),
                'progress_percent': progress,
                'deadline': goal.deadline.isoformat() if goal.deadline else None,
            })
        return rows
