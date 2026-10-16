"""Расход из цели: одно списание, без двойного вычета из свободно."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from categories.models import Category
from goals.models import Goal, GoalLedgerEntry
from telegram_bot.handlers.callback_handler import CallbackHandler
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.goal_service import GoalService
from telegram_bot.services.goal_spend import (
    GoalSpendShortfall,
    goal_balance,
    goal_spend_note,
    spend_expense_from_goal,
)
from telegram_bot.services.transaction_service import TransactionService
from transactions.models import Transaction


class GoalSpendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='spend-user', password='x')
        self.today = timezone.localdate()
        self.food = Category.objects.create(
            user=self.user,
            name='Продукты',
            type=Category.EXPENSE,
            icon='🛒',
        )
        self.parts = Category.objects.create(
            user=self.user,
            name='Запчасти',
            type=Category.EXPENSE,
            icon='🔧',
        )
        self.meal = self._goal('Еда')
        self.car = self._goal('Машина')
        self._put(self.meal, Decimal('10000'))
        self._put(self.car, Decimal('4000'))

    def _goal(self, title):
        return Goal.objects.create(
            user=self.user,
            title=title,
            target_amount=Decimal('100000'),
        )

    def _put(self, goal, amount):
        GoalLedgerEntry.objects.create(
            goal=goal,
            amount=amount,
            entry_type=GoalLedgerEntry.DEPOSIT,
            occurred_at=timezone.now(),
        )

    def _expense(self, amount, category=None, on_date=None):
        return Transaction.objects.create(
            user=self.user,
            category=category or self.food,
            amount=Decimal(amount),
            date=on_date or self.today,
        )

    def test_spending_from_a_goal_reduces_only_that_goal(self):
        expense = self._expense('-2000')
        result = spend_expense_from_goal(self.user, expense.id, self.meal.id)
        self.assertTrue(result.ok)
        self.assertEqual(result.remaining, Decimal('8000'))
        self.assertEqual(goal_balance(self.car.id), Decimal('4000'))
        self.assertIn('Еда', goal_spend_note(expense.id))
        self.assertEqual(
            GoalLedgerEntry.objects.filter(
                linked_transaction=expense,
                entry_type=GoalLedgerEntry.SPEND,
            ).count(),
            1,
        )

    def test_picking_the_same_goal_again_does_not_double_charge(self):
        expense = self._expense('-2000')
        spend_expense_from_goal(self.user, expense.id, self.meal.id)
        again = spend_expense_from_goal(self.user, expense.id, self.meal.id)
        self.assertTrue(again.ok)
        self.assertEqual(goal_balance(self.meal.id), Decimal('8000'))

    def test_switching_goals_returns_the_money(self):
        expense = self._expense('-2000', category=self.parts)
        spend_expense_from_goal(self.user, expense.id, self.meal.id)
        moved = spend_expense_from_goal(self.user, expense.id, self.car.id)
        self.assertTrue(moved.ok)
        self.assertEqual(goal_balance(self.meal.id), Decimal('10000'))
        self.assertEqual(goal_balance(self.car.id), Decimal('2000'))
        self.assertIn('Машина', goal_spend_note(expense.id))

    def test_short_goal_is_left_untouched(self):
        expense = self._expense('-5000')
        result = spend_expense_from_goal(self.user, expense.id, self.car.id)
        self.assertFalse(result.ok)
        self.assertIn('4,000', result.message)
        self.assertEqual(goal_balance(self.car.id), Decimal('4000'))
        self.assertEqual(goal_spend_note(expense.id), '')

    def test_income_cannot_come_out_of_a_goal(self):
        salary = Category.objects.create(
            user=self.user,
            name='Диана',
            type=Category.INCOME,
            icon='💰',
        )
        income = self._expense('5000', category=salary)
        result = spend_expense_from_goal(self.user, income.id, self.meal.id)
        self.assertFalse(result.ok)
        self.assertEqual(goal_balance(self.meal.id), Decimal('10000'))

    def test_free_funds_count_the_purchase_once(self):
        Transaction.objects.create(
            user=self.user,
            category=Category.objects.create(
                user=self.user,
                name='Зарплата',
                type=Category.INCOME,
                icon='💰',
            ),
            amount=Decimal('100000'),
            date=self.today,
        )
        expense = self._expense('-2000')
        spend_expense_from_goal(self.user, expense.id, self.meal.id)
        free = async_to_sync(GoalService(self.user).get_free_funds_for_month)(self.today)
        # 100 000 доход − 2 000 расход − (10 000 еда + 4 000 машина − 2 000 списание)
        self.assertEqual(free, Decimal('86000'))

    def test_deleting_the_expense_returns_the_goal_money(self):
        expense = self._expense('-2000')
        spend_expense_from_goal(self.user, expense.id, self.meal.id)
        deleted = async_to_sync(TransactionService(self.user).delete_transaction)(expense.id)
        self.assertTrue(deleted)
        self.assertEqual(goal_balance(self.meal.id), Decimal('10000'))

    def test_a_bigger_amount_has_to_fit_the_goal(self):
        expense = self._expense('-2000')
        spend_expense_from_goal(self.user, expense.id, self.car.id)
        service = TransactionService(self.user)
        with self.assertRaises(GoalSpendShortfall):
            async_to_sync(service.update_transaction_amount)(expense.id, Decimal('5000'))
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal('-2000'))
        self.assertEqual(goal_balance(self.car.id), Decimal('2000'))

        async_to_sync(service.update_transaction_amount)(expense.id, Decimal('3000'))
        self.assertEqual(goal_balance(self.car.id), Decimal('1000'))

    def test_moving_the_date_moves_the_goal_entry(self):
        expense = self._expense('-2000')
        spend_expense_from_goal(self.user, expense.id, self.meal.id)
        new_date = self.today - timedelta(days=40)
        async_to_sync(TransactionService(self.user).update_transaction_date)(
            expense.id,
            new_date,
        )
        entry = GoalLedgerEntry.objects.get(
            linked_transaction=expense,
            entry_type=GoalLedgerEntry.SPEND,
        )
        self.assertEqual(timezone.localtime(entry.occurred_at).date(), new_date)

    def test_expense_card_has_the_goal_button(self):
        with_goal = ActionKeyboard.get_transaction_actions_keyboard(5, from_goal=True)
        without = ActionKeyboard.get_transaction_actions_keyboard(5)
        with_data = [button.callback_data for row in with_goal.inline_keyboard for button in row]
        without_data = [button.callback_data for row in without.inline_keyboard for button in row]
        self.assertIn('tx_goal_5', with_data)
        self.assertNotIn('tx_goal_5', without_data)


class GoalSpendRouteTests(TestCase):
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

    async def test_the_button_opens_the_list_and_a_goal_is_a_separate_action(self):
        await self._bind('list', '_handle_tx_goal_list')
        await self._bind('pick', '_handle_tx_goal_pick')
        await self._bind('unknown', '_handle_unknown_callback')
        self.assertEqual(await self._route('tx_goal_5'), ['list'])
        self.assertEqual(await self._route('tx_goal_use_5_3'), ['pick'])
