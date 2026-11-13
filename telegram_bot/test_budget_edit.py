from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from budgets.models import Budget
from categories.models import Category
from telegram_bot.handlers.text_handler import TextHandler
from telegram_bot.models import TelegramUser


class BudgetAmountEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='budget-edit', password='x')
        self.telegram_user = TelegramUser.objects.create(
            user=self.user,
            telegram_id=424242,
            username='budget-edit',
        )
        self.category = Category.objects.create(
            user=self.user,
            name='Кафе и рестораны',
            type=Category.EXPENSE,
            icon='☕',
        )
        today = timezone.now().date()
        start = today.replace(day=1)
        if today.month == 12:
            end = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=Decimal('3000.00'),
            period_type=Budget.MONTHLY,
            start_date=start,
            end_date=end,
        )

    async def test_editing_amount_saves_without_an_async_orm_call(self):
        handler = TextHandler()
        update = MagicMock()
        update.effective_chat.id = 1
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.user_data = {'editing_budget_id': self.budget.id}
        context.bot.send_message = AsyncMock()

        await handler._handle_budget_amount_input(
            update,
            context,
            self.telegram_user,
            '8000',
        )

        await self.budget.arefresh_from_db()
        self.assertEqual(self.budget.amount, Decimal('8000.00'))
        self.assertNotIn('editing_budget_id', context.user_data)
        context.bot.send_message.assert_not_called()
        update.message.reply_text.assert_awaited()
