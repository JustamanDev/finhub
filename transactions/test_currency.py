from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from categories.models import Category
from telegram_bot.utils.currency_text import (
    explicit_entry_currency,
    parse_leading_amount,
)
from telegram_bot.utils.text_parser import TextCommandParser
from transactions.currencies import RUB, VND
from transactions.exchange import apply_entered_amount, parse_cbr_vnd_xml, rub_amount
from transactions.models import ExchangeRate, Transaction


CBR_SAMPLE = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="14.10.2026" name="Foreign Currency Market">
    <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Доллар США</Name>
        <Value>90,0000</Value>
    </Valute>
    <Valute ID="R01720">
        <NumCode>704</NumCode>
        <CharCode>VND</CharCode>
        <Nominal>10000</Nominal>
        <Name>Донгов</Name>
        <Value>32,4500</Value>
    </Valute>
</ValCurs>
"""


class CbrXmlTests(TestCase):
    def test_parses_vnd_quote_per_unit(self):
        quote = parse_cbr_vnd_xml(CBR_SAMPLE)
        self.assertEqual(quote.rate_date, date(2026, 10, 14))
        self.assertEqual(quote.nominal, 10000)
        self.assertEqual(quote.value, Decimal('32.4500'))
        self.assertEqual(quote.rate, Decimal('0.0032450000'))

    def test_rub_amount_keeps_sign(self):
        self.assertEqual(
            rub_amount(Decimal('-50000'), Decimal('0.0032450000')),
            Decimal('-162.25'),
        )


class LeadingAmountTests(TestCase):
    def test_plain_amount_has_no_currency_mark(self):
        parsed = parse_leading_amount('500 кофе')
        self.assertEqual(parsed['amount'], '500')
        self.assertIsNone(parsed['currency'])
        self.assertEqual(parsed['rest'], 'кофе')

    def test_restaurant_is_not_eaten_by_ruble_letter(self):
        parsed = parse_leading_amount('500 ресторан')
        self.assertIsNone(parsed['currency'])
        self.assertEqual(parsed['rest'], 'ресторан')

    def test_explicit_marks(self):
        dong = parse_leading_amount('50000д кофе')
        self.assertEqual(dong['currency'], VND)
        self.assertEqual(dong['rest'], 'кофе')

        words = parse_leading_amount('50000 донгов кофе')
        self.assertEqual(words['currency'], VND)
        self.assertEqual(words['rest'], 'кофе')

        rub = parse_leading_amount('1500 руб такси')
        self.assertEqual(rub['currency'], RUB)
        self.assertEqual(rub['rest'], 'такси')

        spaced = parse_leading_amount('500 р кофе')
        self.assertEqual(spaced['currency'], RUB)
        self.assertEqual(spaced['rest'], 'кофе')

        only = parse_leading_amount('50000д')
        self.assertEqual(only['currency'], VND)
        self.assertEqual(only['rest'], '')


class TextParserCurrencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='parser-user', password='x')
        self.category = Category.objects.create(
            user=self.user,
            name='Кофе',
            type=Category.EXPENSE,
        )

    def test_unmarked_amount_does_not_pick_currency(self):
        parsed = TextCommandParser(self.user).parse('500 кофе')
        self.assertTrue(parsed['success'])
        self.assertEqual(parsed['amount'], Decimal('500'))
        self.assertIsNone(parsed['currency'])
        self.assertIsNone(explicit_entry_currency(parsed))
        self.assertEqual(parsed['category'].id, self.category.id)

    def test_spoken_thousands_are_an_amount(self):
        parsed = TextCommandParser(self.user).parse('210 тысяч')
        self.assertTrue(parsed['success'])
        self.assertEqual(parsed['type'], 'amount_only')
        self.assertEqual(parsed['amount'], Decimal('210000'))
        self.assertIsNone(parsed['currency'])

    def test_dong_mark_does_not_stick_to_category(self):
        parsed = TextCommandParser(self.user).parse('50000д кофе')
        self.assertTrue(parsed['success'])
        self.assertEqual(parsed['amount'], Decimal('50000'))
        self.assertEqual(parsed['currency'], VND)
        self.assertEqual(parsed['category'].id, self.category.id)


class VndConversionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fx-user', password='x')
        self.category = Category.objects.create(
            user=self.user,
            name='Кофе',
            type=Category.EXPENSE,
        )
        self.quote = SimpleNamespace(
            rate=Decimal('0.0032450000'),
            rate_date=date(2026, 10, 14),
            nominal=10000,
        )

    def test_existing_style_create_stays_rubles(self):
        transaction = Transaction.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('-500.00'),
            date=date(2026, 10, 14),
        )
        self.assertEqual(transaction.currency, RUB)
        self.assertEqual(transaction.original_amount, Decimal('-500.00'))
        self.assertEqual(transaction.amount, Decimal('-500.00'))

    @patch('transactions.exchange.get_vnd_rub_rate')
    def test_dong_expense_is_stored_in_rubles(self, get_rate):
        get_rate.return_value = self.quote
        transaction = Transaction(
            user=self.user,
            category=self.category,
            date=date(2026, 10, 14),
        )
        apply_entered_amount(transaction, Decimal('-50000'), VND)
        transaction.save()

        stored = Transaction.objects.get(pk=transaction.pk)
        self.assertEqual(stored.currency, VND)
        self.assertEqual(stored.original_amount, Decimal('-50000'))
        self.assertEqual(stored.amount, Decimal('-162.25'))
        self.assertEqual(stored.rate_date, date(2026, 10, 14))
        self.assertEqual(stored.rate_nominal, 10000)

    def test_cached_rate_is_reused_same_moscow_day(self):
        from transactions.exchange import get_vnd_rub_rate, moscow_today

        ExchangeRate.objects.create(
            rate_date=date(2026, 10, 14),
            base_currency=VND,
            quote_currency=RUB,
            nominal=10000,
            value=Decimal('32.4500'),
            rate=Decimal('0.0032450000'),
            fetched_on=moscow_today(),
        )
        with patch('transactions.exchange.fetch_cbr_vnd_quote') as fetch:
            quote = get_vnd_rub_rate()
        fetch.assert_not_called()
        self.assertEqual(quote.nominal, 10000)


class PersonalCurrencyTests(TestCase):
    def test_usd_mark_is_a_currency(self):
        parsed = parse_leading_amount('20 usd кофе')
        self.assertEqual(parsed['currency'], 'USD')
        self.assertEqual(parsed['rest'], 'кофе')

    def test_disabled_currency_is_not_explicit(self):
        self.assertIsNone(
            explicit_entry_currency(
                {'currency': 'USD'},
                allowed=['RUB', 'VND'],
            ),
        )
        self.assertEqual(
            explicit_entry_currency(
                {'currency': 'VND'},
                allowed=['RUB', 'VND'],
            ),
            'VND',
        )

    def test_cross_rate_stores_amount_in_base(self):
        from transactions.exchange import moscow_today

        user = User.objects.create_user(username='fx-usd', password='x')
        category = Category.objects.create(
            user=user,
            name='Кофе',
            type=Category.EXPENSE,
        )
        today = moscow_today()
        ExchangeRate.objects.create(
            rate_date=date(2026, 10, 14),
            base_currency='USD',
            quote_currency='RUB',
            nominal=1,
            value=Decimal('90'),
            rate=Decimal('90'),
            fetched_on=today,
        )
        ExchangeRate.objects.create(
            rate_date=date(2026, 10, 14),
            base_currency='EUR',
            quote_currency='RUB',
            nominal=1,
            value=Decimal('100'),
            rate=Decimal('100'),
            fetched_on=today,
        )
        transaction = Transaction(
            user=user,
            category=category,
            date=date(2026, 10, 14),
        )
        apply_entered_amount(transaction, Decimal('10'), 'USD', base='EUR')
        transaction.save()
        stored = Transaction.objects.get(pk=transaction.pk)
        self.assertEqual(stored.report_currency, 'EUR')
        self.assertEqual(stored.amount, Decimal('9.00'))
        self.assertEqual(stored.original_amount, Decimal('10'))

    def test_base_change_rescales_existing_rubles(self):
        from transactions.exchange import change_base_currency, moscow_today
        from telegram_bot.models import TelegramUser

        user = User.objects.create_user(username='fx-base', password='x')
        category = Category.objects.create(
            user=user,
            name='Кофе',
            type=Category.EXPENSE,
        )
        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=4242,
            base_currency='RUB',
            input_currencies=['RUB', 'VND'],
        )
        Transaction.objects.create(
            user=user,
            category=category,
            amount=Decimal('90.00'),
            date=date(2026, 10, 14),
        )
        ExchangeRate.objects.create(
            rate_date=date(2026, 10, 14),
            base_currency='USD',
            quote_currency='RUB',
            nominal=1,
            value=Decimal('90'),
            rate=Decimal('90'),
            fetched_on=moscow_today(),
        )
        change_base_currency(telegram_user, 'USD')
        telegram_user.refresh_from_db()
        stored = Transaction.objects.get(user=user)
        self.assertEqual(telegram_user.base_currency, 'USD')
        self.assertEqual(stored.amount, Decimal('1.00'))
        self.assertEqual(stored.report_currency, 'USD')
