"""Короткое меню категорий: ручной выбор или шесть частых за 30 дней."""

from datetime import date, timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.test import TestCase

from categories.models import Category
from telegram_bot.keyboards.categories import CategoryKeyboard
from telegram_bot.models import TelegramUser
from telegram_bot.services.category_management_service import CategoryManagementService
from telegram_bot.services.quick_categories import (
    QUICK_MENU_SIZE,
    clear_quick,
    drop_quick_if_type_is_full,
    select_quick_categories,
    toggle_quick,
)
from transactions.models import Transaction


class QuickCategoryMenuTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='quick-user', password='x')
        self.today = date(2026, 10, 26)
        self.names = [
            'Еда',
            'Аренда',
            'Кафе',
            'Одежда',
            'Хобби',
            'Бета',
            'Старое',
            'Ягоды',
        ]
        self.categories = {
            name: Category.objects.create(
                user=self.user,
                name=name,
                type=Category.EXPENSE,
                icon='•',
            )
            for name in self.names
        }

    def _spend(self, name: str, when: date, times: int = 1) -> None:
        for _ in range(times):
            Transaction.objects.create(
                user=self.user,
                category=self.categories[name],
                amount=Decimal('-100'),
                date=when,
            )

    def _names(self) -> list[str]:
        menu = select_quick_categories(self.user, Category.EXPENSE, self.today)
        return [category.name for category in menu.categories]

    def test_top_six_come_from_the_last_thirty_days(self):
        self._spend('Еда', self.today, 5)
        self._spend('Аренда', self.today, 4)
        self._spend('Кафе', self.today, 3)
        self._spend('Одежда', self.today, 2)
        self._spend('Хобби', self.today, 2)
        self._spend('Старое', self.today - timedelta(days=40), 10)

        menu = select_quick_categories(self.user, Category.EXPENSE, self.today)

        self.assertFalse(menu.manual)
        self.assertEqual(menu.total_active, 8)
        self.assertEqual(
            self._names(),
            ['Еда', 'Аренда', 'Кафе', 'Одежда', 'Хобби', 'Бета'],
        )
        self.assertNotIn('Старое', self._names())

    def test_window_includes_the_day_thirty_days_ago(self):
        edge = self.today - timedelta(days=29)
        self._spend('Ягоды', edge, 1)

        self.assertEqual(self._names()[0], 'Ягоды')

    def test_manual_pins_replace_frequency_and_are_not_padded(self):
        self._spend('Еда', self.today, 5)
        self.categories['Ягоды'].is_quick = True
        self.categories['Ягоды'].save(update_fields=['is_quick'])

        menu = select_quick_categories(self.user, Category.EXPENSE, self.today)

        self.assertTrue(menu.manual)
        self.assertEqual([category.name for category in menu.categories], ['Ягоды'])

    def test_archived_pin_does_not_stay_in_the_menu(self):
        self.categories['Еда'].is_quick = True
        self.categories['Еда'].is_active = False
        self.categories['Еда'].save(update_fields=['is_quick', 'is_active'])
        self._spend('Кафе', self.today, 1)

        menu = select_quick_categories(self.user, Category.EXPENSE, self.today)

        self.assertFalse(menu.manual)
        self.assertNotIn('Еда', [category.name for category in menu.categories])
        self.assertEqual(menu.categories[0].name, 'Кафе')

    def test_other_user_operations_do_not_count(self):
        other = User.objects.create_user(username='other-quick', password='x')
        foreign = Category.objects.create(
            user=other,
            name='Чужое',
            type=Category.EXPENSE,
            icon='•',
        )
        Transaction.objects.create(
            user=other,
            category=foreign,
            amount=Decimal('-100'),
            date=self.today,
        )
        self._spend('Кафе', self.today, 1)

        self.assertEqual(self._names()[0], 'Кафе')

    def test_seventh_pin_is_refused(self):
        for name in ['Еда', 'Аренда', 'Кафе', 'Одежда', 'Хобби', 'Бета']:
            category, error = toggle_quick(self.user, self.categories[name].id)
            self.assertIsNone(error)
            self.assertTrue(category.is_quick)

        category, error = toggle_quick(self.user, self.categories['Ягоды'].id)

        self.assertEqual(error, 'В меню уже шесть. Снимите одну, чтобы поставить эту.')
        category.refresh_from_db()
        self.assertFalse(category.is_quick)
        self.assertEqual(
            Category.objects.filter(user=self.user, is_quick=True).count(),
            QUICK_MENU_SIZE,
        )

    def test_clear_returns_the_menu_to_frequency(self):
        self._spend('Кафе', self.today, 3)
        toggle_quick(self.user, self.categories['Ягоды'].id)

        clear_quick(self.user, Category.EXPENSE)
        menu = select_quick_categories(self.user, Category.EXPENSE, self.today)

        self.assertFalse(menu.manual)
        self.assertEqual(menu.categories[0].name, 'Кафе')

    def test_type_change_drops_the_pin_when_the_new_side_is_full(self):
        for index in range(QUICK_MENU_SIZE):
            Category.objects.create(
                user=self.user,
                name=f'Доход {index}',
                type=Category.INCOME,
                icon='•',
                is_quick=True,
            )
        expense = self.categories['Еда']
        expense.is_quick = True
        expense.save(update_fields=['is_quick'])

        dropped = drop_quick_if_type_is_full(self.user, expense, Category.INCOME)

        self.assertTrue(dropped)
        self.assertFalse(expense.is_quick)

    def test_restore_drops_the_pin_when_six_are_already_marked(self):
        for name in ['Аренда', 'Кафе', 'Одежда', 'Хобби', 'Бета', 'Ягоды']:
            toggle_quick(self.user, self.categories[name].id)
        food = self.categories['Еда']
        food.is_quick = True
        food.save(update_fields=['is_quick'])
        service = CategoryManagementService(self.user)
        async_to_sync(service.archive_category)(food.id)

        restored = async_to_sync(service.restore_category)(food.id)

        self.assertTrue(restored.is_active)
        self.assertFalse(restored.is_quick)

    def test_keyboard_offers_the_rest_behind_one_button(self):
        telegram_user = TelegramUser.objects.create(user=self.user, telegram_id=501)
        self._spend('Еда', self.today, 1)
        keyboard = CategoryKeyboard(telegram_user)

        markup = async_to_sync(keyboard.get_frequent_categories_keyboard)('expense')
        labels = [button.text for row in markup.inline_keyboard for button in row]
        callbacks = [
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        ]

        self.assertIn('📋 Все категории', labels)
        self.assertIn('all_categories_expense', callbacks)
        self.assertEqual(
            sum(1 for callback in callbacks if callback.startswith('category_')),
            QUICK_MENU_SIZE,
        )

    def test_keyboard_hides_show_all_when_everything_fits(self):
        Category.objects.filter(user=self.user).exclude(name='Еда').delete()
        telegram_user = TelegramUser.objects.create(user=self.user, telegram_id=502)
        keyboard = CategoryKeyboard(telegram_user)

        markup = async_to_sync(keyboard.get_frequent_categories_keyboard)('expense')
        labels = [button.text for row in markup.inline_keyboard for button in row]

        self.assertNotIn('📋 Все категории', labels)
        self.assertIn('• Еда', labels)

    def test_full_list_is_paged_and_can_return(self):
        for index in range(4):
            Category.objects.create(
                user=self.user,
                name=f'Ещё {index}',
                type=Category.EXPENSE,
                icon='•',
            )
        telegram_user = TelegramUser.objects.create(user=self.user, telegram_id=503)
        keyboard = CategoryKeyboard(telegram_user)

        first = async_to_sync(keyboard.get_categories_keyboard)('expense', 0)
        callbacks = [
            button.callback_data
            for row in first.inline_keyboard
            for button in row
        ]

        self.assertIn('page_expense_1', callbacks)
        self.assertIn('quick_back_expense', callbacks)
        self.assertLessEqual(
            sum(1 for callback in callbacks if callback.startswith('category_')),
            10,
        )
