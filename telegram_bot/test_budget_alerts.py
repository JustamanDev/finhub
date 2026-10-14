"""Уведомление один раз, когда траты переходят лимит."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget
from categories.models import Category
from telegram_bot.services.budget_alerts import (
    breach_after_limit_change,
    breaches_after_spend,
    snapshot_spent,
)
from telegram_bot.services.transaction_service import TransactionService
from transactions.models import Transaction


class BudgetAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alert-user', password='x')
        self.today = timezone.localdate()
        self.month_start = self.today.replace(day=1)
        if self.today.month == 12:
            next_month = date(self.today.year + 1, 1, 1)
        else:
            next_month = date(self.today.year, self.today.month + 1, 1)
        self.month_end = next_month - timedelta(days=1)
        self.food = Category.objects.create(
            user=self.user,
            name='Продукты',
            type=Category.EXPENSE,
            icon='🛒',
        )
        self.budget = Budget.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('1000'),
            period_type=Budget.MONTHLY,
            start_date=self.month_start,
            end_date=self.month_end,
        )

    def _spend(self, amount, on_date=None):
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal(amount),
            date=on_date or self.today,
        )

    def test_spend_under_the_limit_is_quiet(self):
        before = snapshot_spent(self.user, self.food, self.today)
        self._spend('-400')
        self.assertEqual(
            breaches_after_spend(self.user, self.food, self.today, before),
            [],
        )

    def test_crossing_the_limit_is_reported_once(self):
        self._spend('-700')
        before = snapshot_spent(self.user, self.food, self.today)
        self._spend('-400')
        breaches = breaches_after_spend(self.user, self.food, self.today, before)
        self.assertEqual(len(breaches), 1)
        self.assertEqual(breaches[0].spent, Decimal('1100'))
        self.assertEqual(breaches[0].limit, Decimal('1000'))
        self.assertIn('Продукты', breaches[0].category_name)

        again = snapshot_spent(self.user, self.food, self.today)
        self._spend('-50')
        self.assertEqual(
            breaches_after_spend(self.user, self.food, self.today, again),
            [],
        )

    def test_income_does_not_cross_a_limit(self):
        salary = Category.objects.create(
            user=self.user,
            name='Зарплата',
            type=Category.INCOME,
            icon='💰',
        )
        before = snapshot_spent(self.user, salary, self.today)
        Transaction.objects.create(
            user=self.user,
            category=salary,
            amount=Decimal('5000'),
            date=self.today,
        )
        self.assertEqual(
            breaches_after_spend(self.user, salary, self.today, before),
            [],
        )

    def test_spend_outside_the_period_is_quiet(self):
        outside = self.month_start - timedelta(days=1)
        before = snapshot_spent(self.user, self.food, outside)
        self._spend('-5000', on_date=outside)
        self.assertEqual(
            breaches_after_spend(self.user, self.food, outside, before),
            [],
        )

    def test_new_limit_below_money_already_spent_is_reported(self):
        self._spend('-1500')
        self.budget.amount = Decimal('1000')
        breach = breach_after_limit_change(self.budget, None)
        self.assertIsNotNone(breach)
        self.assertEqual(breach.spent, Decimal('1500'))

    def test_lowering_an_already_broken_limit_is_quiet(self):
        self._spend('-1500')
        self.budget.amount = Decimal('800')
        self.assertIsNone(
            breach_after_limit_change(self.budget, Decimal('1000')),
        )

    def test_lowering_a_limit_under_the_fact_is_reported(self):
        self._spend('-800')
        self.budget.amount = Decimal('500')
        breach = breach_after_limit_change(self.budget, Decimal('1000'))
        self.assertIsNotNone(breach)
        self.assertEqual(breach.limit, Decimal('500'))

    def test_inactive_budget_is_quiet(self):
        self.budget.is_active = False
        self.budget.save(update_fields=['is_active'])
        before = snapshot_spent(self.user, self.food, self.today)
        self._spend('-5000')
        self.assertEqual(
            breaches_after_spend(self.user, self.food, self.today, before),
            [],
        )

    async def test_service_marks_the_transaction_that_crossed(self):
        service = TransactionService(self.user)
        await service.create_transaction(
            amount=Decimal('700'),
            category=self.food,
            transaction_type='expense',
            transaction_date=self.today,
        )
        crossed = await service.create_transaction(
            amount=Decimal('400'),
            category=self.food,
            transaction_type='expense',
            transaction_date=self.today,
        )
        breaches = crossed._budget_breaches
        self.assertEqual(len(breaches), 1)
        self.assertEqual(breaches[0].spent, Decimal('1100'))
