import logging
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel
from categories.models import Category
from transactions.currencies import CURRENCY_CHOICES, RUB, is_known


logger = logging.getLogger('transactions')


class Transaction(TimestampedModel):
    """
    Модель финансовой транзакции.
    
    Представляет собой единичную операцию дохода или расхода,
    привязанную к определенной категории и пользователю.
    
    Attributes:
        amount: Сумма в валюте отчёта (базовая на момент записи), со знаком
        original_amount: Сумма в валюте ввода, со знаком
        currency: как сумму ввели
        report_currency: в какой валюте лежит amount
        exchange_rate: единиц валюты отчёта за 1 единицу валюты ввода
        description: Описание транзакции
        category: Категория транзакции
        date: Дата совершения транзакции
        user: Владелец транзакции
    """
    amount = models.DecimalField('Сумма в валюте отчёта', max_digits=12, decimal_places=2)
    currency = models.CharField(
        'Валюта ввода',
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=RUB,
    )
    report_currency = models.CharField(
        'Валюта отчёта',
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=RUB,
        help_text='В какой валюте лежит amount. По умолчанию рубли.',
    )
    original_amount = models.DecimalField(
        'Сумма в валюте ввода',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    exchange_rate = models.DecimalField(
        'Курс к валюте отчёта',
        max_digits=20,
        decimal_places=10,
        default=Decimal('1'),
        help_text='Сколько единиц валюты отчёта за 1 единицу валюты ввода. Если они совпадают, курс = 1.',
    )
    rate_date = models.DateField('Дата курса ЦБ', null=True, blank=True)
    rate_nominal = models.PositiveIntegerField(
        'Номинал курса',
        default=1,
        help_text='Сколько единиц валюты в котировке ЦБ. Для донга обычно 10000.',
    )
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
        report = self.report_currency or RUB
        if self.currency != report and self.original_amount is not None:
            return (
                f"{self.original_amount} {self.currency} "
                f"({self.amount} {report}) - {self.category.name} ({self.date})"
            )
        return f"{self.amount} {report} - {self.category.name} ({self.date})"
        
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
        if not self.currency or not is_known(self.currency):
            self.currency = RUB
        if not self.report_currency or not is_known(self.report_currency):
            self.report_currency = RUB
        if self.exchange_rate is None:
            self.exchange_rate = Decimal('1')
        if self.original_amount is None:
            self.original_amount = self.amount
        if not self.rate_nominal:
            self.rate_nominal = 1

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


class ExchangeRate(TimestampedModel):
    """Дневной курс валюты к рублю. Для донга источник — XML ЦБ РФ."""

    rate_date = models.DateField('Дата курса')
    base_currency = models.CharField('Валюта', max_length=3)
    quote_currency = models.CharField('Котировка', max_length=3, default=RUB)
    nominal = models.PositiveIntegerField('Номинал', default=1)
    value = models.DecimalField(
        'Значение ЦБ',
        max_digits=16,
        decimal_places=4,
        help_text='Рублей за nominal единиц валюты, как публикует ЦБ.',
    )
    rate = models.DecimalField(
        'Рублей за 1 единицу',
        max_digits=20,
        decimal_places=10,
    )
    source = models.CharField('Источник', max_length=32, default='cbr')
    fetched_on = models.DateField('Запрошено')

    class Meta:
        verbose_name = 'Курс валюты'
        verbose_name_plural = 'Курсы валют'
        ordering = ['-rate_date']
        constraints = [
            models.UniqueConstraint(
                fields=['rate_date', 'base_currency', 'quote_currency'],
                name='unique_exchange_rate_per_day',
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.base_currency}/{self.quote_currency} "
            f"{self.value} за {self.nominal} на {self.rate_date}"
        )
