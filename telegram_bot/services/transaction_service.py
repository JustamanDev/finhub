import logging
from decimal import Decimal
from datetime import date
from typing import Optional
from django.contrib.auth.models import User
from django.db import models
from asgiref.sync import sync_to_async

from transactions.currencies import RUB, VND
from transactions.exchange import apply_entered_amount, rub_amount
from transactions.models import Transaction
from categories.models import Category
from telegram_bot.services.budget_alerts import (
    breaches_after_spend,
    snapshot_spent,
)

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
        currency: str = RUB,
    ) -> Transaction:
        """
        Создает новую транзакцию
        
        Args:
            amount: Сумма транзакции
            category: Категория
            transaction_type: Тип транзакции ('expense' или 'income')
            transaction_date: Дата транзакции (по умолчанию сегодня)
            description: Описание транзакции
            currency: Валюта введённой суммы. Донги переводятся в рубли.
            
        Returns:
            Созданная транзакция
        """
        if transaction_date is None:
            transaction_date = date.today()
        
        # Корректируем знак суммы в зависимости от типа
        if transaction_type == 'expense':
            signed = -abs(amount)
        else:
            signed = abs(amount)

        def _create() -> Transaction:
            before = snapshot_spent(self.user, category, transaction_date)
            transaction = Transaction(
                user=self.user,
                category=category,
                amount=signed,
                date=transaction_date,
                description=description,
            )
            apply_entered_amount(transaction, signed, currency or RUB)
            transaction.save()
            transaction._budget_breaches = breaches_after_spend(
                self.user,
                category,
                transaction_date,
                before,
            )
            return transaction

        transaction = await sync_to_async(_create, thread_sensitive=True)()
        amount = transaction.amount
        
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
        def _update_date():
            try:
                transaction = Transaction.objects.select_related('category').get(
                    id=transaction_id,
                    user=self.user,
                )
            except Transaction.DoesNotExist:
                return None
            before = snapshot_spent(self.user, transaction.category, new_date)
            transaction.date = new_date
            transaction.save()
            from telegram_bot.services.goal_spend import move_linked_spend

            move_linked_spend(transaction)
            transaction._budget_breaches = breaches_after_spend(
                self.user,
                transaction.category,
                new_date,
                before,
            )
            return transaction

        transaction = await sync_to_async(_update_date, thread_sensitive=True)()
        if transaction is None:
            logger.warning(
                f"Транзакция {transaction_id} не найдена "
                f"для пользователя {self.user.id}"
            )
        return transaction
    
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

    async def update_transaction_amount(
        self,
        transaction_id: int,
        new_amount: Decimal,
    ) -> Optional[Transaction]:
        """
        Обновляет сумму транзакции.

        Сохраняет семантику знака:
        - для расходов сумма хранится отрицательной
        - для доходов сумма хранится положительной
        """
        def _update_amount():
            try:
                transaction = Transaction.objects.select_related('category').get(
                    id=transaction_id,
                    user=self.user,
                )
            except Transaction.DoesNotExist:
                return None

            before = snapshot_spent(
                self.user,
                transaction.category,
                transaction.date,
            )
            if transaction.category.type == 'expense':
                signed = -abs(new_amount)
            else:
                signed = abs(new_amount)

            if transaction.currency == VND and transaction.exchange_rate:
                transaction.original_amount = signed
                transaction.amount = rub_amount(signed, transaction.exchange_rate)
            else:
                transaction.currency = RUB
                transaction.original_amount = signed
                transaction.exchange_rate = Decimal('1')
                transaction.rate_date = None
                transaction.rate_nominal = 1
                transaction.amount = signed

            from telegram_bot.services.goal_spend import (
                ensure_spend_fits,
                resize_linked_spend,
            )

            ensure_spend_fits(transaction, abs(transaction.amount))
            transaction.save()
            resize_linked_spend(transaction)
            transaction._budget_breaches = breaches_after_spend(
                self.user,
                transaction.category,
                transaction.date,
                before,
            )
            return transaction

        return await sync_to_async(_update_amount, thread_sensitive=True)()
    
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
            from telegram_bot.services.goal_spend import release_linked_spend

            await sync_to_async(release_linked_spend, thread_sensitive=True)(
                transaction.id,
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