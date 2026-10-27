"""Excel-отчёты для Telegram: файл месяца и файл года."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone

from budgets.models import Budget
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.services.report_figures import (
    BudgetSnap,
    GoalSnap,
    LedgerTx,
    Tx,
    build_month_report,
    build_year_report,
    month_bounds,
    period_caption,
    previous_month,
    year_caption,
)
from telegram_bot.services.report_workbook import render_month_workbook, render_year_workbook
from telegram_bot.services.weekly_digest import vietnam_today
from transactions.currencies import RUB, base_for_user, reports_phrase, symbol_of
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class ExcelExportResult:
    def __init__(self, filename: str, content: bytes, caption: str):
        self.filename = filename
        self.content = content
        self.caption = caption


class ReportExportService:
    """Собирает операции, резерв и лимиты и отдаёт готовую книгу."""

    def __init__(self, user: User):
        self.user = user

    async def build_monthly_excel(
        self,
        year: int,
        month: int,
        today: date | None = None,
    ) -> ExcelExportResult:
        today = today or vietnam_today()
        prev_year, prev_month = previous_month(year, month)
        start, _ = month_bounds(prev_year, prev_month)
        _, end = month_bounds(year, month)
        source = await self._load(start, end)
        report = build_month_report(
            year=year,
            month=month,
            today=today,
            unit=source.unit,
            currency_phrase=source.currency_phrase,
            generated_label=source.generated_label,
            transactions=source.transactions,
            ledger=source.ledger,
            goals=source.goals,
            budgets=source.budgets,
        )
        recurring_rows, debt_rows = await sync_to_async(self._side_rows)(today)
        return ExcelExportResult(
            filename=f'finhub_{year}-{month:02d}.xlsx',
            content=render_month_workbook(report, recurring_rows, debt_rows),
            caption=period_caption(year, month),
        )

    async def build_yearly_excel(
        self,
        year: int,
        today: date | None = None,
    ) -> ExcelExportResult:
        today = today or vietnam_today()
        start = date(year - 1, 12, 1)
        end = date(year + 1, 1, 1)
        source = await self._load(start, end)
        report = build_year_report(
            year=year,
            today=today,
            unit=source.unit,
            currency_phrase=source.currency_phrase,
            generated_label=source.generated_label,
            transactions=source.transactions,
            ledger=source.ledger,
            goals=source.goals,
            budgets=source.budgets,
        )
        recurring_rows, debt_rows = await sync_to_async(self._side_rows)(today)
        return ExcelExportResult(
            filename=f'finhub_{year}.xlsx',
            content=render_year_workbook(report, recurring_rows, debt_rows),
            caption=year_caption(year),
        )

    def _side_rows(self, today: date) -> tuple[tuple[str, ...], tuple[str, ...]]:
        from debts.ledger import obligation_lines
        from recurring.rhythm import expectation_lines

        return (
            tuple(expectation_lines(self.user, today)),
            tuple(obligation_lines(self.user)),
        )

    async def _load(self, start: date, end: date) -> '_Source':
        user = self.user

        def _fetch() -> '_Source':
            transactions = list(
                Transaction.objects.filter(
                    user=user,
                    date__gte=start,
                    date__lt=end,
                ).select_related('category').order_by('date', 'id')
            )
            entries = list(
                GoalLedgerEntry.objects.filter(
                    goal__user=user,
                    occurred_at__lt=_aware(end),
                ).select_related('goal').order_by('occurred_at', 'id')
            )
            goals = list(Goal.objects.filter(user=user))
            budgets = list(
                Budget.objects.filter(
                    user=user,
                    period_type=Budget.MONTHLY,
                ).select_related('category')
            )
            currency = base_for_user(user)
            return _Source(
                unit=symbol_of(currency),
                currency_phrase=reports_phrase(currency),
                generated_label=timezone.localtime().strftime('%d.%m.%Y %H:%M'),
                transactions=[_tx(item) for item in transactions],
                ledger=[_entry(item) for item in entries],
                goals=[_goal(item) for item in goals],
                budgets=[_budget(item) for item in budgets],
            )

        return await sync_to_async(_fetch, thread_sensitive=True)()


class _Source:
    def __init__(
        self,
        *,
        unit: str,
        currency_phrase: str,
        generated_label: str,
        transactions: list[Tx],
        ledger: list[LedgerTx],
        goals: list[GoalSnap],
        budgets: list[BudgetSnap],
    ):
        self.unit = unit
        self.currency_phrase = currency_phrase
        self.generated_label = generated_label
        self.transactions = transactions
        self.ledger = ledger
        self.goals = goals
        self.budgets = budgets


def _tx(item: Transaction) -> Tx:
    amount = Decimal(item.amount)
    original = item.original_amount
    return Tx(
        id=item.id,
        day=item.date,
        amount=amount,
        category_id=item.category_id,
        label=_label(item.category.icon, item.category.name),
        description=item.description or '',
        currency=item.currency or RUB,
        original_amount=Decimal(original) if original is not None else amount,
    )


def _entry(item: GoalLedgerEntry) -> LedgerTx:
    occurred = item.occurred_at
    if timezone.is_aware(occurred):
        occurred = timezone.localtime(occurred)
    return LedgerTx(
        day=occurred.date(),
        goal_id=item.goal_id,
        title=item.goal.title,
        is_envelope=item.goal.is_envelope,
        entry_type=item.entry_type,
        amount=Decimal(item.amount),
        comment=item.comment or '',
    )


def _goal(item: Goal) -> GoalSnap:
    return GoalSnap(
        id=item.id,
        title=item.title,
        is_envelope=item.is_envelope,
        status=item.status,
        target_amount=Decimal(item.target_amount) if item.target_amount is not None else None,
        deadline=item.deadline,
    )


def _budget(item: Budget) -> BudgetSnap:
    return BudgetSnap(
        category_id=item.category_id,
        label=_label(item.category.icon, item.category.name),
        amount=Decimal(item.amount),
        start=item.start_date,
        end=item.end_date,
        is_active=item.is_active,
    )


def _label(icon: str | None, name: str | None) -> str:
    return f'{(icon or "").strip()} {(name or "").strip()}'.strip()


def _aware(day: date) -> datetime:
    return timezone.make_aware(datetime(day.year, day.month, day.day))
