"""Ритм повтора и то, что долг в этот блок не попадает."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from categories.models import Category
from debts.models import Debt
from recurring.models import RecurringTemplate
from recurring.rhythm import (
    add_months,
    due_templates,
    expectation_lines,
    expectation_phrase,
    mark_reminded,
    roll_forward,
)
from telegram_bot.services.recurring_posting import record_occurrence


class RhythmTests(TestCase):
    def test_month_end_clamps_and_stays_on_the_calendar_day(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(
            roll_forward(date(2026, 1, 15), RecurringTemplate.MONTHLY, date(2026, 4, 2)),
            date(2026, 4, 15),
        )

    def test_exact_range_and_empty_expectations(self):
        user = User.objects.create_user(username='rhythm', password='x')
        category = Category.objects.create(user=user, name='Жильё', type=Category.EXPENSE)
        exact = RecurringTemplate(
            user=user,
            name='Аренда',
            category=category,
            periodicity=RecurringTemplate.MONTHLY,
            amount_kind=RecurringTemplate.EXACT,
            amount=Decimal('12000'),
            next_due=date(2026, 11, 15),
        )
        exact.full_clean()
        phrase = expectation_phrase(exact, lambda amount: f'{amount}')
        self.assertEqual(phrase, 'обычно 12000')

        empty = RecurringTemplate(
            user=user,
            name='Подарки',
            category=category,
            periodicity=RecurringTemplate.YEARLY,
            amount_kind=RecurringTemplate.OPEN,
            next_due=date(2026, 12, 1),
        )
        empty.full_clean()
        self.assertEqual(expectation_phrase(empty, lambda amount: ''), 'сумма каждый раз своя')

        broken = RecurringTemplate(
            user=user,
            name='Сломанный',
            category=category,
            periodicity=RecurringTemplate.WEEKLY,
            amount_kind=RecurringTemplate.RANGE,
            amount_min=Decimal('20'),
            amount_max=Decimal('10'),
            next_due=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            broken.full_clean()

    def test_reminder_once_then_a_normal_transaction_moves_the_date(self):
        user = User.objects.create_user(username='rent', password='x')
        category = Category.objects.create(user=user, name='Жильё', type=Category.EXPENSE)
        template = RecurringTemplate.objects.create(
            user=user,
            name='Аренда',
            category=category,
            periodicity=RecurringTemplate.MONTHLY,
            amount_kind=RecurringTemplate.EXACT,
            amount=Decimal('10000'),
            next_due=date(2026, 10, 1),
        )
        today = date(2026, 10, 27)
        self.assertEqual(list(due_templates(user, today)), [template])
        mark_reminded(template)
        self.assertEqual(list(due_templates(user, today)), [])

        transaction = record_occurrence(template, Decimal('11500'), today)
        template.refresh_from_db()
        self.assertEqual(transaction.amount, Decimal('-11500'))
        self.assertEqual(transaction.description, 'Аренда')
        self.assertEqual(transaction.date, today)
        self.assertEqual(template.next_due, date(2026, 11, 1))
        self.assertIsNone(template.reminded_for)

    def test_report_block_does_not_mention_a_debt(self):
        user = User.objects.create_user(username='split', password='x')
        category = Category.objects.create(user=user, name='Жильё', type=Category.EXPENSE)
        RecurringTemplate.objects.create(
            user=user,
            name='Аренда',
            category=category,
            periodicity=RecurringTemplate.MONTHLY,
            amount_kind=RecurringTemplate.OPEN,
            next_due=date(2026, 11, 1),
        )
        Debt.objects.create(
            user=user,
            counterparty='Иван',
            direction=Debt.OWE,
            principal=Decimal('5000'),
        )
        text = '\n'.join(expectation_lines(user, date(2026, 10, 27)))
        self.assertIn('Аренда', text)
        self.assertNotIn('Иван', text)
