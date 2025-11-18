from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel


class TelegramUser(TimestampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(
        max_length=255,
        blank=True,
    )
    first_name = models.CharField(
        max_length=255,
        blank=True,
    )
    last_name = models.CharField(
        max_length=255,
        blank=True,
    )
    language_code = models.CharField(
        max_length=10,
        default='ru',
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"@{self.username} ({self.telegram_id})"

    class Meta:
        verbose_name = "Telegram пользователь"
        verbose_name_plural = "Telegram пользователи"


class UserState(TimestampedModel):
    TRANSACTION_TYPE_CHOICES = [
        ('expense', 'Расход'),
        ('income', 'Доход'),
    ]

    telegram_user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
    )
    last_transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        default='expense',
    )
    current_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    awaiting_category = models.BooleanField(default=False)
    awaiting_category_creation = models.BooleanField(default=False)
    context_data = models.JSONField(
        default=dict,
        blank=True,
    )

    def __str__(self):
        return f"Состояние {self.telegram_user.username}"

    class Meta:
        verbose_name = "Состояние пользователя"
        verbose_name_plural = "Состояния пользователей"


class UserAlias(TimestampedModel):
    telegram_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
    )
    alias = models.CharField(max_length=50)
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.CASCADE,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.alias} → {self.category.name}"

    class Meta:
        unique_together = [
            'telegram_user',
            'alias',
        ]
        verbose_name = "Алиас пользователя"
        verbose_name_plural = "Алиасы пользователей"


class BotMessage(TimestampedModel):
    MESSAGE_TYPE_CHOICES = [
        ('incoming', 'Входящее'),
        ('outgoing', 'Исходящее'),
        ('callback', 'Callback'),
        ('error', 'Ошибка'),
    ]

    telegram_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
    )
    text = models.TextField()
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    def __str__(self):
        return f"{self.message_type}: {self.text[:50]}..."

    class Meta:
        verbose_name = "Сообщение бота"
        verbose_name_plural = "Сообщения бота"
        ordering = ['-created_at']
