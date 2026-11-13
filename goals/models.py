from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel
from transactions.currencies import CURRENCY_CHOICES, RUB
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
    currency = models.CharField(
        'Валюта',
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=RUB,
        help_text='В ней целевая сумма, взносы и остаток. В отчёте переводится в базовую.',
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
    amount = models.DecimalField(
        'Сумма',
        max_digits=14,
        decimal_places=2,
        help_text='В валюте цели или конверта. Плюс — взнос, минус — снятие или трата.',
    )
    report_amount = models.DecimalField(
        'Сумма в валюте отчёта',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Та же строка в базовой валюте на момент записи. Её суммирует «свободно».',
    )
    report_currency = models.CharField(
        'Валюта отчёта',
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=RUB,
    )
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

    def save(self, *args, **kwargs):
        extra: list[str] = []
        if self.report_amount is None:
            self.report_amount = self.amount
            extra.append('report_amount')
        if not self.report_currency:
            self.report_currency = RUB
            extra.append('report_currency')
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and extra:
            kwargs['update_fields'] = list(update_fields) + [
                name for name in extra if name not in update_fields
            ]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        sign = '+' if self.amount >= Decimal('0') else ''
        return f"{self.goal_id}: {sign}{self.amount} ({self.entry_type})"

