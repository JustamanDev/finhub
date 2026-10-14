"""Срок цели: темп отложений, дедлайн и вопрос консультанту."""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from goals.models import Goal, GoalLedgerEntry
from telegram_bot.services.goal_eta import (
    STATUS_BEHIND,
    STATUS_NO_DEADLINE,
    STATUS_NO_PACE,
    STATUS_ON_TRACK,
    STATUS_OVERDUE,
    STATUS_REACHED,
    build_goal_eta,
)
from telegram_bot.voice.intents import VoiceIntentType
from telegram_bot.voice.interpreter import VoiceInterpreter
from telegram_bot.voice.period_parser import (
    looks_like_advisor_question,
    parse_goal_hint,
)


class GoalEtaMathTests(TestCase):
    def test_on_track_when_pace_covers_deadline(self):
        eta = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('60000'),
            balance=Decimal('30000'),
            deadline=date(2026, 12, 31),
            monthly_nets=[Decimal('10000')] * 3,
            deposited_this_month=Decimal('0'),
            free_funds=Decimal('15000'),
        )
        self.assertEqual(eta.status, STATUS_ON_TRACK)
        self.assertEqual(eta.required_per_month, Decimal('10000.00'))
        self.assertEqual(eta.pace_per_month, Decimal('10000.00'))
        self.assertEqual(eta.eta_months, 3)
        self.assertEqual(eta.eta_date, date(2027, 1, 14))
        self.assertTrue(eta.as_dict()['free_funds_cover_rest'])

    def test_behind_when_pace_is_slower_than_plan(self):
        eta = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('60000'),
            balance=Decimal('30000'),
            deadline=date(2026, 12, 31),
            monthly_nets=[Decimal('5000')] * 3,
            deposited_this_month=Decimal('0'),
            free_funds=Decimal('1000'),
        )
        self.assertEqual(eta.status, STATUS_BEHIND)
        self.assertEqual(eta.eta_months, 6)
        self.assertEqual(eta.eta_date, date(2027, 4, 14))
        self.assertFalse(eta.as_dict()['free_funds_cover_rest'])

    def test_no_pace_without_complete_months(self):
        eta = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('60000'),
            balance=Decimal('0'),
            deadline=date(2026, 12, 31),
            monthly_nets=[],
            deposited_this_month=Decimal('2000'),
            free_funds=Decimal('0'),
        )
        self.assertEqual(eta.status, STATUS_NO_PACE)
        self.assertIsNone(eta.eta_date)
        self.assertEqual(eta.still_needed_this_month, Decimal('18000.00'))

    def test_overdue_and_reached(self):
        overdue = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('1000'),
            balance=Decimal('100'),
            deadline=date(2026, 9, 1),
            monthly_nets=[Decimal('100')],
            deposited_this_month=Decimal('0'),
            free_funds=Decimal('0'),
        )
        self.assertEqual(overdue.status, STATUS_OVERDUE)

        reached = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('1000'),
            balance=Decimal('1000'),
            deadline=date(2026, 12, 1),
            monthly_nets=[],
            deposited_this_month=Decimal('0'),
            free_funds=Decimal('0'),
        )
        self.assertEqual(reached.status, STATUS_REACHED)
        self.assertEqual(reached.eta_months, 0)

    def test_open_goal_still_has_eta_from_pace(self):
        eta = build_goal_eta(
            today=date(2026, 10, 14),
            target=Decimal('30000'),
            balance=Decimal('0'),
            deadline=None,
            monthly_nets=[Decimal('10000')] * 3,
            deposited_this_month=Decimal('0'),
            free_funds=Decimal('0'),
        )
        self.assertEqual(eta.status, STATUS_NO_DEADLINE)
        self.assertEqual(eta.as_dict()['eta_label'], 'январь 2027')
        self.assertIsNone(eta.required_per_month)


class GoalEtaSnapshotTests(TestCase):
    def test_question_focuses_goal_and_uses_past_deposits(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.advisor_snapshot_service import (
            AdvisorSnapshotService,
        )

        user = User.objects.create_user(username='eta-user', password='x')
        goal = Goal.objects.create(
            user=user,
            title='Отпуск',
            target_amount=Decimal('60000'),
            deadline=date(2026, 12, 31),
        )
        Goal.objects.filter(pk=goal.pk).update(
            created_at=timezone.make_aware(datetime(2026, 6, 1)),
        )
        for month in (7, 8, 9):
            GoalLedgerEntry.objects.create(
                goal=goal,
                amount=Decimal('10000'),
                entry_type=GoalLedgerEntry.DEPOSIT,
                occurred_at=timezone.make_aware(datetime(2026, month, 15)),
            )

        today = date(2026, 10, 14)
        snapshot = async_to_sync(AdvisorSnapshotService(user).build)(
            today=today,
            question='когда закрою отпуск',
        )
        self.assertEqual(snapshot['goal_focus']['status'], 'matched')
        self.assertEqual(snapshot['goal_focus']['title'], 'Отпуск')
        eta = snapshot['goals'][0]['eta']
        self.assertEqual(eta['status'], STATUS_ON_TRACK)
        self.assertEqual(eta['pace_per_month'], 10000.0)
        self.assertEqual(eta['pace_months'], 3)
        self.assertEqual(eta['required_per_month'], 10000.0)

    def test_unknown_goal_lists_existing_titles(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.advisor_snapshot_service import (
            AdvisorSnapshotService,
        )

        user = User.objects.create_user(username='eta-unknown', password='x')
        Goal.objects.create(
            user=user,
            title='Отпуск',
            target_amount=Decimal('1000'),
        )
        snapshot = async_to_sync(AdvisorSnapshotService(user).build)(
            today=date(2026, 10, 14),
            question='когда закрою байк',
        )
        self.assertEqual(snapshot['goal_focus']['status'], 'unknown')
        self.assertIn('Отпуск', snapshot['goal_focus']['candidates'])


class AdvisorQuestionRoutingTests(TestCase):
    def test_question_detectors(self):
        self.assertEqual(parse_goal_hint('когда закрою отпуск'), 'отпуск')
        self.assertEqual(parse_goal_hint('сколько откладывать на ipad'), 'ipad')
        self.assertIsNone(parse_goal_hint('успею ли к дедлайну'))
        self.assertTrue(looks_like_advisor_question('когда закрою отпуск'))
        self.assertTrue(looks_like_advisor_question('сколько потратил в этом месяце'))
        self.assertFalse(looks_like_advisor_question('500 кофе'))
        self.assertFalse(looks_like_advisor_question('210 тысяч'))
        self.assertFalse(looks_like_advisor_question('пополни цель отпуск на 5000'))

    def test_voice_fast_path_keeps_deposits_and_amounts(self):
        from categories.models import Category

        user = User.objects.create_user(username='eta-voice', password='x')
        Category.objects.create(
            user=user,
            name='Продукты',
            type='expense',
            color='#000',
            icon='🛒',
        )
        interpreter = VoiceInterpreter(user)
        question = interpreter.interpret('когда закрою отпуск')
        self.assertEqual(question.intent, VoiceIntentType.ASK_ADVISOR)

        amount = interpreter.interpret('210 тысяч')
        self.assertEqual(amount.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(amount.amount, Decimal('210000'))

        deposit = interpreter.interpret('пополни цель отпуск на 5000')
        self.assertEqual(deposit.intent, VoiceIntentType.MANAGE_GOAL)
        self.assertEqual(deposit.amount, Decimal('5000'))
