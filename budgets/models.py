import logging
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import (
    datetime,
    timedelta,
)
from decimal import Decimal
from core.models import TimestampedModel
from categories.models import Category


logger = logging.getLogger('budgets')


class Budget(TimestampedModel):
    """
    Модель бюджета с план-факт анализом.
    
    Позволяет создавать бюджеты по категориям с автоматическим
    расчетом потраченной суммы, остатка и процентов выполнения.
    
    Attributes:
        category: Категория расходов для бюджета
        amount: Запланированная сумма бюджета
        period_type: Тип периода (месячный, недельный, годовой)
        start_date: Дата начала периода
        end_date: Дата окончания периода
        user: Владелец бюджета
        is_active: Активен ли бюджет
    """
    MONTHLY = 'monthly'
    WEEKLY = 'weekly'
    YEARLY = 'yearly'
    
    PERIOD_CHOICES = [
        (MONTHLY, 'Месячный'),
        (WEEKLY, 'Недельный'),
        (YEARLY, 'Годовой'),
    ]
    
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='budgets',
        verbose_name='Категория'
    )
    amount = models.DecimalField('Сумма бюджета', max_digits=12, decimal_places=2)
    period_type = models.CharField('Период', max_length=10, choices=PERIOD_CHOICES, default=MONTHLY)
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets', verbose_name='Пользователь')
    is_active = models.BooleanField('Активен', default=True)
    
    class Meta:
        verbose_name = 'Бюджет'
        verbose_name_plural = 'Бюджеты'
        ordering = [
            '-start_date',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'category',
                    'start_date',
                    'end_date',
                    'user',
                ],
                name='unique_budget_per_period',
            ),
        ]
        
    def __str__(self):
        return f"{self.category.name}: {self.amount} руб. ({self.get_period_type_display()})"
        
    @property
    def spent_amount(self):
        """
        Вычисляет сумму потраченную за период бюджета.
        
        Returns:
            Decimal: Общая сумма трат по категории за период бюджета
        """
        from transactions.models import Transaction
        
        # Учитываем только расходы (отрицательные суммы)
        spent = Transaction.objects.filter(
            user=self.user,
            category=self.category,
            date__gte=self.start_date,
            date__lte=self.end_date,
            amount__lt=0  # Только расходы (отрицательные суммы)
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Возвращаем абсолютное значение (положительное число)
        return abs(spent)
        
    @property
    def remaining_amount(self):
        """
        Вычисляет остаток бюджета.
        
        Returns:
            Decimal: Разница между запланированной суммой и потраченной
        """
        from decimal import Decimal
        return Decimal(str(self.amount)) - self.spent_amount
        
    @property
    def spent_percentage(self):
        """
        Вычисляет процент потраченного бюджета.
        
        Returns:
            float: Процент потраченной суммы от общего бюджета (0-100+)
        """
        from decimal import Decimal
        if self.amount == 0:
            return 0
        return float((self.spent_amount / Decimal(str(self.amount))) * 100)
        
    @property
    def remaining_percentage(self):
        """Процент оставшегося бюджета"""
        return 100 - self.spent_percentage
        
    @property
    def is_overspent(self):
        """
        Проверяет превышен ли бюджет.
        
        Returns:
            bool: True если потрачено больше запланированного
        """
        from decimal import Decimal
        return self.spent_amount > Decimal(str(self.amount))
        
    @property
    def days_remaining(self):
        """Количество дней до конца периода бюджета"""
        from datetime import date

        if self.start_date is None or self.end_date is None:
            return 0

        today = date.today()
        if self.end_date is None:
            return 0

        if today > self.end_date:
            return 0  # Период завершен

        return (self.end_date - today).days
        
    @property
    def days_total(self):
        """Всего дней в периоде"""
        if not self.start_date or not self.end_date:  # Проверка на None
            return 0
        try:
            return (self.end_date - self.start_date).days + 1
        except (TypeError, AttributeError):
            return 0
        
    @property
    def daily_budget_remaining(self):
        """
        Вычисляет дневной бюджет из оставшейся суммы.
        
        Returns:
            Decimal: Сумма которую можно тратить в день до конца периода
        """
        if self.days_remaining <= 0:
            return Decimal('0.00')
        try:
            return self.remaining_amount / self.days_remaining
        except (TypeError, ZeroDivisionError):
            return Decimal('0.00')
        
    @classmethod
    def get_current_budget(cls, user, category, date=None):
        """
        Получает текущий активный бюджет для категории на указанную дату.
        
        Args:
            user: Пользователь - владелец бюджета
            category: Категория для поиска бюджета
            date: Дата для проверки (по умолчанию сегодня)
            
        Returns:
            Budget или None: Активный бюджет для категории или None если не найден
        """
        if date is None:
            date = timezone.now().date()
            
        return cls.objects.filter(
            user=user,
            category=category,
            start_date__lte=date,
            end_date__gte=date,
            is_active=True
        ).first()
        
    @classmethod  
    def create_monthly_budget(cls, user, category, amount, year=None, month=None):
        """
        Создает месячный бюджет для указанного года и месяца.
        
        Args:
            user: Пользователь - владелец бюджета
            category: Категория для бюджета
            amount: Сумма бюджета
            year: Год (по умолчанию текущий)
            month: Месяц (по умолчанию текущий)
            
        Returns:
            Budget: Созданный бюджет
        """
        if year is None or month is None:
            today = timezone.now().date()
            year = year or today.year
            month = month or today.month
            
        start_date = datetime(year, month, 1).date()
        
        # Последний день месяца
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
            
        return cls.objects.create(
            user=user,
            category=category,
            amount=amount,
            period_type=cls.MONTHLY,
            start_date=start_date,
            end_date=end_date
        )
        
    def save(self, *args, **kwargs):
        """
        Переопределенный метод сохранения с логированием.
        
        Автоматически устанавливает end_date для месячных бюджетов
        если он не был указан явно.
        """
        is_new = self.pk is None
        
        # Автоматически устанавливаем даты для месячного бюджета
        if self.period_type == self.MONTHLY and not self.end_date and self.start_date:
            start = self.start_date
            if start.month == 12:
                end_date = datetime(start.year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(start.year, start.month + 1, 1).date() - timedelta(days=1)
            self.end_date = end_date
            
        if is_new:
            super().save(*args, **kwargs)
            logger.info(
                f"Budget created: ID={self.id}, User={self.user.username}, "
                f"Category={self.category.name}, Amount={self.amount}, "
                f"Period={self.get_period_type_display()}, "
                f"Dates={self.start_date} to {self.end_date}"
            )
        else:
            old_budget = Budget.objects.get(pk=self.pk)
            super().save(*args, **kwargs)
            
            # Log significant changes
            changes = []
            if old_budget.amount != self.amount:
                changes.append(f"amount: {old_budget.amount} -> {self.amount}")
            if old_budget.is_active != self.is_active:
                changes.append(f"status: {'active' if self.is_active else 'inactive'}")
                
            if changes:
                logger.info(
                    f"Budget updated: ID={self.id}, User={self.user.username}, "
                    f"Category={self.category.name}, Changes: {', '.join(changes)}"
                )
                
        # Log overspent budgets
        if not is_new and self.is_overspent:
            logger.warning(
                f"Budget overspent: ID={self.id}, User={self.user.username}, "
                f"Category={self.category.name}, Budget={self.amount}, "
                f"Spent={self.spent_amount}, Overage={self.spent_amount - self.amount}"
            )
