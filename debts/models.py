"""Долг: кому и сколько. К транзакциям и повторяющимся операциям не привязан."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce

from core.models import TimestampedModel
from transactions.currencies import CURRENCY_CHOICES, RUB


class Debt(TimestampedModel):
    """Обязательство. Якорь — исходная сумма и контрагент."""

    OWE = 'owe'
    OWED = 'owed'
    DIRECTION_CHOICES = [
        (OWE, 'Я должен'),
        (OWED, 'Мне должны'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='debts',
        verbose_name='Пользователь',
    )
    counterparty = models.CharField('Кому', max_length=100)
    direction = models.CharField(
        'Направление',
        max_length=10,
        choices=DIRECTION_CHOICES,
    )
    principal = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    currency = models.CharField(
        'Валюта',
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=RUB,
        help_text='В ней сумма и платежи. В отчёте остаток переводится в базовую.',
    )
    is_open = models.BooleanField('Открыт', default=True)

    class Meta:
        verbose_name = 'Долг'
        verbose_name_plural = 'Долги'
        ordering = ['counterparty', 'id']

    def __str__(self) -> str:
        return f'{self.counterparty}: {self.principal}'

    def clean(self) -> None:
        if self.principal is None or self.principal <= 0:
            raise ValidationError('Сумма долга должна быть больше нуля.')

    @property
    def paid(self) -> Decimal:
        total = self.payments.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0')),
        )['total']
        return Decimal(total or 0)

    @property
    def remaining(self) -> Decimal:
        left = Decimal(self.principal) - self.paid
        return left if left > 0 else Decimal('0')


class DebtPayment(TimestampedModel):
    """Платёж по долгу. Транзакцию не создаёт."""

    debt = models.ForeignKey(
        Debt,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Долг',
    )
    amount = models.DecimalField(
        'Сумма',
        max_digits=12,
        decimal_places=2,
        help_text='В валюте долга.',
    )
    input_amount = models.DecimalField(
        'Сумма ввода',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Как заплатили, если валюта платежа отличается от валюты долга.',
    )
    input_currency = models.CharField('Валюта ввода', max_length=3, blank=True, default='')
    paid_on = models.DateField('Дата')

    class Meta:
        verbose_name = 'Платёж по долгу'
        verbose_name_plural = 'Платежи по долгам'
        ordering = ['-paid_on', '-id']

    def clean(self) -> None:
        if self.amount is None or self.amount <= 0:
            raise ValidationError('Платёж должен быть больше нуля.')
