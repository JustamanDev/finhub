"""Напоминания по сроку и темпу цели. Деньги не двигают."""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from goals.models import Goal
from telegram_bot.models import TelegramUser
from telegram_bot.services.goal_watch import (
    collect_goal_watches,
    remember_goal_watch,
)


class GoalWatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='watch', password='x')
        self.telegram_user = TelegramUser.objects.create(
            user=self.user,
            telegram_id=77001,
            username='watch',
        )

    def _goal(self, title, deadline, *, kind=Goal.SAVINGS, target='10000'):
        return Goal.objects.create(
            user=self.user,
            title=title,
            kind=kind,
            target_amount=Decimal(target),
            deadline=deadline,
            currency='VND',
        )

    def test_week_day_and_late_are_different_messages(self):
        self._goal('Визаран', date(2026, 3, 20))
        week = collect_goal_watches(self.telegram_user, date(2026, 3, 15))
        self.assertEqual(len(week), 1)
        self.assertIn('До срока 5 дней', week[0][1])
        self.assertIn('карточке цели', week[0][1])

        day = collect_goal_watches(self.telegram_user, date(2026, 3, 20))
        self.assertIn('Срок сегодня', day[0][1])

        late = collect_goal_watches(self.telegram_user, date(2026, 3, 23))
        self.assertIn('Срок был', late[0][1])

        too_late = collect_goal_watches(self.telegram_user, date(2026, 3, 28))
        self.assertEqual(too_late, [])

    def test_same_notice_is_not_repeated(self):
        self._goal('Визаран', date(2026, 3, 20))
        first = collect_goal_watches(self.telegram_user, date(2026, 3, 15))
        remember_goal_watch(self.telegram_user, first[0][0])
        second = collect_goal_watches(self.telegram_user, date(2026, 3, 16))
        self.assertEqual(second, [])

    def test_pace_starts_on_the_20th_when_deadline_is_far(self):
        self._goal('Подушка', date(2026, 6, 1), target='12000')
        quiet = collect_goal_watches(self.telegram_user, date(2026, 3, 10))
        self.assertEqual(quiet, [])
        pace = collect_goal_watches(self.telegram_user, date(2026, 3, 20))
        self.assertEqual(len(pace), 1)
        self.assertIn('до темпа не хватает', pace[0][1])
        self.assertTrue(pace[0][0].endswith(':2026-03'))

    def test_envelope_and_reached_goal_stay_quiet(self):
        self._goal('Запас', date(2026, 3, 20), kind=Goal.ENVELOPE)
        reached = self._goal('Собрана', date(2026, 3, 20))
        from django.utils import timezone
        from goals.models import GoalLedgerEntry

        GoalLedgerEntry.objects.create(
            goal=reached,
            entry_type=GoalLedgerEntry.DEPOSIT,
            amount=Decimal('10000'),
            occurred_at=timezone.now(),
        )
        self.assertEqual(
            collect_goal_watches(self.telegram_user, date(2026, 3, 15)),
            [],
        )

    def test_morning_sends_at_most_three(self):
        for index, day in enumerate((16, 17, 18, 19), start=1):
            self._goal(f'Цель {index}', date(2026, 3, day))
        notices = collect_goal_watches(self.telegram_user, date(2026, 3, 15))
        self.assertEqual(len(notices), 3)
        self.assertIn('Цель 1', notices[0][1])
