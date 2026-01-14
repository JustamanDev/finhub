from django.contrib import admin

from telegram_bot.models import (
    BotMessage,
    BotText,
    TelegramUser,
    UserAlias,
    UserState,
)


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "is_active",
        "created_at",
    ]
    search_fields = [
        "telegram_id",
        "username",
        "first_name",
        "last_name",
        "user__username",
    ]
    list_filter = [
        "is_active",
        "created_at",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(UserState)
class UserStateAdmin(admin.ModelAdmin):
    list_display = [
        "telegram_user",
        "last_transaction_type",
        "awaiting_category",
        "awaiting_category_creation",
        "updated_at",
    ]
    search_fields = [
        "telegram_user__username",
        "telegram_user__telegram_id",
    ]
    list_filter = [
        "last_transaction_type",
        "awaiting_category",
        "awaiting_category_creation",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(UserAlias)
class UserAliasAdmin(admin.ModelAdmin):
    list_display = [
        "telegram_user",
        "alias",
        "category",
        "amount",
        "created_at",
    ]
    search_fields = [
        "alias",
        "telegram_user__username",
        "telegram_user__telegram_id",
        "category__name",
    ]
    list_filter = [
        "created_at",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(BotMessage)
class BotMessageAdmin(admin.ModelAdmin):
    list_display = [
        "telegram_user",
        "message_type",
        "short_text",
        "created_at",
    ]
    list_filter = [
        "message_type",
        "created_at",
    ]
    search_fields = [
        "telegram_user__username",
        "telegram_user__telegram_id",
        "text",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    def short_text(self, obj: BotMessage) -> str:
        return (obj.text or "")[:80]


@admin.register(BotText)
class BotTextAdmin(admin.ModelAdmin):
    list_display = [
        "slug",
        "title",
        "is_active",
        "updated_at",
    ]
    search_fields = [
        "slug",
        "title",
        "text",
    ]
    list_filter = [
        "is_active",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "slug",
                    "title",
                    "is_active",
                ),
            },
        ),
        (
            "Текст",
            {
                "fields": ("text",),
                "description": (
                    "Поддерживаемые плейсхолдеры:\n"
                    "- <code>{first_name}</code> или <code>{firstName}</code> — имя пользователя из Telegram."
                ),
            },
        ),
        (
            "Системное",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )
