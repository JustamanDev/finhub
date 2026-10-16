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
    ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (ACTIVE, 'Активна'),
        (PAUSED, 'Пауза'),
        (COMPLETED, 'Завершена'),
        (CANCELLED, 'Отменена'),
        (ARCHIVED, 'В архиве'),
    ]

    SAVINGS = 'savings'
    ENVELOPE = 'envelope'

    KIND_CHOICES = [
        (SAVINGS, 'Цель'),
        (ENVELOPE, 'Конверт'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='goals',
        verbose_name='Пользователь',
    )
    title = models.CharField('Название', max_length=120)
    kind = models.CharField(
        'Тип',
        max_length=16,
        choices=KIND_CHOICES,
        default=SAVINGS,
    )
    target_amount = models.DecimalField(
        'Целевая сумма',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    deadline = models.DateField('Дедлайн', null=True, blank=True)
    status = models.CharField(
        'Статус',
        max_length=16,
        choices=STATUS_CHOICES,
        default=ACTIVE,
    )

    class Meta:
        verbose_name = 'Цель или конверт'
        verbose_name_plural = 'Цели и конверты'
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

    @property
    def is_envelope(self) -> bool:
        return self.kind == self.ENVELOPE

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
            # Важно: имя индекса фиксируем явно, чтобы состояние моделей
            # совпадало с миграциями и не возникало "changes not reflected"
            # при `manage.py migrate`.
            models.Index(
                fields=[
                    'goal',
                    'occurred_at',
                ],
                name='goals_goall_goal_id_b2f0f5_idx',
            ),
        ]

    def __str__(self) -> str:
        sign = '+' if self.amount >= Decimal('0') else ''
        return f"{self.goal_id}: {sign}{self.amount} ({self.entry_type})"

