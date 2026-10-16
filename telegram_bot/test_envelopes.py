"""Конверт без процента и архив целей."""

import zipfile
from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from goals.models import Goal, GoalLedgerEntry
from telegram_bot.handlers.callback_handler import CallbackHandler
from telegram_bot.handlers.goals_handler import GoalsHandler
from telegram_bot.services.goal_service import GoalService, GoalTitleTaken
from telegram_bot.services.goal_spend import list_goals_for_spend
from telegram_bot.services.report_export_service import ReportExportService
from transactions.models import Transaction
from categories.models import Category


class EnvelopeAndArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='envelope-user', password='x')
        self.service = GoalService(self.user)
        self.today = timezone.localdate()

    def test_envelope_has_balance_and_no_completion_percent(self):
        goal = async_to_sync(self.service.create_envelope)('Еда', Decimal('10000'))
        self.assertEqual(goal.kind, Goal.ENVELOPE)
        self.assertIsNone(goal.target_amount)

        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=Decimal('-2000'),
            entry_type=GoalLedgerEntry.SPEND,
            occurred_at=timezone.now(),
            comment='Продукты',
        )
        data = async_to_sync(self.service.get_goal_card_data)(goal.id)
        self.assertEqual(data['balance'], Decimal('8000'))
        self.assertEqual(data['spent'], Decimal('2000'))
        self.assertIsNone(data['eta'])

        text = '\n'.join(GoalsHandler._card_lines(data))
        self.assertIn('лежит **8,000 ₽**', text)
        self.assertNotIn('%', text)
        self.assertNotIn('Осталось накопить', text)

    def test_spending_from_a_savings_goal_does_not_lower_progress(self):
        goal = async_to_sync(self.service.create_goal)('Машина', Decimal('10000'))
        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=Decimal('10000'),
            entry_type=GoalLedgerEntry.DEPOSIT,
            occurred_at=timezone.now(),
        )
        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=Decimal('-2000'),
            entry_type=GoalLedgerEntry.SPEND,
            occurred_at=timezone.now(),
        )
        data = async_to_sync(self.service.get_goal_card_data)(goal.id)
        self.assertEqual(data['progress_pct'], Decimal('100'))
        self.assertEqual(data['committed'], Decimal('10000'))
        self.assertEqual(data['balance'], Decimal('8000'))
        self.assertEqual(data['remaining_total'], Decimal('0'))

    def test_archive_hides_the_record_and_keeps_the_reserve(self):
        goal = async_to_sync(self.service.create_envelope)('Еда', Decimal('8000'))
        Category.objects.create(
            user=self.user,
            name='Зарплата',
            type=Category.INCOME,
            icon='💰',
        )
        Transaction.objects.create(
            user=self.user,
            category=Category.objects.get(name='Зарплата'),
            amount=Decimal('100000'),
            date=self.today,
        )
        before = async_to_sync(self.service.get_free_funds_for_month)(self.today)

        archived = async_to_sync(self.service.archive_goal)(goal.id)
        self.assertEqual(archived.status, Goal.ARCHIVED)
        listed = async_to_sync(self.service.list_goals)()
        self.assertEqual(listed, [])
        self.assertEqual(list_goals_for_spend(self.user), [])
        after = async_to_sync(self.service.get_free_funds_for_month)(self.today)
        self.assertEqual(after, before)
        self.assertEqual(after, Decimal('92000'))

        restored = async_to_sync(self.service.restore_goal)(goal.id)
        self.assertEqual(restored.status, Goal.ACTIVE)
        again = async_to_sync(self.service.list_goals)()
        self.assertEqual([item.id for item in again], [goal.id])

    def test_a_taken_name_is_a_message_not_a_crash(self):
        async_to_sync(self.service.create_envelope)('Еда', Decimal('1000'))
        with self.assertRaises(GoalTitleTaken) as caught:
            async_to_sync(self.service.create_goal)('Еда', Decimal('50000'))
        self.assertIn('уже есть', str(caught.exception))

    def test_creating_the_same_name_brings_an_archived_envelope_back(self):
        goal = async_to_sync(self.service.create_envelope)('Еда', Decimal('1000'))
        async_to_sync(self.service.archive_goal)(goal.id)
        revived = async_to_sync(self.service.create_envelope)('Еда', Decimal('500'))
        self.assertEqual(revived.id, goal.id)
        self.assertEqual(revived.status, Goal.ACTIVE)
        data = async_to_sync(self.service.get_goal_card_data)(goal.id)
        self.assertEqual(data['balance'], Decimal('1500'))

    def test_excel_splits_envelopes_from_savings_goals(self):
        async_to_sync(self.service.create_envelope)('Еда', Decimal('10000'))
        async_to_sync(self.service.create_goal)('Машина', Decimal('400000'))
        result = async_to_sync(ReportExportService(self.user).build_monthly_excel)(
            self.today.year,
            self.today.month,
        )
        workbook = zipfile.ZipFile(BytesIO(result.content)).read('xl/workbook.xml').decode()
        self.assertIn('name="Цели"', workbook)
        self.assertIn('name="Конверты"', workbook)
        strings = zipfile.ZipFile(BytesIO(result.content)).read('xl/sharedStrings.xml').decode()
        self.assertIn('Остаток (₽)', strings)
        self.assertIn('Еда', strings)
        self.assertIn('Машина', strings)
        self.assertNotIn('не выполнена', strings)


class GoalArchiveRouteTests(TestCase):
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

    async def test_archive_confirm_and_yes_are_different_actions(self):
        await self._bind('confirm', '_handle_goal_archive_confirm')
        await self._bind('yes', '_handle_goal_archive_yes')
        await self._bind('restore', '_handle_goal_restore')
        await self._bind('unknown', '_handle_unknown_callback')
        self.assertEqual(await self._route('goal_archive_4'), ['confirm'])
        self.assertEqual(await self._route('goal_archive_yes_4'), ['yes'])
        self.assertEqual(await self._route('goal_restore_4'), ['restore'])
