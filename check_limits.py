#!/usr/bin/env python
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finhub.settings')
django.setup()

from transactions.models import Transaction
from budgets.models import Budget
from categories.models import Category
from django.contrib.auth import get_user_model

User = get_user_model()

def check_limits_and_transactions():
    """Проверяет состояние лимитов и транзакций"""
    
    # Находим пользователя
    user = User.objects.filter(username__startswith='tg_').first()
    if not user:
        print("❌ Пользователь не найден")
        return
    
    print(f"👤 Пользователь: {user}")
    
    # Проверяем транзакции
    transactions = Transaction.objects.filter(user=user)
    print(f"💰 Транзакций: {transactions.count()}")
    
    if transactions.exists():
        print("📊 Примеры транзакций:")
        for t in transactions[:5]:
            print(f"  - {t.category.name}: {t.amount} ₽ ({t.date})")
    else:
        print("⚠️  Транзакций нет")
    
    # Проверяем бюджеты/лимиты
    budgets = Budget.objects.filter(user=user, is_active=True)
    print(f"\n📋 Бюджетов/лимитов: {budgets.count()}")
    
    if budgets.exists():
        print("📊 Детали бюджетов:")
        for budget in budgets:
            print(f"\n  🎯 {budget.category.name}")
            print(f"     Сумма: {budget.amount} ₽")
            print(f"     Период: {budget.start_date} - {budget.end_date}")
            print(f"     Потрачено: {budget.spent_amount} ₽")
            print(f"     Процент: {budget.spent_percentage:.1f}%")
            print(f"     Остаток: {budget.remaining_amount} ₽")
    else:
        print("⚠️  Бюджетов нет")
    
    # Проверяем категории
    categories = Category.objects.filter(user=user)
    print(f"\n📂 Категорий: {categories.count()}")
    for cat in categories:
        print(f"  - {cat.icon} {cat.name}")

if __name__ == '__main__':
    check_limits_and_transactions() 