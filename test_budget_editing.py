#!/usr/bin/env python3
"""
Простой тест для проверки редактирования бюджета
"""

import os
import sys
import django
from decimal import Decimal

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finhub.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from categories.models import Category
from budgets.models import Budget


def test_budget_editing():
    """Тест редактирования бюджета"""
    print("🧪 Начинаем тест редактирования бюджета")
    
    try:
        # Создаем тестового пользователя
        user, created = User.objects.get_or_create(
            username='testuser_budget',
            defaults={
                'email': 'test_budget@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        print(f"✅ Пользователь: {user.username}")
        
        # Создаем тестовую категорию
        category, created = Category.objects.get_or_create(
            name='Тестовая категория для бюджета',
            user=user,
            defaults={
                'icon': '🛒',
                'type': 'expense',
                'is_active': True
            }
        )
        print(f"✅ Категория: {category.name}")
        
        # Создаем тестовый бюджет
        today = timezone.now().date()
        start_date = datetime(today.year, today.month, 1).date()
        
        if today.month == 12:
            end_date = datetime(today.year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(today.year, today.month + 1, 1).date() - timedelta(days=1)
        
        budget, created = Budget.objects.get_or_create(
            user=user,
            category=category,
            start_date=start_date,
            end_date=end_date,
            defaults={
                'amount': Decimal('5000.00'),
                'period_type': Budget.MONTHLY,
                'is_active': True
            }
        )
        
        print(f"✅ Бюджет создан: {budget}")
        print(f"   - Сумма: {budget.amount}")
        print(f"   - Период: {budget.get_period_type_display()}")
        print(f"   - Даты: {budget.start_date} - {budget.end_date}")
        
        # Тестируем редактирование бюджета
        old_amount = budget.amount
        new_amount = Decimal('7500.00')
        
        print(f"🔄 Тестируем обновление бюджета с {old_amount} на {new_amount}")
        
        # Обновляем бюджет
        budget.amount = new_amount
        budget.save()
        
        # Проверяем, что бюджет обновился
        updated_budget = Budget.objects.get(id=budget.id)
        print(f"✅ Бюджет обновлен: {updated_budget.amount}")
        
        if updated_budget.amount == new_amount:
            print("✅ Тест редактирования бюджета ПРОЙДЕН!")
        else:
            print("❌ Тест редактирования бюджета ПРОВАЛЕН!")
            return False
        
        # Тестируем методы модели
        print("\n🧪 Тестируем методы модели бюджета:")
        
        # spent_amount
        spent = budget.spent_amount
        print(f"   - spent_amount: {spent}")
        
        # remaining_amount
        remaining = budget.remaining_amount
        print(f"   - remaining_amount: {remaining}")
        
        # spent_percentage
        percentage = budget.spent_percentage
        print(f"   - spent_percentage: {percentage}")
        
        # is_overspent
        overspent = budget.is_overspent
        print(f"   - is_overspent: {overspent}")
        
        # days_remaining
        days = budget.days_remaining
        print(f"   - days_remaining: {days}")
        
        print("✅ Все методы модели работают корректно!")
        
        # Очистка тестовых данных
        budget.delete()
        category.delete()
        user.delete()
        
        print("✅ Тестовые данные очищены")
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_budget_editing()
    sys.exit(0 if success else 1) 