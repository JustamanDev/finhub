"""Архив категории: меню прячет, отчёт хранит суммы."""

from datetime import date, timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget
from categories.models import Category
from telegram_bot.handlers.report_handler import ReportHandler
from telegram_bot.services.category_management_service import CategoryManagementService
from telegram_bot.services.report_service import ReportService
from telegram_bot.voice.category_resolver import CategoryResolver, ResolveStatus
from transactions.models import Transaction


class CategoryArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='archive-user', password='x')
        self.today = timezone.localdate()
        self.month_start = self.today.replace(day=1)
        if self.today.month == 12:
            next_month = date(self.today.year + 1, 1, 1)
        else:
            next_month = date(self.today.year, self.today.month + 1, 1)
        self.month_end = next_month - timedelta(days=1)
        self.food = Category.objects.create(
            user=self.user,
            name='Кафе',
            type=Category.EXPENSE,
            icon='☕',
        )
        self.empty = Category.objects.create(
            user=self.user,
            name='Старый абонемент',
            type=Category.EXPENSE,
            icon='🎟️',
        )
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('-1800'),
            date=self.today,
        )
        self.current_budget = Budget.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('5000'),
            period_type=Budget.MONTHLY,
            start_date=self.month_start,
            end_date=self.month_end,
            is_active=True,
        )
        self.past_budget = Budget.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('4000'),
            period_type=Budget.MONTHLY,
            start_date=self.month_start - timedelta(days=32),
            end_date=self.month_start - timedelta(days=1),
            is_active=True,
        )
        self.service = CategoryManagementService(self.user)

    def test_archive_hides_category_and_keeps_transactions(self):
        archived = async_to_sync(self.service.archive_category)(self.food.id)
        self.assertFalse(archived.is_active)
        self.assertEqual(
            Transaction.objects.filter(category=self.food).count(),
            1,
        )
        visible = async_to_sync(self.service.get_user_categories)()
        self.assertNotIn(self.food.id, [item.id for item in visible])
        hidden = async_to_sync(self.service.get_archived_categories)()
        self.assertIn(self.food.id, [item.id for item in hidden])

        self.current_budget.refresh_from_db()
        self.past_budget.refresh_from_db()
        self.assertFalse(self.current_budget.is_active)
        self.assertTrue(self.past_budget.is_active)

        result = CategoryResolver(self.user).resolve('Кафе', 'expense')
        self.assertEqual(result.status, ResolveStatus.UNKNOWN)

    def test_report_shows_archived_spend_and_skips_empty_archive(self):
        async_to_sync(self.service.archive_category)(self.food.id)
        async_to_sync(self.service.archive_category)(self.empty.id)
        report = async_to_sync(ReportService(self.user).get_monthly_report)(
            self.today.year,
            self.today.month,
        )
        text = ReportHandler()._format_report_message(report)
        self.assertIn('Кафе', text)
        self.assertIn('1,800', text)
        self.assertNotIn('Старый абонемент', text)
        self.assertEqual(report['total_expenses'], Decimal('1800'))

    def test_restore_and_recreate_by_same_name(self):
        async_to_sync(self.service.archive_category)(self.food.id)
        restored = async_to_sync(self.service.restore_category)(self.food.id)
        self.assertTrue(restored.is_active)
        self.current_budget.refresh_from_db()
        self.assertTrue(self.current_budget.is_active)

        async_to_sync(self.service.archive_category)(self.food.id)
        revived = async_to_sync(self.service.create_category)(
            'Кафе',
            Category.EXPENSE,
            icon='🥐',
        )
        self.assertEqual(revived.id, self.food.id)
        self.assertTrue(revived.is_active)
        self.assertEqual(revived.icon, '🥐')
        self.assertEqual(Transaction.objects.filter(category_id=revived.id).count(), 1)
