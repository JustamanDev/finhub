"""Два Excel-отчёта: месяц и год."""

import zipfile
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from xml.etree import ElementTree

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget
from categories.models import Category
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.handlers.callback_handler import CallbackHandler
from telegram_bot.keyboards.reports import ReportKeyboard
from telegram_bot.services.report_export_service import ReportExportService
from telegram_bot.services.report_figures import (
    BudgetSnap,
    Flow,
    GoalSnap,
    LedgerTx,
    Tx,
    build_month_report,
    build_year_report,
)
from transactions.models import Transaction


TODAY = date(2026, 10, 10)


def _tx(tx_id, day, amount, category_id, label) -> Tx:
    return Tx(tx_id, day, Decimal(amount), category_id, label, '', 'RUB', Decimal(amount))


def _entry(day, goal_id, title, entry_type, amount, *, envelope=False) -> LedgerTx:
    return LedgerTx(day, goal_id, title, envelope, entry_type, Decimal(amount), '')


def _report(**kwargs):
    base = dict(
        year=2026,
        month=10,
        today=TODAY,
        unit='₽',
        currency_phrase='рублях',
        generated_label='10.10.2026 09:00',
        transactions=[],
        ledger=[],
        goals=[],
        budgets=[],
    )
    base.update(kwargs)
    return build_month_report(**base)


class ReportFigureTests(TestCase):
    def test_free_keeps_reserve_spend_from_being_counted_twice(self):
        report = _report(
            transactions=[
                _tx(1, TODAY, 100000, 1, 'Зарплата'),
                _tx(2, TODAY, -30000, 2, 'Еда'),
                _tx(3, TODAY, -5000, 2, 'Еда'),
            ],
            ledger=[
                _entry(TODAY, 7, 'Кухня', 'deposit', 10000, envelope=True),
                _entry(TODAY, 7, 'Кухня', 'spend', -5000, envelope=True),
            ],
            goals=[GoalSnap(7, 'Кухня', True, 'active', None, None)],
        )
        self.assertEqual(report.flow, Flow(Decimal('100000'), Decimal('35000'), Decimal('5000')))
        self.assertEqual(report.flow.free, Decimal('60000'))
        self.assertEqual(report.envelopes[0].balance, Decimal('5000'))
        self.assertIn('больше, чем в сентябре', report.comparison)

    def test_purchase_does_not_reduce_goal_progress(self):
        report = _report(
            ledger=[
                _entry(TODAY, 3, 'Машина', 'deposit', 10000),
                _entry(TODAY, 3, 'Машина', 'spend', -2000),
            ],
            goals=[GoalSnap(3, 'Машина', False, 'active', Decimal('400000'), date(2027, 10, 1))],
        )
        goal = report.goals[0]
        self.assertEqual(goal.committed, Decimal('10000'))
        self.assertEqual(goal.spent_total, Decimal('2000'))
        self.assertEqual(goal.balance, Decimal('8000'))
        self.assertEqual(goal.progress, Decimal('10000') / Decimal('400000'))

    def test_pace_appears_only_while_the_month_is_open(self):
        open_month = _report(transactions=[_tx(1, TODAY, -3100, 2, 'Еда')])
        self.assertIn('Прошло 10 из 31 дней', open_month.pace)
        closed = _report(
            year=2026,
            month=9,
            transactions=[_tx(1, date(2026, 9, 2), -1000, 2, 'Еда')],
        )
        self.assertIsNone(closed.pace)

    def test_limit_uses_this_month_fact(self):
        report = _report(
            transactions=[_tx(1, TODAY, -25000, 2, '🍔 Еда')],
            budgets=[BudgetSnap(2, '🍔 Еда', Decimal('20000'), date(2026, 10, 1), date(2026, 10, 31), True)],
        )
        row = report.expenses[0]
        self.assertEqual(row.amount, Decimal('25000'))
        self.assertEqual(row.limit, Decimal('20000'))
        self.assertEqual(row.remaining, Decimal('-5000'))
        self.assertEqual(row.limit_ratio, Decimal('25000') / Decimal('20000'))

    def test_turned_off_current_limit_stays_hidden(self):
        report = _report(
            transactions=[_tx(1, TODAY, -1000, 2, 'Еда')],
            budgets=[BudgetSnap(2, 'Еда', Decimal('20000'), date(2026, 10, 1), date(2026, 10, 31), False)],
        )
        self.assertIsNone(report.expenses[0].limit)

    def test_future_months_are_empty_and_january_compares_with_december(self):
        report = build_year_report(
            year=2026,
            today=TODAY,
            unit='₽',
            currency_phrase='рублях',
            generated_label='10.10.2026 09:00',
            transactions=[
                _tx(1, date(2025, 12, 5), -4000, 2, 'Еда'),
                _tx(2, date(2026, 1, 5), -1000, 2, 'Еда'),
                _tx(3, date(2026, 11, 5), -9999, 2, 'Еда'),
            ],
            ledger=[],
            goals=[],
            budgets=[],
        )
        self.assertEqual(report.months[0].flow.expenses, Decimal('1000'))
        self.assertEqual(report.months[0].expense_delta, Decimal('-3000'))
        self.assertEqual(report.months[9].state, 'current')
        self.assertIsNone(report.months[10].flow)
        self.assertEqual(report.flow.expenses, Decimal('1000'))
        self.assertEqual(report.expenses[0].months[10], None)
        self.assertEqual(report.expenses[0].months[0], Decimal('1000'))


class ReportWorkbookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='report-user', password='x')
        self.income = Category.objects.create(user=self.user, name='Зарплата', icon='💰', type='income')
        self.food = Category.objects.create(user=self.user, name='Еда', icon='🍔', type='expense')
        Transaction.objects.create(
            user=self.user,
            category=self.income,
            amount=Decimal('100000'),
            original_amount=Decimal('100000'),
            currency='RUB',
            date=TODAY,
            description='Аванс',
        )
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('-25000'),
            original_amount=Decimal('-25000'),
            currency='RUB',
            date=TODAY,
            description='Магазин',
        )
        Transaction.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('-3000'),
            original_amount=Decimal('-3000'),
            currency='RUB',
            date=date(2026, 3, 4),
            description='Март',
        )
        Budget.objects.create(
            user=self.user,
            category=self.food,
            amount=Decimal('20000'),
            period_type=Budget.MONTHLY,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
            is_active=True,
        )
        goal = Goal.objects.create(
            user=self.user,
            title='Машина',
            kind=Goal.SAVINGS,
            target_amount=Decimal('400000'),
            status=Goal.ACTIVE,
        )
        occurred = timezone.make_aware(datetime(2026, 10, 10, 12, 0))
        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=Decimal('10000'),
            entry_type=GoalLedgerEntry.DEPOSIT,
            occurred_at=occurred,
        )

    def test_month_file_has_the_story_and_the_numbers(self):
        result = async_to_sync(ReportExportService(self.user).build_monthly_excel)(2026, 10, TODAY)
        self.assertEqual(result.filename, 'finhub_2026-10.xlsx')
        self.assertEqual(result.caption, 'Отчёт за октябрь 2026')
        text = _xlsx_text(result.content)
        self.assertIn('name="Обзор"', text)
        self.assertIn('name="Категории"', text)
        self.assertIn('name="Резервы"', text)
        self.assertIn('name="Журнал"', text)
        self.assertIn('Движение по дням', text)
        self.assertIn('Машина', text)
        self.assertIn('🍔 Еда', text)
        self.assertNotIn('name="Кэшфлоу"', text)
        numbers = _xlsx_numbers(result.content)
        self.assertIn(100000, numbers)
        self.assertIn(25000, numbers)
        self.assertIn(65000, numbers)

    def test_year_file_keeps_future_months_and_the_march_fact(self):
        result = async_to_sync(ReportExportService(self.user).build_yearly_excel)(2026, TODAY)
        self.assertEqual(result.filename, 'finhub_2026.xlsx')
        self.assertEqual(result.caption, 'Отчёт за 2026 год')
        text = _xlsx_text(result.content)
        self.assertIn('Движение по месяцам', text)
        self.assertIn('Ноябрь', text)
        numbers = _xlsx_numbers(result.content)
        self.assertIn(3000, numbers)
        self.assertIn(100000, numbers)


class ReportMenuTests(TestCase):
    def test_main_menu_names_the_screen_and_the_two_files(self):
        labels = _labels(ReportKeyboard.get_report_main_keyboard())
        self.assertEqual(
            labels,
            [
                ('Этот месяц', 'report_current'),
                ('Файл за месяц', 'report_export_excel_current'),
                ('Файл за год', 'report_export_year_current'),
                ('Другие месяцы', 'report_all'),
                ('🏠 Главное меню', 'main_menu'),
            ],
        )

    def test_period_menu_exports_that_month_and_its_year(self):
        keyboard = ReportKeyboard.get_report_navigation_keyboard(
            {'year': 2026, 'month': 3},
            [{'year': 2026, 'month': 3}],
        )
        labels = dict(_labels(keyboard))
        self.assertEqual(labels['Файл за месяц'], 'report_export_excel_2026_3')
        self.assertEqual(labels['Файл за год'], 'report_export_year_2026')


class ReportExportRouteTests(TestCase):
    def setUp(self):
        self.handler = CallbackHandler()
        self.handler.get_or_create_telegram_user = AsyncMock(return_value=MagicMock())
        self.handler.handle_error = AsyncMock()
        self.calls = []

    async def _bind(self, name, attr):
        async def _inner(*_args, **_kwargs):
            self.calls.append(name)

        setattr(self.handler, attr, _inner)

    async def _route(self, data):
        self.calls.clear()
        update = MagicMock()
        update.effective_user = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = data
        update.callback_query.answer = AsyncMock()
        await self.handler.handle_callback_query(update, MagicMock())
        return list(self.calls)

    async def test_year_export_is_not_treated_as_a_month(self):
        await self._bind('month', '_handle_report_export_excel_current')
        await self._bind('year', '_handle_report_export_year_current')
        await self._bind('period', '_handle_report_export_excel_period')
        await self._bind('year_period', '_handle_report_export_year')
        await self._bind('unknown', '_handle_unknown_callback')
        self.assertEqual(await self._route('report_export_excel_current'), ['month'])
        self.assertEqual(await self._route('report_export_year_current'), ['year'])
        self.assertEqual(await self._route('report_export_excel_2026_03'), ['period'])
        self.assertEqual(await self._route('report_export_year_2026'), ['year_period'])


def _labels(keyboard):
    return [
        (button.text, button.callback_data)
        for row in keyboard.inline_keyboard
        for button in row
    ]


def _xlsx_text(content: bytes) -> str:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        parts = [
            archive.read(name).decode('utf-8')
            for name in archive.namelist()
            if name.endswith('.xml')
        ]
    return '\n'.join(parts)


def _xlsx_numbers(content: bytes) -> set[float]:
    found: set[float] = set()
    with zipfile.ZipFile(BytesIO(content)) as archive:
        for name in archive.namelist():
            if not name.startswith('xl/worksheets/'):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for node in root.iter():
                if node.tag.endswith('v') and node.text:
                    try:
                        found.add(float(node.text))
                    except ValueError:
                        continue
    return found
