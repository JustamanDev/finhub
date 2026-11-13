"""Цель и конверт хранят свою валюту. Отчёт и «свободно» считают базовую."""

from datetime import date
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase

from goals.models import Goal
from telegram_bot.models import TelegramUser
from telegram_bot.services.goal_service import GoalService
from telegram_bot.utils.amount_text import split_amount
from transactions.exchange import change_base_currency, moscow_today
from transactions.models import ExchangeRate


def _rate(code: str, value: str) -> None:
    ExchangeRate.objects.create(
        rate_date=date(2026, 11, 13),
        base_currency=code,
        quote_currency='RUB',
        nominal=1,
        value=Decimal(value),
        rate=Decimal(value),
        fetched_on=moscow_today(),
    )


class OwnCurrencyTests(TestCase):
    def test_split_amount_reads_a_named_currency(self):
        amount, currency = split_amount('170000 донгов')
        self.assertEqual(amount, Decimal('170000.00'))
        self.assertEqual(currency, 'VND')
        amount, currency = split_amount('170 000')
        self.assertEqual(amount, Decimal('170000.00'))
        self.assertIsNone(currency)

    def test_dollar_goal_stores_dollars_and_frees_rubles(self):
        _rate('USD', '90')
        user = User.objects.create_user(username='usd-goal', password='x')
        TelegramUser.objects.create(
            user=user,
            telegram_id=7701,
            base_currency='RUB',
            input_currencies=['RUB', 'USD'],
        )
        service = GoalService(user)
        goal = async_to_sync(service.create_goal)(
            'Отпуск',
            Decimal('1000'),
            currency='USD',
        )
        entry = async_to_sync(service.add_deposit)(
            goal.id,
            Decimal('9000'),
            source_currency='RUB',
        )
        self.assertEqual(goal.currency, 'USD')
        self.assertEqual(goal.target_amount, Decimal('1000'))
        self.assertEqual(entry.amount, Decimal('100.00'))
        self.assertEqual(entry.report_amount, Decimal('9000.00'))
        free = async_to_sync(service.get_free_funds_for_month)(date(2026, 11, 1))
        self.assertEqual(free, Decimal('-9000.00'))
        balance = async_to_sync(service.get_goal_balance)(goal.id)
        self.assertEqual(balance, Decimal('100.00'))

    def test_base_change_does_not_rewrite_the_goal(self):
        _rate('USD', '90')
        user = User.objects.create_user(username='fx-goal', password='x')
        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=7702,
            base_currency='RUB',
            input_currencies=['RUB', 'USD'],
        )
        goal = Goal.objects.create(
            user=user,
            title='Подушка',
            target_amount=Decimal('9000'),
            currency='RUB',
        )
        from goals.models import GoalLedgerEntry

        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=Decimal('900'),
            report_amount=Decimal('900'),
            report_currency='RUB',
            entry_type=GoalLedgerEntry.DEPOSIT,
        )
        change_base_currency(telegram_user, 'USD')
        goal.refresh_from_db()
        entry = goal.entries.get()
        self.assertEqual(goal.target_amount, Decimal('9000'))
        self.assertEqual(goal.currency, 'RUB')
        self.assertEqual(entry.amount, Decimal('900'))
        self.assertEqual(entry.report_amount, Decimal('10.00'))
        self.assertEqual(entry.report_currency, 'USD')
