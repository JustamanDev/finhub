"""Шаблон повторяющейся операции. Сам платёж потом становится обычной транзакцией."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from categories.models import Category
from core.models import TimestampedModel


class RecurringTemplate(TimestampedModel):
    """Ритм и ожидание. Якорь — дата следующего раза."""

    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    YEARLY = 'yearly'
    PERIOD_CHOICES = [
        (WEEKLY, 'Каждую неделю'),
        (MONTHLY, 'Каждый месяц'),
        (YEARLY, 'Каждый год'),
    ]

    EXACT = 'exact'
    RANGE = 'range'
    OPEN = 'open'
    AMOUNT_KIND_CHOICES = [
        (EXACT, 'Точная сумма'),
        (RANGE, 'Диапазон'),
        (OPEN, 'Сумма не задана'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_templates',
        verbose_name='Пользователь',
    )
    name = models.CharField('Название', max_length=100)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='recurring_templates',
        verbose_name='Категория',
    )
    periodicity = models.CharField(
        'Периодичность',
        max_length=10,
        choices=PERIOD_CHOICES,
    )
    amount_kind = models.CharField(
        'Ожидание суммы',
        max_length=10,
        choices=AMOUNT_KIND_CHOICES,
        default=OPEN,
    )
    amount = models.DecimalField(
        'Точная сумма',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    amount_min = models.DecimalField(
        'Сумма от',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    amount_max = models.DecimalField(
        'Сумма до',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    next_due = models.DateField('Следующий раз')
    reminded_for = models.DateField(
        'Напоминание уже за эту дату',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Повторяющаяся операция'
        verbose_name_plural = 'Повторяющиеся операции'
        ordering = ['next_due', 'name']

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if self.category_id and self.category.user_id != self.user_id:
            raise ValidationError('Категория принадлежит другому человеку.')
        if self.amount_kind == self.EXACT:
            if self.amount is None or self.amount <= 0:
                raise ValidationError('Для точной суммы нужно положительное число.')
            if self.amount_min is not None or self.amount_max is not None:
                raise ValidationError('У точной суммы нет диапазона.')
        elif self.amount_kind == self.RANGE:
            if self.amount is not None:
                raise ValidationError('У диапазона нет одной точной суммы.')
            if (
                self.amount_min is None
                or self.amount_max is None
                or self.amount_min <= 0
                or self.amount_max < self.amount_min
            ):
                raise ValidationError('Диапазон: положительные границы, «до» не меньше «от».')
        elif self.amount_kind == self.OPEN:
            if self.amount is not None or self.amount_min is not None or self.amount_max is not None:
                raise ValidationError('Пустое ожидание не хранит сумму.')
        else:
            raise ValidationError('Неизвестное ожидание суммы.')
