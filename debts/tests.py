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

    def test_debt_keeps_dong_and_report_shows_rubles(self):
        from transactions.exchange import moscow_today
        from transactions.models import ExchangeRate

        user = User.objects.create_user(username='vnd-debt', password='x')
        ExchangeRate.objects.create(
            rate_date=date(2026, 11, 13),
            base_currency='VND',
            quote_currency='RUB',
            nominal=1,
            value=Decimal('0.004'),
            rate=Decimal('0.004'),
            fetched_on=moscow_today(),
        )
        debt = Debt.objects.create(
            user=user,
            counterparty='Ань',
            direction=Debt.OWED,
            principal=Decimal('170000'),
            currency='VND',
        )
        text = '\n'.join(obligation_lines(user))
        self.assertIn('170 000 ₫', text)
        self.assertIn('≈ 680 ₽', text)
        self.assertNotIn('170 000 ₽', text)

        add_payment(debt, Decimal('680'), date(2026, 11, 13), source_currency='RUB')
        debt.refresh_from_db()
        self.assertFalse(debt.is_open)
        payment = debt.payments.get()
        self.assertEqual(payment.amount, Decimal('170000.00'))
        self.assertEqual(payment.input_currency, 'RUB')
