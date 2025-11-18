import logging
from decimal import Decimal
from datetime import date
from typing import Optional
from django.contrib.auth.models import User
from django.db import models
from asgiref.sync import sync_to_async

from transactions.models import Transaction
from categories.models import Category
from budgets.models import Budget

logger = logging.getLogger(__name__)


class TransactionService:
    """Сервис для работы с транзакциями через Telegram бот"""
    
    def __init__(self, user: User):
        self.user = user
    
    async def create_transaction(
        self,
        amount: Decimal,
        category: Category,
        transaction_type: str,
        transaction_date: Optional[date] = None,
        description: str = "",
    ) -> Transaction:
        """
        Создает новую транзакцию
        
        Args:
            amount: Сумма транзакции
            category: Категория
            transaction_type: Тип транзакции ('expense' или 'income')
            transaction_date: Дата транзакции (по умолчанию сегодня)
            description: Описание транзакции
            
        Returns:
            Созданная транзакция
        """
        if transaction_date is None:
            transaction_date = date.today()
        
        # Корректируем знак суммы в зависимости от типа
        if transaction_type == 'expense':
            amount = -abs(amount)
        else:
            amount = abs(amount)
        
        transaction = await Transaction.objects.acreate(
            user=self.user,
            category=category,
            amount=amount,
            date=transaction_date,
            description=description,
        )
        
        logger.info(
            f"Создана транзакция: {amount}₽ "
            f"в категории {category.name} для пользователя {self.user.id}"
        )
        
        return transaction
    
    async def update_transaction_date(
        self,
        transaction_id: int,
        new_date: date,
    ) -> Optional[Transaction]:
        """
        Обновляет дату транзакции
        
        Args:
            transaction_id: ID транзакции
            new_date: Новая дата
            
        Returns:
            Обновленная транзакция или None если не найдена
        """
        try:
            transaction = await Transaction.objects.aget(
                id=transaction_id,
                user=self.user,
            )
            transaction.date = new_date
            await transaction.asave()
            return transaction
        except Transaction.DoesNotExist:
            logger.warning(
                f"Транзакция {transaction_id} не найдена "
                f"для пользователя {self.user.id}"
            )
            return None
    
    async def update_transaction_description(
        self,
        transaction_id: int,
        description: str,
    ) -> Optional[Transaction]:
        """
        Обновляет описание транзакции
        
        Args:
            transaction_id: ID транзакции
            description: Новое описание
            
        Returns:
            Обновленная транзакция или None если не найдена
        """
        try:
            transaction = await Transaction.objects.aget(
                id=transaction_id,
                user=self.user,
            )
            transaction.description = description
            await transaction.asave()
            return transaction
        except Transaction.DoesNotExist:
            return None
    
    async def delete_transaction(
        self,
        transaction_id: int,
    ) -> bool:
        """
        Удаляет транзакцию
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            True если транзакция удалена, False если не найдена
        """
        try:
            transaction = await Transaction.objects.aget(
                id=transaction_id,
                user=self.user,
            )
            await transaction.adelete()
            logger.info(
                f"Удалена транзакция {transaction_id} "
                f"пользователя {self.user.id}"
            )
            return True
        except Transaction.DoesNotExist:
            return False
    
    async def get_today_statistics(self) -> dict:
        """
        Получает статистику за сегодня
        
        Returns:
            Словарь со статистикой
        """
        today = date.today()
        
        # Используем sync ORM в отдельном потоке через sync_to_async
        expenses_qs = Transaction.objects.filter(
            user=self.user,
            date=today,
            amount__lt=0,
        )
        
        income_qs = Transaction.objects.filter(
            user=self.user,
            date=today,
            amount__gt=0,
        )
        
        # Агрегируем суммы в thread-sensitive контексте
        expenses_total = await sync_to_async(
            lambda: expenses_qs.aggregate(total=models.Sum('amount'))['total'] or Decimal('0'),
            thread_sensitive=True,
        )()
        income_total = await sync_to_async(
            lambda: income_qs.aggregate(total=models.Sum('amount'))['total'] or Decimal('0'),
            thread_sensitive=True,
        )()
        
        return {
            'expenses': abs(expenses_total),
            'income': income_total,
            'balance': income_total + expenses_total,
        }


class SmartSuggestionsService:
    """Сервис умных предложений для категорий"""
    
    def __init__(self, user: User):
        self.user = user
    
    async def get_suggested_amounts(
        self,
        category: Category,
        limit: int = 3,
    ) -> list[Decimal]:
        """
        Получает предлагаемые суммы для категории
        
        Args:
            category: Категория
            limit: Максимальное количество предложений
            
        Returns:
            Список предлагаемых сумм
        """
        # TODO: Реализовать более умную логику предложений
        # Пока возвращаем фиксированные варианты
        if category.type == 'expense':
            if 'кофе' in category.name.lower():
                return [
                    Decimal('150'),
                    Decimal('250'),
                    Decimal('400'),
                ]
            elif 'продукты' in category.name.lower():
                return [
                    Decimal('500'),
                    Decimal('1000'),
                    Decimal('2000'),
                ]
            elif 'транспорт' in category.name.lower():
                return [
                    Decimal('57'),
                    Decimal('150'),
                    Decimal('500'),
                ]
        
        return [] 