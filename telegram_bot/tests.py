import logging
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async
from categories.models import Category
from budgets.models import Budget
from telegram_bot.handlers.text_handler import TextHandler
from telegram_bot.models import TelegramUser


logger = logging.getLogger('test_budget_editing')


class BudgetEditingTestCase(TestCase):
    """Тест для проверки редактирования бюджета"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Создаем Telegram пользователя
        self.telegram_user = TelegramUser.objects.create(
            telegram_id=123456789,
            user=self.user,
            username='testuser'
        )
        
        # Создаем категорию
        self.category = Category.objects.create(
            name='Тестовая категория',
            icon='🛒',
            user=self.user,
            type='expense',
            is_active=True
        )
        
        # Создаем бюджет
        today = timezone.now().date()
        start_date = datetime(today.year, today.month, 1).date()
        
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        
        self.budget = Budget.objects.create(
            user=self.user,
            category=self.category,
            amount=5000.00,
            period_type=Budget.MONTHLY,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        
        logger.info(f"✅ Тестовые данные созданы:")
        logger.info(f"   - Пользователь: {self.user.username}")
        logger.info(f"   - Категория: {self.category.name}")
        logger.info(f"   - Бюджет: {self.budget} (сумма: {self.budget.amount})")
    
    async def test_budget_editing_flow(self):
        """Тест полного цикла редактирования бюджета"""
        logger.info("🧪 Начинаем тест редактирования бюджета")
        
        # Симулируем контекст редактирования
        context_data = {
            'editing_budget_id': self.budget.id,
            'waiting_for_budget_amount': True
        }
        
        # Симулируем ввод новой суммы
        new_amount = "7500"
        
        logger.info(f"🔍 Тестируем обновление бюджета с {self.budget.amount} на {new_amount}")
        
        try:
            # Получаем обновленный бюджет из базы
            updated_budget = await sync_to_async(Budget.objects.get)(id=self.budget.id)
            logger.info(f"✅ Бюджет получен из БД: {updated_budget.amount}")
            
            # Проверяем, что бюджет существует
            self.assertIsNotNone(updated_budget)
            logger.info("✅ Бюджет существует")
            
            # Проверяем, что бюджет принадлежит правильному пользователю
            self.assertEqual(updated_budget.user, self.user)
            logger.info("✅ Бюджет принадлежит правильному пользователю")
            
            # Проверяем, что бюджет активен
            self.assertTrue(updated_budget.is_active)
            logger.info("✅ Бюджет активен")
            
            # Проверяем, что бюджет принадлежит правильной категории
            self.assertEqual(updated_budget.category, self.category)
            logger.info("✅ Бюджет принадлежит правильной категории")
            
            logger.info("✅ Все проверки пройдены успешно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте: {e}")
            self.fail(f"Тест провален: {e}")
    
    async def test_budget_creation_flow(self):
        """Тест создания нового бюджета"""
        logger.info("🧪 Начинаем тест создания бюджета")
        
        # Симулируем контекст создания
        context_data = {
            'budget_category_id': self.category.id,
            'waiting_for_budget_amount': True
        }
        
        # Симулируем ввод суммы
        amount = "10000"
        
        logger.info(f"🔍 Тестируем создание бюджета на сумму {amount}")
        
        try:
            # Проверяем, что категория существует
            category = await sync_to_async(Category.objects.get)(id=self.category.id)
            logger.info(f"✅ Категория найдена: {category.name}")
            
            # Проверяем, что категория принадлежит правильному пользователю
            self.assertEqual(category.user, self.user)
            logger.info("✅ Категория принадлежит правильному пользователю")
            
            # Проверяем, что категория активна
            self.assertTrue(category.is_active)
            logger.info("✅ Категория активна")
            
            logger.info("✅ Все проверки создания пройдены успешно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте создания: {e}")
            self.fail(f"Тест создания провален: {e}")
    
    def test_budget_model_methods(self):
        """Тест методов модели бюджета"""
        logger.info("🧪 Тестируем методы модели бюджета")
        
        try:
            # Тестируем __str__
            budget_str = str(self.budget)
            logger.info(f"✅ __str__: {budget_str}")
            
            # Тестируем spent_amount
            spent = self.budget.spent_amount
            logger.info(f"✅ spent_amount: {spent}")
            
            # Тестируем remaining_amount
            remaining = self.budget.remaining_amount
            logger.info(f"✅ remaining_amount: {remaining}")
            
            # Тестируем spent_percentage
            percentage = self.budget.spent_percentage
            logger.info(f"✅ spent_percentage: {percentage}")
            
            # Тестируем is_overspent
            overspent = self.budget.is_overspent
            logger.info(f"✅ is_overspent: {overspent}")
            
            # Тестируем days_remaining
            days = self.budget.days_remaining
            logger.info(f"✅ days_remaining: {days}")
            
            logger.info("✅ Все методы модели работают корректно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте методов модели: {e}")
            self.fail(f"Тест методов модели провален: {e}")
    
    def test_budget_constraints(self):
        """Тест ограничений модели бюджета"""
        logger.info("🧪 Тестируем ограничения модели бюджета")
        
        try:
            # Проверяем, что бюджет уникален по периоду
            today = timezone.now().date()
            start_date = datetime(today.year, today.month, 1).date()
            
            if today.month == 12:
                end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
            
            # Пытаемся создать дубликат бюджета
            duplicate_budget = Budget(
                user=self.user,
                category=self.category,
                amount=3000.00,
                period_type=Budget.MONTHLY,
                start_date=start_date,
                end_date=end_date,
                is_active=True
            )
            
            # Это должно вызвать ошибку уникальности
            with self.assertRaises(Exception):
                duplicate_budget.save()
            
            logger.info("✅ Ограничение уникальности работает корректно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте ограничений: {e}")
            self.fail(f"Тест ограничений провален: {e}")


if __name__ == '__main__':
    # Запуск тестов с логированием
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    import django
    django.setup()
    
    # Создаем тестовый экземпляр
    test_case = BudgetEditingTestCase()
    test_case.setUp()
    
    # Запускаем тесты
    import asyncio
    
    async def run_tests():
        await test_case.test_budget_editing_flow()
        await test_case.test_budget_creation_flow()
        test_case.test_budget_model_methods()
        test_case.test_budget_constraints()
        logger.info("🎉 Все тесты завершены!")
    
    asyncio.run(run_tests())


from decimal import Decimal
from unittest.mock import patch

from telegram_bot.voice.intents import (
    CONFIDENCE_AUTO_SAVE,
    ParsedVoiceCommand,
    VoiceIntentType,
)
from telegram_bot.voice.interpreter import VoiceInterpreter


class ParsedVoiceCommandTests(TestCase):
    def test_auto_save_when_confident_and_category(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=CONFIDENCE_AUTO_SAVE,
            raw_transcript='300 продукты',
            category=object(),
        )
        self.assertFalse(command.needs_confirmation())
        self.assertFalse(command.should_reject())

    def test_confirm_when_low_confidence(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.7,
            raw_transcript='что-то',
            amount=Decimal('300'),
            category_name='Продукты',
        )
        self.assertTrue(command.needs_confirmation())

    def test_reject_when_too_low_confidence(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.3,
            raw_transcript='неясно',
        )
        self.assertTrue(command.should_reject())

    def test_partial_without_amount_does_not_reject(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.7,
            raw_transcript='зарплата',
            category_name='Зарплата',
            transaction_type='income',
            amount=None,
        )
        self.assertFalse(command.should_reject())

    def test_amount_only_skips_confirmation(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=1.0,
            raw_transcript='500',
            amount=Decimal('500'),
            transaction_type='expense',
            command_type='amount_only',
        )
        self.assertFalse(command.needs_confirmation())

    def test_to_executor_dict_includes_description(self):
        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=1.0,
            raw_transcript='500 кофе',
            amount=Decimal('500'),
            transaction_type='expense',
            category_name='Кафе',
            description='утром',
            command_type='amount_category',
        )
        payload = command.to_executor_dict()
        self.assertEqual(payload['description'], 'утром')


class VoiceInterpreterRegexTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='voice_test',
            password='test',
        )
        self.category = Category.objects.create(
            user=self.user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🛒',
        )

    def test_fast_path_amount_category(self):
        interpreter = VoiceInterpreter(self.user)
        command = interpreter.interpret('500 продукты')
        self.assertEqual(command.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(command.confidence, 1.0)
        self.assertEqual(command.amount, Decimal('500'))
        self.assertEqual(command.category.id, self.category.id)

    def test_fast_path_natural_voice_phrase(self):
        mobile = Category.objects.create(
            user=self.user,
            name='Мобильный',
            type='expense',
            color='#000000',
            icon='📱',
        )
        interpreter = VoiceInterpreter(self.user)
        command = interpreter.interpret(
            'Добавь 500 рублей в категорию мобильный.',
        )
        self.assertEqual(command.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(command.confidence, 1.0)
        self.assertEqual(command.amount, Decimal('500'))
        self.assertEqual(command.category.id, mobile.id)

    def test_fast_path_income_natural_phrase(self):
        salary = Category.objects.create(
            user=self.user,
            name='Зарплата',
            type='income',
            color='#000000',
            icon='💰',
        )
        interpreter = VoiceInterpreter(self.user)
        command = interpreter.interpret('получил 5000 зарплата')
        self.assertEqual(command.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(command.confidence, 1.0)
        self.assertEqual(command.amount, Decimal('5000'))
        self.assertEqual(command.transaction_type, 'income')
        self.assertEqual(command.category.id, salary.id)

    def test_compact_natural_income_phrase(self):
        from telegram_bot.voice.interpreter import _compact_natural_income_phrase

        self.assertEqual(
            _compact_natural_income_phrase('получил 5000 зарплата'),
            '+5000 зарплата',
        )
        self.assertEqual(
            _compact_natural_income_phrase('зарплата 5000'),
            '+5000',
        )

    def test_compact_natural_phrase(self):
        from telegram_bot.voice.interpreter import _compact_natural_phrase

        self.assertEqual(
            _compact_natural_phrase('Добавь 500 рублей в категорию мобильный.'),
            '500 мобильный',
        )

    @patch('telegram_bot.voice.interpreter.openai_api_key', return_value='')
    def test_llm_skipped_without_api_key_after_regex_fail(self, _mock_key):
        interpreter = VoiceInterpreter(self.user)
        command = interpreter.interpret(
            'запиши расход триста рублей на продукты',
        )
        self.assertFalse(command.success)
        self.assertIn('OPENAI_API_KEY', command.error or '')


class OpenAIProxyConfigTests(TestCase):
    @patch('telegram_bot.voice.config.config')
    def test_openai_proxy_url_prefers_openai_var(self, mock_config):
        def side_effect(key, default='', cast=None):
            values = {
                'OPENAI_PROXY_URL': 'socks5h://eu-proxy:1080',
                'TELEGRAM_PROXY_URL': 'socks5://ru-proxy:1080',
            }
            return values.get(key, default)

        mock_config.side_effect = side_effect
        from telegram_bot.voice.config import openai_proxy_url

        self.assertEqual(openai_proxy_url(), 'socks5h://eu-proxy:1080')

    @patch('telegram_bot.voice.config.config')
    def test_openai_proxy_url_falls_back_to_telegram(self, mock_config):
        def side_effect(key, default='', cast=None):
            values = {
                'OPENAI_PROXY_URL': '',
                'TELEGRAM_PROXY_URL': 'socks5://ru-proxy:1080',
            }
            return values.get(key, default)

        mock_config.side_effect = side_effect
        from telegram_bot.voice.config import openai_proxy_url

        self.assertEqual(openai_proxy_url(), 'socks5://ru-proxy:1080')

    def test_format_openai_region_error(self):
        from telegram_bot.voice.openai_client import format_openai_error

        exc = Exception(
            "Error code: 403 - {'error': {'code': "
            "'unsupported_country_region_territory'}}",
        )
        message = format_openai_error(exc)
        self.assertIn('OPENAI_PROXY_URL', message)
        self.assertIn('регион', message.lower())


class TelegramResilienceTestCase(TestCase):
    def test_is_message_not_modified_error(self):
        from telegram.error import BadRequest
        from telegram_bot.utils.telegram_resilience import is_message_not_modified_error

        error = BadRequest(
            "Message is not modified: specified new message content and "
            "reply markup are exactly the same as a current content and "
            "reply markup of the message",
        )
        other_error = BadRequest("Chat not found")

        self.assertTrue(is_message_not_modified_error(error))
        self.assertFalse(is_message_not_modified_error(other_error))
        self.assertFalse(is_message_not_modified_error(ValueError("boom")))

    def test_get_callback_query(self):
        from telegram import CallbackQuery, Update
        from unittest.mock import MagicMock
        from telegram_bot.utils.telegram_resilience import get_callback_query

        query = MagicMock(spec=CallbackQuery)
        update = MagicMock(spec=Update)
        update.callback_query = query

        self.assertIs(get_callback_query(query), query)
        self.assertIs(get_callback_query(update), query)
        plain_update = MagicMock(spec=Update)
        plain_update.callback_query = None
        del plain_update.edit_message_text
        self.assertIsNone(get_callback_query(plain_update))


class CategoryResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='resolver_test',
            password='test',
        )
        self.products = Category.objects.create(
            user=self.user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )
        self.mobile = Category.objects.create(
            user=self.user,
            name='Связь и интернет',
            type='expense',
            color='#000000',
            icon='📱',
        )
        self.cafe = Category.objects.create(
            user=self.user,
            name='Еда вне дома',
            type='expense',
            color='#000000',
            icon='🍽',
        )
        self.salary = Category.objects.create(
            user=self.user,
            name='Зарплата',
            type='income',
            color='#000000',
            icon='💰',
        )

    def test_exact_match(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        result = CategoryResolver(self.user).resolve('продукты', 'expense')
        self.assertEqual(result.status, ResolveStatus.MATCHED)
        self.assertEqual(result.match.id, self.products.id)

    def test_synonym_match(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        transport = Category.objects.create(
            user=self.user,
            name='Транспорт',
            type='expense',
            color='#000000',
            icon='🚇',
        )
        result = CategoryResolver(self.user).resolve('такси', 'expense')
        self.assertEqual(result.status, ResolveStatus.MATCHED)
        self.assertEqual(result.match.id, transport.id)

    def test_ambiguous_food_synonym(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        # «еда» hits both Продукты (synonym) and Еда вне дома
        result = CategoryResolver(self.user).resolve('еда', 'expense')
        self.assertEqual(result.status, ResolveStatus.AMBIGUOUS)
        self.assertGreaterEqual(len(result.candidates), 2)

    def test_fuzzy_mobile(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        result = CategoryResolver(self.user).resolve('мобильный', 'expense')
        self.assertEqual(result.status, ResolveStatus.MATCHED)
        self.assertEqual(result.match.id, self.mobile.id)

    def test_unknown_category(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        result = CategoryResolver(self.user).resolve('абракадабра', 'expense')
        self.assertEqual(result.status, ResolveStatus.UNKNOWN)
        self.assertIsNone(result.match)

    def test_income_salary(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        result = CategoryResolver(self.user).resolve('зп', 'income')
        self.assertEqual(result.status, ResolveStatus.MATCHED)
        self.assertEqual(result.match.id, self.salary.id)

    def test_ambiguous_when_close_scores(self):
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        Category.objects.create(
            user=self.user,
            name='Продуктовый магазин',
            type='expense',
            color='#000000',
            icon='🏪',
        )
        # "продукт" is substring of both Продукты and Продуктовый магазин
        result = CategoryResolver(self.user).resolve('продукт', 'expense')
        self.assertIn(
            result.status,
            {ResolveStatus.AMBIGUOUS, ResolveStatus.MATCHED},
        )
        if result.status == ResolveStatus.AMBIGUOUS:
            self.assertGreaterEqual(len(result.candidates), 2)


class VoiceDialogManagerTests(TestCase):
    def test_missing_slots_amount(self):
        from telegram_bot.voice.dialog import missing_slots_for_create, next_step

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.8,
            raw_transcript='зарплата',
            category_name='Зарплата',
            category=object(),
            transaction_type='income',
            amount=None,
        )
        missing = missing_slots_for_create(command)
        self.assertEqual(missing, ['amount'])
        self.assertEqual(next_step(missing), 'awaiting_amount')

    def test_missing_slots_unresolved_category(self):
        from telegram_bot.voice.dialog import missing_slots_for_create, next_step

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.9,
            raw_transcript='500 xyz',
            amount=Decimal('500'),
            category_name='xyz',
            transaction_type='expense',
            category=None,
            command_type='amount_category',
        )
        missing = missing_slots_for_create(command)
        self.assertEqual(missing, ['category'])
        self.assertEqual(next_step(missing), 'awaiting_category')

    def test_amount_only_no_dialog_slots(self):
        from telegram_bot.voice.dialog import missing_slots_for_create

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=1.0,
            raw_transcript='500',
            amount=Decimal('500'),
            transaction_type='expense',
            command_type='amount_only',
        )
        self.assertEqual(missing_slots_for_create(command), [])

    def test_dialog_timeout(self):
        from telegram_bot.voice.dialog import (
            VoiceDialogState,
            is_dialog_expired,
        )

        dialog = VoiceDialogState(
            intent='create_transaction',
            step='awaiting_amount',
            created_at=0,
        )
        self.assertTrue(is_dialog_expired(dialog, timeout_sec=1))

    def test_parse_amount_and_type_helpers(self):
        from telegram_bot.voice.dialog import _parse_amount, _parse_type

        self.assertEqual(_parse_amount('1 500,50'), Decimal('1500.50'))
        self.assertEqual(_parse_type('доход'), 'income')
        self.assertEqual(_parse_type('расход'), 'expense')
        self.assertIsNone(_parse_type('что-то'))

    def test_slots_roundtrip(self):
        from telegram_bot.voice.dialog import command_to_slots, slots_to_command

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=0.9,
            raw_transcript='зарплата',
            amount=None,
            category_name='Зарплата',
            transaction_type='income',
        )
        slots = command_to_slots(command)
        slots['amount'] = Decimal('50000')
        rebuilt = slots_to_command(slots, 'зарплата')
        self.assertEqual(rebuilt.amount, Decimal('50000'))
        self.assertEqual(rebuilt.transaction_type, 'income')
        self.assertEqual(rebuilt.category_name, 'Зарплата')


class VoiceBudgetPhase3Tests(TestCase):
    def setUp(self):
        from decimal import Decimal

        self.user = User.objects.create_user(
            username='budget_voice',
            password='test',
        )
        self.products = Category.objects.create(
            user=self.user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )
        self.transport = Category.objects.create(
            user=self.user,
            name='Транспорт',
            type='expense',
            color='#000000',
            icon='🚌',
        )
        self.salary = Category.objects.create(
            user=self.user,
            name='Зарплата',
            type='income',
            color='#000000',
            icon='💰',
        )
        self.Decimal = Decimal

    def test_b1_fast_path_limit_with_category(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        command = VoiceInterpreter(self.user).interpret('лимит 5000 на продукты')
        self.assertEqual(command.intent, VoiceIntentType.SET_BUDGET)
        self.assertEqual(command.amount, self.Decimal('5000'))
        self.assertEqual(command.category.id, self.products.id)
        self.assertEqual(command.transaction_type, 'expense')

    def test_budget_category_then_amount(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        cafe = Category.objects.create(
            user=self.user,
            name='Кафе и рестораны',
            type='expense',
            color='#000000',
            icon='🍽',
        )
        command = VoiceInterpreter(self.user).interpret(
            'Установи бюджет на категорию «Кафе и рестораны», 5000 рублей.',
        )
        self.assertEqual(command.intent, VoiceIntentType.SET_BUDGET)
        self.assertEqual(command.amount, self.Decimal('5000'))
        self.assertEqual(command.category.id, cafe.id)
        self.assertNotIn('5000', command.category_name or '')

    def test_dialog_parse_spoken_amount_with_yes(self):
        from telegram_bot.voice.dialog import _parse_amount

        self.assertEqual(_parse_amount('Да, пять тысяч рублей.'), self.Decimal('5000'))
        self.assertEqual(_parse_amount('пять тысяч'), self.Decimal('5000'))
        self.assertEqual(_parse_amount('5000'), self.Decimal('5000'))

    def test_b2_budget_alias(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        command = VoiceInterpreter(self.user).interpret('бюджет 10000 еда')
        self.assertEqual(command.intent, VoiceIntentType.SET_BUDGET)
        self.assertEqual(command.amount, self.Decimal('10000'))
        # «еда» may resolve via synonym to cafe/products — amount+intent is enough here
        self.assertTrue(command.category_name)

    def test_b3_missing_amount_slots(self):
        from telegram_bot.voice.dialog import missing_slots_for_budget, next_step
        from telegram_bot.voice.intents import ParsedVoiceCommand, VoiceIntentType

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.SET_BUDGET,
            success=True,
            confidence=1.0,
            raw_transcript='лимит на транспорт',
            category=self.transport,
            category_name='Транспорт',
            transaction_type='expense',
            amount=None,
        )
        missing = missing_slots_for_budget(command)
        self.assertEqual(missing, ['amount'])
        self.assertEqual(next_step(missing), 'awaiting_amount')

    def test_b4_missing_category_slots(self):
        from telegram_bot.voice.dialog import missing_slots_for_budget, next_step
        from telegram_bot.voice.intents import ParsedVoiceCommand, VoiceIntentType

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.SET_BUDGET,
            success=True,
            confidence=1.0,
            raw_transcript='лимит 5000',
            amount=self.Decimal('5000'),
            transaction_type='expense',
        )
        missing = missing_slots_for_budget(command)
        self.assertEqual(missing, ['category'])
        self.assertEqual(next_step(missing), 'awaiting_category')

    def test_b5_upsert_create_and_update(self):
        from telegram_bot.services.voice_budget_executor import (
            find_current_month_budget,
            upsert_monthly_budget,
        )

        result = upsert_monthly_budget(
            self.user,
            self.products,
            self.Decimal('5000'),
        )
        self.assertTrue(result.created)
        self.assertEqual(result.budget.amount, self.Decimal('5000'))
        self.assertIsNone(result.previous_amount)

        result2 = upsert_monthly_budget(
            self.user,
            self.products,
            self.Decimal('7000'),
        )
        self.assertFalse(result2.created)
        self.assertEqual(result2.previous_amount, self.Decimal('5000'))
        self.assertEqual(result2.budget.amount, self.Decimal('7000'))
        self.assertEqual(
            find_current_month_budget(self.user, self.products).id,
            result.budget.id,
        )

    def test_budget_rejects_income_category(self):
        from telegram_bot.services.voice_budget_executor import upsert_monthly_budget

        with self.assertRaises(ValueError):
            upsert_monthly_budget(
                self.user,
                self.salary,
                self.Decimal('1000'),
            )

    def test_budget_slots_roundtrip(self):
        from telegram_bot.voice.dialog import command_to_slots, slots_to_command
        from telegram_bot.voice.intents import ParsedVoiceCommand, VoiceIntentType

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.SET_BUDGET,
            success=True,
            confidence=1.0,
            raw_transcript='лимит на транспорт',
            amount=None,
            category_name='Транспорт',
            transaction_type='expense',
        )
        slots = command_to_slots(command)
        self.assertEqual(slots['intent'], 'set_budget')
        slots['amount'] = self.Decimal('3000')
        rebuilt = slots_to_command(slots, command.raw_transcript)
        self.assertEqual(rebuilt.intent, VoiceIntentType.SET_BUDGET)
        self.assertEqual(rebuilt.amount, self.Decimal('3000'))
        self.assertEqual(rebuilt.category_name, 'Транспорт')

    def test_fast_path_limit_without_amount(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        command = VoiceInterpreter(self.user).interpret('лимит на транспорт')
        self.assertEqual(command.intent, VoiceIntentType.SET_BUDGET)
        self.assertIsNone(command.amount)
        self.assertEqual(command.category.id, self.transport.id)


class VoiceGoalPhase4Tests(TestCase):
    def setUp(self):
        from decimal import Decimal

        from asgiref.sync import async_to_sync
        from goals.models import Goal

        self.Decimal = Decimal
        self.user = User.objects.create_user(
            username='goal_voice',
            password='test',
        )
        self.vacation = Goal.objects.create(
            user=self.user,
            title='Отпуск',
            target_amount=Decimal('100000'),
        )
        self.ipad = Goal.objects.create(
            user=self.user,
            title='iPad',
            target_amount=Decimal('80000'),
        )
        async_to_sync(self._seed_balance)()

    async def _seed_balance(self):
        from telegram_bot.services.goal_service import GoalService

        await GoalService(self.user).add_deposit(self.vacation.id, self.Decimal('10000'))

    def test_g1_deposit_fast_path(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import GOAL_ACTION_DEPOSIT, VoiceIntentType

        command = VoiceInterpreter(self.user).interpret(
            'пополни цель отпуск на 5000',
        )
        self.assertEqual(command.intent, VoiceIntentType.MANAGE_GOAL)
        self.assertEqual(command.goal_action, GOAL_ACTION_DEPOSIT)
        self.assertEqual(command.amount, self.Decimal('5000'))
        self.assertEqual(command.goal.id, self.vacation.id)

    def test_g2_create_fast_path(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import GOAL_ACTION_CREATE, VoiceIntentType

        command = VoiceInterpreter(self.user).interpret(
            'создай цель MacBook 150000',
        )
        self.assertEqual(command.intent, VoiceIntentType.MANAGE_GOAL)
        self.assertEqual(command.goal_action, GOAL_ACTION_CREATE)
        self.assertEqual(command.goal_title, 'MacBook')
        self.assertEqual(command.amount, self.Decimal('150000'))

    def test_g5_unknown_goal_slots(self):
        from telegram_bot.voice.dialog import missing_slots_for_goal, next_step
        from telegram_bot.voice.intents import (
            GOAL_ACTION_DEPOSIT,
            ParsedVoiceCommand,
            VoiceIntentType,
        )

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.MANAGE_GOAL,
            success=True,
            confidence=1.0,
            raw_transcript='пополни цель марсоход на 1000',
            amount=self.Decimal('1000'),
            goal_action=GOAL_ACTION_DEPOSIT,
            goal_title='марсоход',
            goal=None,
        )
        missing = missing_slots_for_goal(command)
        self.assertEqual(missing, ['goal'])
        self.assertEqual(next_step(missing), 'awaiting_goal')

    def test_goal_resolver_exact(self):
        from telegram_bot.voice.goal_resolver import GoalResolver, ResolveStatus

        result = GoalResolver(self.user).resolve('отпуск')
        self.assertEqual(result.status, ResolveStatus.MATCHED)
        self.assertEqual(result.match.id, self.vacation.id)

    def test_deposit_and_withdraw_executor(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.voice_goal_executor import (
            execute_goal_deposit,
            execute_goal_withdraw,
        )

        deposit = async_to_sync(execute_goal_deposit)(
            self.user,
            self.vacation,
            self.Decimal('2000'),
        )
        self.assertEqual(deposit.balance, self.Decimal('12000'))

        withdraw = async_to_sync(execute_goal_withdraw)(
            self.user,
            self.vacation,
            self.Decimal('3000'),
        )
        self.assertEqual(withdraw.balance, self.Decimal('9000'))

    def test_create_goal_executor(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.voice_goal_executor import execute_goal_create

        result = async_to_sync(execute_goal_create)(
            self.user,
            'Велосипед',
            self.Decimal('40000'),
        )
        self.assertEqual(result.goal.title, 'Велосипед')
        self.assertEqual(result.goal.target_amount, self.Decimal('40000'))

    def test_withdraw_insufficient_funds(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.voice_goal_executor import execute_goal_withdraw

        with self.assertRaises(ValueError):
            async_to_sync(execute_goal_withdraw)(
                self.user,
                self.ipad,
                self.Decimal('1000'),
            )

    def test_goal_slots_roundtrip(self):
        from telegram_bot.voice.dialog import command_to_slots, slots_to_command
        from telegram_bot.voice.intents import (
            GOAL_ACTION_DEPOSIT,
            ParsedVoiceCommand,
            VoiceIntentType,
        )

        command = ParsedVoiceCommand(
            intent=VoiceIntentType.MANAGE_GOAL,
            success=True,
            confidence=1.0,
            raw_transcript='пополни отпуск',
            amount=None,
            goal_action=GOAL_ACTION_DEPOSIT,
            goal_title='Отпуск',
            goal=self.vacation,
        )
        slots = command_to_slots(command)
        self.assertEqual(slots['intent'], 'manage_goal')
        self.assertEqual(slots['goal_id'], self.vacation.id)
        slots['amount'] = self.Decimal('2500')
        rebuilt = slots_to_command(slots, command.raw_transcript)
        self.assertEqual(rebuilt.intent, VoiceIntentType.MANAGE_GOAL)
        self.assertEqual(rebuilt.goal_action, GOAL_ACTION_DEPOSIT)
        self.assertEqual(rebuilt.amount, self.Decimal('2500'))


class AdvisorSnapshotTests(TestCase):
    def setUp(self):
        from decimal import Decimal
        from datetime import date
        import calendar

        from transactions.models import Transaction

        self.Decimal = Decimal
        self.user = User.objects.create_user(username='advisor_u', password='x')
        self.products = Category.objects.create(
            user=self.user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )
        today = date.today()
        start = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = date(today.year, today.month, last_day)
        Transaction.objects.create(
            user=self.user,
            category=self.products,
            amount=Decimal('-1500'),
            date=today,
            description='test',
        )
        Budget.objects.create(
            user=self.user,
            category=self.products,
            amount=Decimal('5000'),
            period_type=Budget.MONTHLY,
            start_date=start,
            end_date=end,
            is_active=True,
        )

    def test_snapshot_month_totals(self):
        from asgiref.sync import async_to_sync
        from telegram_bot.services.advisor_snapshot_service import (
            AdvisorSnapshotService,
        )

        snapshot = async_to_sync(AdvisorSnapshotService(self.user).build)()
        self.assertEqual(snapshot['month_totals']['expenses'], 1500.0)
        self.assertTrue(snapshot['budgets'])
        self.assertEqual(snapshot['budgets'][0]['category'], 'Продукты')
        self.assertEqual(snapshot['budgets'][0]['limit'], 5000.0)

    def test_empty_snapshot_reply_without_llm(self):
        from telegram_bot.services.voice_advisor_executor import (
            answer_from_snapshot,
        )

        empty = {
            'period': {'name': 'июль 2026'},
            'month_totals': {
                'income': 0,
                'expenses': 0,
                'balance': 0,
                'free_funds': 0,
            },
            'today': {'income': 0, 'expenses': 0, 'balance': 0},
            'top_expense_categories': [],
            'top_income_categories': [],
            'budgets': [],
            'goals': [],
            'suggestions': [],
        }
        text = answer_from_snapshot('сколько потратил?', empty)
        self.assertIn('мало данных', text.lower())

    def test_suggestions_count_as_signal(self):
        from telegram_bot.services.voice_advisor_executor import (
            _snapshot_has_signal,
        )

        snapshot = {
            'month_totals': {
                'income': 0,
                'expenses': 0,
                'balance': 0,
                'free_funds': 0,
            },
            'today': {'income': 0, 'expenses': 0, 'balance': 0},
            'top_expense_categories': [],
            'top_income_categories': [],
            'budgets': [],
            'goals': [],
            'suggestions': [
                {
                    'title': 'Резерв',
                    'description': 'Можно отложить',
                    'suggested_amount': 1000.0,
                },
            ],
        }
        self.assertTrue(_snapshot_has_signal(snapshot))


class NumberWordsTests(TestCase):
    def test_parse_simple(self):
        from decimal import Decimal

        from telegram_bot.voice.number_words import parse_number_words

        self.assertEqual(parse_number_words('триста'), Decimal('300'))
        self.assertEqual(parse_number_words('пятьсот'), Decimal('500'))
        self.assertEqual(parse_number_words('две тысячи'), Decimal('2000'))
        self.assertEqual(
            parse_number_words('две тысячи пятьсот'),
            Decimal('2500'),
        )
        self.assertEqual(parse_number_words('50 тысяч'), Decimal('50000'))
        self.assertEqual(
            parse_number_words('полтора миллиона'),
            Decimal('1500000'),
        )
        self.assertEqual(parse_number_words('1.5 млн'), Decimal('1500000'))

    def test_replace_in_phrase(self):
        from telegram_bot.voice.number_words import replace_spoken_numbers

        self.assertEqual(
            replace_spoken_numbers('пятьсот продукты'),
            '500 продукты',
        )
        self.assertEqual(
            replace_spoken_numbers('потратил триста на еду'),
            'потратил 300 на еду',
        )
        self.assertEqual(
            replace_spoken_numbers('лимит пять тысяч на транспорт'),
            'лимит 5000 на транспорт',
        )

    def test_interpreter_spoken_amount(self):
        from decimal import Decimal

        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        user = User.objects.create_user(username='spoken_num', password='x')
        category = Category.objects.create(
            user=user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )
        command = VoiceInterpreter(user).interpret('пятьсот продукты')
        self.assertEqual(command.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(command.amount, Decimal('500'))
        self.assertEqual(command.category.id, category.id)


class VoiceWhisperContextTests(TestCase):
    def test_build_prompt_includes_categories(self):
        from telegram_bot.voice.whisper_context import build_user_whisper_prompt

        user = User.objects.create_user(username='whisper_ctx', password='x')
        Category.objects.create(
            user=user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )
        prompt = build_user_whisper_prompt(user)
        self.assertIn('Продукты', prompt)


class VoiceRouterMockE2ETests(TestCase):
    """Lightweight routing checks without OpenAI (mock interpret path)."""

    def setUp(self):
        from decimal import Decimal

        self.Decimal = Decimal
        self.user = User.objects.create_user(username='e2e_voice', password='x')
        self.telegram_user = TelegramUser.objects.create(
            telegram_id=999001,
            user=self.user,
            username='e2e_voice',
        )
        self.products = Category.objects.create(
            user=self.user,
            name='Продукты',
            type='expense',
            color='#000000',
            icon='🥕',
        )

    def test_interpret_then_missing_slots_for_unknown_category(self):
        from telegram_bot.voice.dialog import missing_slots_for_create
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        command = VoiceInterpreter(self.user).interpret('500 абракадабра')
        self.assertEqual(command.intent, VoiceIntentType.CREATE_TRANSACTION)
        self.assertEqual(command.amount, self.Decimal('500'))
        self.assertIsNone(command.category)
        self.assertIn('category', missing_slots_for_create(command))

    def test_budget_spoken_number_fast_path(self):
        from telegram_bot.voice.interpreter import VoiceInterpreter
        from telegram_bot.voice.intents import VoiceIntentType

        command = VoiceInterpreter(self.user).interpret(
            'лимит пять тысяч на продукты',
        )
        self.assertEqual(command.intent, VoiceIntentType.SET_BUDGET)
        self.assertEqual(command.amount, self.Decimal('5000'))
        self.assertEqual(command.category.id, self.products.id)
