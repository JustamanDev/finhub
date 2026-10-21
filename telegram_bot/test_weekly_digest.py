"""Недельная сводка: границы недели, суммы и HTML-статья."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget
from categories.models import Category
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.models import TelegramUser
from transactions.models import Transaction
from telegram_bot.services.weekly_digest import (
    already_sent,
    build_month_digest,
    build_weekly_digest,
    completed_week,
    current_week,
    format_rub,
    format_today_message,
    mark_sent,
    period_label,
    render_legacy_html,
    render_rich_html,
    seconds_until_next_send,
)


class WeekBoundsTests(TestCase):
    def test_completed_week_is_previous_monday_to_sunday(self):
        # 14 октября 2026 — среда
        start, end = completed_week(date(2026, 10, 14))
        self.assertEqual(start, date(2026, 10, 5))
        self.assertEqual(end, date(2026, 10, 11))

    def test_current_week_runs_through_today(self):
        start, end = current_week(date(2026, 10, 14))
        self.assertEqual(start, date(2026, 10, 12))
        self.assertEqual(end, date(2026, 10, 14))

    def test_period_label_same_month_and_year_boundary(self):
        self.assertEqual(
            period_label(date(2026, 10, 5), date(2026, 10, 11)),
            '5–11 октября',
        )
        self.assertEqual(
            period_label(date(2026, 9, 28), date(2026, 10, 4)),
            '28 сентября – 4 октября',
        )

    def test_next_send_is_nine_in_the_morning_vietnam(self):
        morning = datetime(2026, 10, 12, 8, 0, tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
        self.assertEqual(seconds_until_next_send(morning), 3600)
        after = datetime(2026, 10, 12, 9, 0, tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
        self.assertGreater(seconds_until_next_send(after), 23 * 3600)


class WeeklyDigestBuildTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='week-user', password='x')
        self.telegram_user = TelegramUser.objects.create(
            user=self.user,
            telegram_id=4242,
            username='week',
        )
        self.food = Category.objects.create(
            name='Продукты <дом>',
            type=Category.EXPENSE,
            user=self.user,
        )
        self.salary = Category.objects.create(
            name='Зарплата',
            type=Category.INCOME,
            user=self.user,
        )
        Transaction.objects.create(
            user=self.user,
            category=self.salary,
            amount=Decimal('100000'),
            date=date(2026, 10, 6),
        )
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('-40000'),
            date=date(2026, 10, 7),
        )
        # Вне недели: в лимит месяца входит, в сводку недели нет.
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('-5000'),
            date=date(2026, 10, 1),
        )
        self.goal = Goal.objects.create(
            user=self.user,
            title='Отпуск',
            target_amount=Decimal('60000'),
            deadline=date(2026, 12, 31),
            created_at=timezone.make_aware(datetime(2026, 6, 1, 8, 0)),
        )
        Goal.objects.filter(pk=self.goal.pk).update(
            created_at=timezone.make_aware(datetime(2026, 6, 1, 8, 0)),
        )
        self.goal.refresh_from_db()
        GoalLedgerEntry.objects.create(
            goal=self.goal,
            amount=Decimal('10000'),
            entry_type=GoalLedgerEntry.DEPOSIT,
            occurred_at=datetime(2026, 10, 8, 3, 0, tzinfo=ZoneInfo('Asia/Ho_Chi_Minh')),
        )
        Budget.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('30000'),
            period_type=Budget.MONTHLY,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )

    def test_week_totals_exclude_other_days_and_count_goal_deposit(self):
        digest = build_weekly_digest(
            self.user,
            date(2026, 10, 5),
            date(2026, 10, 11),
            today=date(2026, 10, 14),
            in_progress=False,
        )
        self.assertEqual(digest.income, Decimal('100000'))
        self.assertEqual(digest.expenses, Decimal('40000'))
        self.assertEqual(digest.balance, Decimal('60000'))
        self.assertEqual(digest.allocations, Decimal('10000'))
        self.assertEqual(digest.free_funds, Decimal('50000'))
        self.assertEqual(digest.expense_rows[0].label, 'Продукты <дом>')
        self.assertEqual(digest.expense_rows[0].amount, Decimal('40000'))
        self.assertEqual(digest.budget_rows[0].spent, Decimal('45000'))
        self.assertEqual(digest.budget_rows[0].remaining, Decimal('-15000'))
        self.assertEqual(len(digest.goal_rows), 1)
        self.assertIn('Отпуск', digest.goal_rows[0].title)

    def test_rich_html_escapes_names_and_draws_a_table(self):
        digest = build_weekly_digest(
            self.user,
            date(2026, 10, 5),
            date(2026, 10, 11),
            today=date(2026, 10, 14),
            in_progress=False,
        )
        html = render_rich_html(digest)
        self.assertIn('<table bordered striped>', html)
        self.assertIn('Продукты &lt;дом&gt;', html)
        self.assertNotIn('Продукты <дом>', html)
        self.assertIn('50 000 ₽', html)
        self.assertIn('<h1>Неделя 5–11 октября</h1>', html)
        self.assertIn('За октябрь осталось', html)
        self.assertIn('55 000 ₽', html)
        self.assertNotIn('Баланс', html)
        legacy = render_legacy_html(digest)
        self.assertNotIn('<table', legacy)
        self.assertIn('Продукты &lt;дом&gt;', legacy)
        self.assertIn('<b>', legacy)

    def test_mark_sent_is_idempotent_for_the_same_week(self):
        start = date(2026, 10, 5)
        self.assertFalse(already_sent(self.telegram_user, start))
        mark_sent(self.telegram_user, start)
        self.assertTrue(already_sent(self.telegram_user, start))
        self.assertFalse(already_sent(self.telegram_user, date(2026, 10, 12)))

    def test_format_rub_groups_thousands(self):
        self.assertEqual(format_rub(Decimal('12000')), '12 000 ₽')
        self.assertEqual(format_rub(Decimal('-1500.4')), '−1 500 ₽')

    def test_a_new_transaction_lands_on_the_vietnam_day(self):
        from unittest.mock import patch

        from asgiref.sync import async_to_sync

        from telegram_bot.services.transaction_service import TransactionService

        with patch(
            'telegram_bot.services.weekly_digest.vietnam_today',
            return_value=date(2026, 10, 22),
        ):
            transaction = async_to_sync(
                TransactionService(self.user).create_transaction,
            )(Decimal('10'), self.food, 'expense')
        self.assertEqual(transaction.date, date(2026, 10, 22))

    def test_today_screen_skips_a_zero_income_and_shows_the_month(self):
        text = format_today_message(
            Decimal('1300'),
            Decimal('0'),
            Decimal('42000'),
            'октябрь',
            'RUB',
        )
        self.assertIn('Расходы: 1 300 ₽', text)
        self.assertNotIn('Доходы', text)
        self.assertNotIn('Баланс', text)
        self.assertIn('За октябрь осталось 42 000 ₽.', text)

    def test_month_article_keeps_the_month_balance(self):
        digest = build_month_digest(self.user, 2026, 10, date(2026, 10, 14))
        html = render_rich_html(digest)
        self.assertIn('<h1>Октябрь 2026</h1>', html)
        self.assertIn('Баланс', html)
        self.assertIn('55 000 ₽', html)
        self.assertIn('Продукты &lt;дом&gt;', html)
        self.assertNotIn('За октябрь осталось', html)
