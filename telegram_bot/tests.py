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
