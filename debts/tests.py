"""Долг живёт своей суммой и контрагентом и не создаёт транзакцию."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from categories.models import Category
from debts.ledger import add_payment, obligation_lines
from debts.models import Debt
from recurring.models import RecurringTemplate
from transactions.models import Transaction


class DebtTests(TestCase):
    def test_payment_reduces_the_remainder_and_closes_without_a_transaction(self):
        user = User.objects.create_user(username='debtor', password='x')
        debt = Debt.objects.create(
            user=user,
            counterparty='Иван',
            direction=Debt.OWE,
            principal=Decimal('5000'),
        )
        add_payment(debt, Decimal('2000'), date(2026, 10, 1))
        debt.refresh_from_db()
        self.assertEqual(debt.remaining, Decimal('3000'))
        self.assertTrue(debt.is_open)
        self.assertEqual(Transaction.objects.filter(user=user).count(), 0)

        add_payment(debt, Decimal('3000'), date(2026, 10, 2))
        debt.refresh_from_db()
        self.assertFalse(debt.is_open)
        self.assertEqual(debt.remaining, Decimal('0'))

        with self.assertRaises(ValueError):
            add_payment(debt, Decimal('1'), date(2026, 10, 3))

    def test_report_block_does_not_mention_a_recurring_name(self):
        user = User.objects.create_user(username='owed', password='x')
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
            counterparty='Маша',
            direction=Debt.OWED,
            principal=Decimal('800'),
        )
        text = '\n'.join(obligation_lines(user))
        self.assertIn('Маша', text)
        self.assertIn('мне должны', text)
        self.assertNotIn('Аренда', text)
