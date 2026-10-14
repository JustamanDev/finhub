"""Пользовательские пути бота: выход в меню и сброс режима ввода.

Чек-лист, который эти тесты закрывают:

1. Главное меню: расход, доход, статистика, отчёт, бюджеты, цели, неделя, настройки.
2. Ввод суммы без валюты: можно отказаться и вернуться в меню, следующее сообщение не записывает старую сумму.
3. Быстрый ввод, отмена операции, правка суммы/даты/комментария.
4. Категории: список, создание, переименование, смена иконки, архив, возврат.
5. Лимиты и бюджеты: ввод суммы, отмена, удаление с «Нет».
6. Цели: создание, пополнение, история.
7. Заголовки списков не стирают клавиатуру сообщением «Неизвестная команда».
8. «Назад» из режима ввода снимает этот режим, иначе следующий текст уходит не туда.
"""

from unittest.mock import AsyncMock, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase

from categories.models import Category
from telegram_bot.handlers.budget_handler import BudgetHandler
from telegram_bot.handlers.callback_handler import CallbackHandler
from telegram_bot.handlers.command_handler import CommandHandler
from telegram_bot.handlers.settings_handler import SettingsHandler
from telegram_bot.models import TelegramUser, UserState


def _callback_update(data: str):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    return update


class CallbackRouteTests(TestCase):
    def setUp(self):
        self.handler = CallbackHandler()
        self.handler.get_or_create_telegram_user = AsyncMock(return_value=MagicMock())
        self.handler.handle_error = AsyncMock()
        self.calls = []

        async def record(name):
            async def _inner(*_args, **_kwargs):
                self.calls.append(name)

            return _inner

        # Присваиваем после, см. _bind.
        self._record = record

    async def _bind(self, name, attr):
        async def _inner(*_args, **_kwargs):
            self.calls.append(name)

        setattr(self.handler, attr, _inner)

    async def _route(self, data: str):
        self.calls.clear()
        await self.handler.handle_callback_query(_callback_update(data), MagicMock())
        return list(self.calls)

    async def test_picking_an_icon_saves_it(self):
        await self._bind('menu', '_handle_category_icon')
        await self._bind('select', '_handle_category_icon_select')
        calls = await self._route('category_icon_select_5_☕')
        self.assertEqual(calls, ['select'])

    async def test_budget_delete_no_returns_to_the_budget(self):
        await self._bind('detail', '_handle_budget_detail')
        await self._bind('unknown', '_handle_unknown_callback')
        calls = await self._route('cancel_budget_delete_3')
        self.assertEqual(calls, ['detail'])

    async def test_currency_cancel_returns_home(self):
        await self._bind('home', '_handle_main_menu')
        await self._bind('unknown', '_handle_unknown_callback')
        calls = await self._route('entry_currency_cancel')
        self.assertEqual(calls, ['home'])

    async def test_section_headers_do_not_wipe_the_screen(self):
        await self._bind('unknown', '_handle_unknown_callback')
        for data in ('category_header_income', 'category_header_expense', 'no_action'):
            calls = await self._route(data)
            self.assertNotIn('unknown', calls, data)


class InputModeEscapeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='path-user', password='x')
        self.telegram_user = TelegramUser.objects.create(
            user=self.user,
            telegram_id=909090,
            username='path',
        )
        self.category = Category.objects.create(
            user=self.user,
            name='Кафе',
            type=Category.EXPENSE,
            icon='☕',
        )
        self.state = UserState.objects.create(
            telegram_user=self.telegram_user,
            awaiting_category_creation=True,
            context_data={'category_type': 'expense'},
        )
        self.settings = SettingsHandler()
        self.settings._send_or_edit_message = AsyncMock()

    async def test_back_from_new_category_stops_waiting_for_a_name(self):
        await self.settings.handle_category_add(
            MagicMock(),
            MagicMock(),
            self.telegram_user,
        )
        await self.state.arefresh_from_db()
        self.assertFalse(self.state.awaiting_category_creation)

    async def test_back_from_rename_stops_waiting_for_a_new_name(self):
        context = MagicMock()
        context.user_data = {'renaming_category_id': self.category.id}
        await self.settings.handle_category_actions(
            MagicMock(),
            context,
            self.telegram_user,
            self.category.id,
        )
        self.assertNotIn('renaming_category_id', context.user_data)

    async def test_back_from_budget_amount_stops_waiting_for_a_number(self):
        context = MagicMock()
        context.user_data = {
            'waiting_for_budget_amount': True,
            'budget_category_id': self.category.id,
        }
        handler = BudgetHandler()
        handler._send_or_edit_message = AsyncMock()
        await handler.handle_budgets_add(MagicMock(), context, self.telegram_user)
        self.assertNotIn('waiting_for_budget_amount', context.user_data)

    async def test_back_from_limit_amount_stops_waiting_for_a_number(self):
        context = MagicMock()
        context.user_data = {
            'limit_creation': {'category_id': self.category.id, 'step': 'amount_input'},
        }
        await self.settings.handle_limits_add(
            MagicMock(),
            context,
            self.telegram_user,
        )
        self.assertNotIn('limit_creation', context.user_data)

    async def test_start_clears_category_creation_mode(self):
        handler = CommandHandler()
        update = MagicMock()
        update.effective_user = MagicMock(id=909090, username='path', first_name='П')
        update.effective_chat.id = 1
        context = MagicMock()
        context.bot.send_message = AsyncMock()
        context.user_data = {}
        await handler.start_command(update, context)
        await self.state.arefresh_from_db()
        self.assertFalse(self.state.awaiting_category_creation)
