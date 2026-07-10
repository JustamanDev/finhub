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
from telegram_bot.voice.period_parser import ParsedPeriod, parse_advisor_period

logger = logging.getLogger(__name__)


def _money(value: Decimal | int | float | None) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal('0.01')))


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


class AdvisorSnapshotService:
    def __init__(self, user: User) -> None:
        self.user = user

    async def build(
        self,
        today: date | None = None,
        *,
        period: ParsedPeriod | None = None,
        question: str | None = None,
    ) -> dict[str, Any]:
        today = today or timezone.localdate()
        if period is None:
            period = parse_advisor_period(question or '', today)

        year, month = period.year, period.month
        report = await ReportService(self.user).get_monthly_report(year, month)
        goal_service = GoalService(self.user)
        free_funds = await goal_service.get_free_funds_for_month(
            date(year, month, 1),
        )

        expense_categories, income_categories = self._split_category_stats(report)

        budgets = await self._month_budgets(year, month)
        goals = await self._goals_summary(goal_service)
        recommendations = await goal_service.get_budget_underuse_recommendations(
            today=today,
        )

        prev_year, prev_month = _prev_month(year, month)
        prev_report = await ReportService(self.user).get_monthly_report(
            prev_year,
            prev_month,
        )
        prev_free = await goal_service.get_free_funds_for_month(
            date(prev_year, prev_month, 1),
        )
        comparison = self._build_comparison(report, prev_report, free_funds, prev_free)

        snapshot: dict[str, Any] = {
            'as_of': today.isoformat(),
            'period': {
                'year': year,
                'month': month,
                'name': period.label or report.get('period_name') or f'{month}.{year}',
                'is_current': period.is_current,
            },
            'month_totals': {
                'income': _money(report.get('total_income')),
                'expenses': _money(report.get('total_expenses')),
                'balance': _money(report.get('balance')),
                'free_funds': _money(free_funds),
            },
            'previous_period': {
                'year': prev_year,
                'month': prev_month,
                'name': prev_report.get('period_name') or f'{prev_month}.{prev_year}',
                'income': _money(prev_report.get('total_income')),
                'expenses': _money(prev_report.get('total_expenses')),
                'balance': _money(prev_report.get('balance')),
                'free_funds': _money(prev_free),
            },
            'comparison_vs_previous': comparison,
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
            'monthly_series': None,
            'trend': None,
        }

        if period.trend_months:
            series = await self._build_monthly_series(
                year,
                month,
                period.trend_months,
            )
            snapshot['monthly_series'] = series
            snapshot['trend'] = self._summarize_trend(series)

        if period.is_current:
            today_stats = await TransactionService(self.user).get_today_statistics()
            snapshot['today'] = {
                'income': _money(today_stats.get('income')),
                'expenses': _money(today_stats.get('expenses')),
                'balance': _money(today_stats.get('balance')),
            }
        else:
            snapshot['today'] = None

        return snapshot

    def _split_category_stats(
        self,
        report: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        expense_categories: list[dict[str, Any]] = []
        income_categories: list[dict[str, Any]] = []
        for name, stat in (report.get('categories') or {}).items():
            expense = _money(stat.get('expense'))
            income = _money(stat.get('income'))
            count = int(stat.get('transaction_count') or 0)
            if expense > 0 or (
                stat.get('category')
                and getattr(stat['category'], 'type', None) == 'expense'
                and count
            ):
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
        return expense_categories, income_categories

    def _build_comparison(
        self,
        report: dict[str, Any],
        prev_report: dict[str, Any],
        free_funds: Decimal,
        prev_free: Decimal,
    ) -> dict[str, Any]:
        cur_exp = _money(report.get('total_expenses'))
        prev_exp = _money(prev_report.get('total_expenses'))
        cur_inc = _money(report.get('total_income'))
        prev_inc = _money(prev_report.get('total_income'))
        return {
            'expenses_delta': round(cur_exp - prev_exp, 2),
            'income_delta': round(cur_inc - prev_inc, 2),
            'balance_delta': round(
                _money(report.get('balance')) - _money(prev_report.get('balance')),
                2,
            ),
            'free_funds_delta': round(_money(free_funds) - _money(prev_free), 2),
            'expenses_changed_percent': (
                round((cur_exp - prev_exp) / prev_exp * 100, 1)
                if prev_exp
                else None
            ),
        }

    async def _build_monthly_series(
        self,
        end_year: int,
        end_month: int,
        months: int,
    ) -> list[dict[str, Any]]:
        """Oldest → newest series ending at (end_year, end_month)."""
        report_service = ReportService(self.user)
        points: list[tuple[int, int]] = []
        year, month = end_year, end_month
        for _ in range(months):
            points.append((year, month))
            year, month = _prev_month(year, month)
        points.reverse()

        series: list[dict[str, Any]] = []
        for year, month in points:
            report = await report_service.get_monthly_report(year, month)
            series.append({
                'year': year,
                'month': month,
                'name': report.get('period_name') or f'{month}.{year}',
                'income': _money(report.get('total_income')),
                'expenses': _money(report.get('total_expenses')),
                'balance': _money(report.get('balance')),
            })
        return series

    def _summarize_trend(self, series: list[dict[str, Any]]) -> dict[str, Any]:
        expenses = [float(row.get('expenses') or 0) for row in series]
        incomes = [float(row.get('income') or 0) for row in series]
        n = len(expenses)
        avg_expenses = round(sum(expenses) / n, 2) if n else 0.0
        avg_income = round(sum(incomes) / n, 2) if n else 0.0
        first_exp, last_exp = (expenses[0], expenses[-1]) if n else (0.0, 0.0)
        first_inc, last_inc = (incomes[0], incomes[-1]) if n else (0.0, 0.0)

        def _direction(first: float, last: float) -> str:
            if first == 0 and last == 0:
                return 'flat'
            if first == 0:
                return 'up' if last > 0 else 'flat'
            change = (last - first) / abs(first)
            if change > 0.05:
                return 'up'
            if change < -0.05:
                return 'down'
            return 'flat'

        peak_idx = max(range(n), key=lambda i: expenses[i]) if n else 0
        low_idx = min(range(n), key=lambda i: expenses[i]) if n else 0
        return {
            'months': n,
            'avg_expenses': avg_expenses,
            'avg_income': avg_income,
            'expenses_direction': _direction(first_exp, last_exp),
            'income_direction': _direction(first_inc, last_inc),
            'expenses_first_to_last_delta': round(last_exp - first_exp, 2),
            'expenses_first_to_last_percent': (
                round((last_exp - first_exp) / first_exp * 100, 1)
                if first_exp
                else None
            ),
            'peak_expenses_month': series[peak_idx]['name'] if n else None,
            'peak_expenses': expenses[peak_idx] if n else 0.0,
            'lowest_expenses_month': series[low_idx]['name'] if n else None,
            'lowest_expenses': expenses[low_idx] if n else 0.0,
        }

    async def _month_budgets(self, year: int, month: int) -> list[dict[str, Any]]:
        start = date(year, month, 1)
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
