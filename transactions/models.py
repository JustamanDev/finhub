import logging
from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel
from categories.models import Category


logger = logging.getLogger('transactions')


class Transaction(TimestampedModel):
    """
    Модель финансовой транзакции.
    
    Представляет собой единичную операцию дохода или расхода,
    привязанную к определенной категории и пользователю.
    
    Attributes:
        amount: Сумма транзакции
        description: Описание транзакции
        category: Категория транзакции
        date: Дата совершения транзакции
        user: Владелец транзакции
    """
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        verbose_name='Категория'
    )
    date = models.DateField('Дата')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions', verbose_name='Пользователь')
    
    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = [
            '-date',
            '-created_at',
        ]
        
    def __str__(self):
        return f"{self.amount} руб. - {self.category.name} ({self.date})"
        
    @property
    def is_income(self):
        """
        Проверяет является ли транзакция доходом.
        
        Returns:
            bool: True если транзакция относится к категории доходов
        """
        return self.category.type == Category.INCOME
        
    @property
    def is_expense(self):
        """
        Проверяет является ли транзакция расходом.
        
        Returns:
            bool: True если транзакция относится к категории расходов
        """
        return self.category.type == Category.EXPENSE
        
    def save(self, *args, **kwargs):
        """Переопределенный метод сохранения с логированием."""
        is_new = self.pk is None
        
        if is_new:
            super().save(*args, **kwargs)
            logger.info(
                f"Transaction created: ID={self.id}, User={self.user.username}, "
                f"Amount={self.amount}, Category={self.category.name}, "
                f"Type={self.category.type}, Date={self.date}"
            )
        else:
            old_transaction = Transaction.objects.get(pk=self.pk)
            super().save(*args, **kwargs)
            
            # Log changes
            changes = []
            if old_transaction.amount != self.amount:
                changes.append(f"amount: {old_transaction.amount} -> {self.amount}")
            if old_transaction.category != self.category:
                changes.append(f"category: {old_transaction.category.name} -> {self.category.name}")
            if old_transaction.date != self.date:
                changes.append(f"date: {old_transaction.date} -> {self.date}")
            if old_transaction.description != self.description:
                changes.append(f"description changed")
                
            if changes:
                logger.info(
                    f"Transaction updated: ID={self.id}, User={self.user.username}, "
                    f"Changes: {', '.join(changes)}"
                )
                
    def delete(self, *args, **kwargs):
        """Переопределенный метод удаления с логированием."""
        logger.warning(
            f"Transaction deleted: ID={self.id}, User={self.user.username}, "
            f"Amount={self.amount}, Category={self.category.name}, Date={self.date}"
        )
        super().delete(*args, **kwargs)
