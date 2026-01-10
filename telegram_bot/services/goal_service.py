import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from statistics import median
from typing import Optional

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone

from budgets.models import Budget
from goals.models import (
    Goal,
    GoalLedgerEntry,
)
from transactions.models import Transaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoalRecommendation:
    title: str
    description: str
    suggested_amount: Decimal


class GoalService:
    """
    Сервис целей (конвертов) для Telegram-бота.

    Принцип:
    - транзакции (income/expense) отражают фактические движения денег
    - цели — отдельный ledger (резервирование), который уменьшает "свободно" в месяце
    """

    def __init__(self, user: User):
        self.user = user

    # --- CRUD / ledger ---
    async def create_goal(
        self,
        title: str,
        target_amount: Decimal,
        deadline: Optional[date] = None,
    ) -> Goal:
        return await Goal.objects.acreate(
            user=self.user,
            title=title,
            target_amount=target_amount,
            deadline=deadline,
        )

    async def list_goals(self) -> list[Goal]:
        return await sync_to_async(list)(
            Goal.objects.filter(user=self.user).order_by('-created_at'),
        )

    async def get_goal(self, goal_id: int) -> Optional[Goal]:
        try:
            return await Goal.objects.aget(id=goal_id, user=self.user)
        except Goal.DoesNotExist:
            return None

    async def add_deposit(
        self,
        goal_id: int,
        amount: Decimal,
        comment: str = "",
    ) -> Optional[GoalLedgerEntry]:
        goal = await self.get_goal(goal_id)
        if not goal:
            return None
        return await GoalLedgerEntry.objects.acreate(
            goal=goal,
            amount=abs(amount),
            entry_type=GoalLedgerEntry.DEPOSIT,
            comment=comment,
        )

    async def add_withdraw(
        self,
        goal_id: int,
        amount: Decimal,
        comment: str = "",
    ) -> Optional[GoalLedgerEntry]:
        goal = await self.get_goal(goal_id)
        if not goal:
            return None
        return await GoalLedgerEntry.objects.acreate(
            goal=goal,
            amount=-abs(amount),
            entry_type=GoalLedgerEntry.WITHDRAW,
            comment=comment,
        )

    async def get_goal_balance(self, goal_id: int) -> Decimal:
        qs = GoalLedgerEntry.objects.filter(goal_id=goal_id, goal__user=self.user)
        total = await sync_to_async(
            lambda: qs.aggregate(total=Coalesce(models.Sum('amount'), Decimal('0')))['total'],
            thread_sensitive=True,
        )()
        return Decimal(total or 0)

    async def get_recent_entries(
        self,
        goal_id: int,
        limit: int = 15,
    ) -> list[GoalLedgerEntry]:
        return await sync_to_async(list)(
            GoalLedgerEntry.objects.filter(
                goal_id=goal_id,
                goal__user=self.user,
            )
            .order_by('-occurred_at', '-id')[:limit]
        )

    # --- Monthly metrics ---
    @staticmethod
    def _month_range(target: date) -> tuple[date, date]:
        start = date(target.year, target.month, 1)
        if target.month == 12:
            end = date(target.year + 1, 1, 1)
        else:
            end = date(target.year, target.month + 1, 1)
        return start, end

    @staticmethod
    def _months_inclusive(from_month: date, to_month: date) -> int:
        """Количество месяцев включительно между месяцами from_month и to_month (по month/year)."""
        return (to_month.year - from_month.year) * 12 + (to_month.month - from_month.month) + 1

    async def get_free_funds_for_month(self, month: date) -> Decimal:
        """
        Свободно для трат в месяце:
        Доходы - Расходы - (Отложено в цели за месяц)
        """
        start, end = self._month_range(month)

        tx_qs = Transaction.objects.filter(
            user=self.user,
            date__gte=start,
            date__lt=end,
        )

        income_total = await sync_to_async(
            lambda: tx_qs.filter(amount__gt=0).aggregate(
                total=Coalesce(models.Sum('amount'), Decimal('0')),
            )['total'],
            thread_sensitive=True,
        )()

        expense_total = await sync_to_async(
            lambda: tx_qs.filter(amount__lt=0).aggregate(
                total=Coalesce(models.Sum('amount'), Decimal('0')),
            )['total'],
            thread_sensitive=True,
        )()

        # expense_total negative; convert to positive expenses
        expenses_abs = abs(Decimal(expense_total or 0))

        start_dt = timezone.make_aware(datetime(start.year, start.month, start.day))
        end_dt = timezone.make_aware(datetime(end.year, end.month, end.day))
        entries_qs = GoalLedgerEntry.objects.filter(
            goal__user=self.user,
            occurred_at__gte=start_dt,
            occurred_at__lt=end_dt,
        )
        allocations_net = await sync_to_async(
            lambda: entries_qs.aggregate(total=Coalesce(models.Sum('amount'), Decimal('0')))['total'],
            thread_sensitive=True,
        )()

        free = Decimal(income_total or 0) - expenses_abs - Decimal(allocations_net or 0)
        return free

    async def get_goal_month_metrics(
        self,
        goal: Goal,
        month: date,
    ) -> dict:
        start, end = self._month_range(month)
        start_dt = timezone.make_aware(datetime(start.year, start.month, start.day))
        end_dt = timezone.make_aware(datetime(end.year, end.month, end.day))
        qs = GoalLedgerEntry.objects.filter(
            goal=goal,
            occurred_at__gte=start_dt,
            occurred_at__lt=end_dt,
        )
        deposits = await sync_to_async(
            lambda: qs.filter(amount__gt=0).aggregate(total=Coalesce(models.Sum('amount'), Decimal('0')))['total'],
            thread_sensitive=True,
        )()
        withdraws = await sync_to_async(
            lambda: qs.filter(amount__lt=0).aggregate(total=Coalesce(models.Sum('amount'), Decimal('0')))['total'],
            thread_sensitive=True,
        )()

        deposits = Decimal(deposits or 0)
        withdraws = Decimal(withdraws or 0)  # negative
        net = deposits + withdraws

        return {
            'deposits': deposits,
            'withdraws': withdraws,
            'net': net,
        }

    async def get_goal_card_data(
        self,
        goal_id: int,
        today: Optional[date] = None,
    ) -> Optional[dict]:
        goal = await self.get_goal(goal_id)
        if not goal:
            return None

        today = today or timezone.localdate()
        balance = await self.get_goal_balance(goal_id)
        balance = max(balance, Decimal('0'))

        target = Decimal(goal.target_amount)
        remaining_total = max(target - balance, Decimal('0'))
        progress_pct = Decimal('0')
        if target > 0:
            progress_pct = (balance / target) * Decimal('100')

        # План по месяцам
        months_remaining = None
        planned_per_month = None
        planned_this_month = None
        if goal.deadline and goal.deadline >= today:
            months_remaining = self._months_inclusive(today, goal.deadline)
            if months_remaining > 0:
                planned_per_month = (remaining_total / Decimal(months_remaining)).quantize(Decimal('0.01'))
                planned_this_month = planned_per_month

        month_metrics = await self.get_goal_month_metrics(goal, today)
        deposited_this_month = month_metrics['deposits']
        withdrawn_this_month = abs(month_metrics['withdraws'])

        remaining_this_month = None
        if planned_this_month is not None:
            remaining_this_month = max(planned_this_month - deposited_this_month, Decimal('0'))

        free_funds = await self.get_free_funds_for_month(today)

        recommendations = await self.get_budget_underuse_recommendations(today)

        return {
            'goal': goal,
            'balance': balance,
            'target': target,
            'remaining_total': remaining_total,
            'progress_pct': progress_pct,
            'months_remaining': months_remaining,
            'planned_per_month': planned_per_month,
            'planned_this_month': planned_this_month,
            'deposited_this_month': deposited_this_month,
            'withdrawn_this_month': withdrawn_this_month,
            'remaining_this_month': remaining_this_month,
            'free_funds_this_month': free_funds,
            'recommendations': recommendations,
        }

    # --- Recommendations (budget underuse) ---
    async def get_budget_underuse_recommendations(
        self,
        today: Optional[date] = None,
        months: int = 3,
        min_rubles: Decimal = Decimal('1000'),
        min_percent: Decimal = Decimal('0.05'),
    ) -> list[GoalRecommendation]:
        """
        Рекомендации на основе недоиспользования бюджетов.

        Ищем категории с месячными бюджетами, которые 3 месяца подряд
        недотрачивались (budget - spent) и дают устойчивый "резерв".
        """
        today = today or timezone.localdate()

        # берем предыдущие полные месяцы (исключаем текущий)
        cursor = date(today.year, today.month, 1)
        months_list: list[date] = []
        for _ in range(months):
            # previous month start
            if cursor.month == 1:
                cursor = date(cursor.year - 1, 12, 1)
            else:
                cursor = date(cursor.year, cursor.month - 1, 1)
            months_list.append(cursor)

        # Собираем бюджеты по этим месяцам
        budgets = await sync_to_async(list)(
            Budget.objects.filter(
                user=self.user,
                is_active=True,
                period_type=Budget.MONTHLY,
                start_date__in=months_list,
            ).select_related('category')
        )

        by_category: dict[int, list[Budget]] = {}
        for b in budgets:
            by_category.setdefault(b.category_id, []).append(b)

        results: list[GoalRecommendation] = []

        for _, items in by_category.items():
            # нужны бюджеты по всем месяцам
            if len(items) < months:
                continue

            # нормализуем по start_date
            items_by_start = {b.start_date: b for b in items}
            if any(m not in items_by_start for m in months_list):
                continue

            underuses: list[Decimal] = []
            budget_amounts: list[Decimal] = []
            for m in months_list:
                b = items_by_start[m]
                spent = await sync_to_async(lambda bb: bb.spent_amount)(b)
                budget_amount = Decimal(b.amount)
                budget_amounts.append(budget_amount)
                underuse = max(Decimal('0'), budget_amount - Decimal(spent))
                underuses.append(underuse)

            # устойчивость: все 3 месяца underuse > 0
            if any(u <= 0 for u in underuses):
                continue

            u_median = Decimal(str(median(underuses))).quantize(Decimal('0.01'))
            b_avg = (sum(budget_amounts, Decimal('0')) / Decimal(len(budget_amounts))).quantize(Decimal('0.01'))

            if u_median < min_rubles:
                continue
            if b_avg > 0 and (u_median / b_avg) < min_percent:
                continue

            category = items[0].category
            title = "Потенциальный резерв из бюджета"
            description = (
                f"В категории «{category.icon} {category.name}» "
                f"у вас 3 месяца подряд остаётся около {u_median:,.0f} ₽ "
                "от бюджета. Можно направить эту сумму в цели."
            )
            results.append(
                GoalRecommendation(
                    title=title,
                    description=description,
                    suggested_amount=u_median,
                )
            )

        # сортируем по величине резерва
        results.sort(key=lambda r: r.suggested_amount, reverse=True)
        return results[:3]

