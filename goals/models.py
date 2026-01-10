from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel
from transactions.models import Transaction


class Goal(TimestampedModel):
    ACTIVE = 'active'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (ACTIVE, 'Активна'),
        (PAUSED, 'Пауза'),
        (COMPLETED, 'Завершена'),
        (CANCELLED, 'Отменена'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='goals',
        verbose_name='Пользователь',
    )
    title = models.CharField('Название цели', max_length=120)
    target_amount = models.DecimalField('Целевая сумма', max_digits=14, decimal_places=2)
    deadline = models.DateField('Дедлайн', null=True, blank=True)
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=STATUS_CHOICES,
        default=ACTIVE,
    )

    class Meta:
        verbose_name = 'Цель'
        verbose_name_plural = 'Цели'
        ordering = [
            '-created_at',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'user',
                    'title',
                ],
                name='unique_goal_title_per_user',
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.user_id})"


class GoalLedgerEntry(TimestampedModel):
    DEPOSIT = 'deposit'
    WITHDRAW = 'withdraw'
    SPEND = 'spend'

    TYPE_CHOICES = [
        (DEPOSIT, 'Пополнение'),
        (WITHDRAW, 'Снятие'),
        (SPEND, 'Покупка/трата из цели'),
    ]

    goal = models.ForeignKey(
        Goal,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Цель',
    )
    occurred_at = models.DateTimeField('Дата операции', default=timezone.now)
    # amount:
    #  - deposit:  +amount
    #  - withdraw: -amount
    #  - spend:    -amount
    amount = models.DecimalField('Сумма', max_digits=14, decimal_places=2)
    entry_type = models.CharField('Тип', max_length=16, choices=TYPE_CHOICES)
    comment = models.TextField('Комментарий', blank=True)
    linked_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='goal_entries',
        verbose_name='Связанная транзакция',
    )

    class Meta:
        verbose_name = 'Операция по цели'
        verbose_name_plural = 'Операции по целям'
        ordering = [
            '-occurred_at',
            '-id',
        ]
        indexes = [
            models.Index(fields=['goal', 'occurred_at']),
        ]

    def __str__(self) -> str:
        sign = '+' if self.amount >= Decimal('0') else ''
        return f"{self.goal_id}: {sign}{self.amount} ({self.entry_type})"

