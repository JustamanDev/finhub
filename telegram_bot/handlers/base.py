import logging
from typing import (
    Dict,
    Any,
    Optional,
    Tuple,
)
from telegram import (
    Update,
    User as TelegramUserModel,
)
from telegram.ext import ContextTypes
from django.contrib.auth.models import User
from django.db import IntegrityError

from telegram_bot.models import (
    TelegramUser,
    UserState,
    BotMessage,
)
from telegram_bot.utils.text_parser import TextCommandParser
from telegram_bot.utils.admin_alerts import notify_admins_about_exception
from telegram_bot.utils.telegram_resilience import retry_telegram_call
from categories.default_categories import ensure_default_categories_async

logger = logging.getLogger(__name__)


class BaseHandler:
    """Базовый класс для всех обработчиков команд"""
    
    def __init__(self):
        self.parser = None

    async def get_or_create_telegram_user_with_bootstrap(
        self,
        telegram_user: TelegramUserModel,
    ) -> Tuple[TelegramUser, bool, int]:
        """
        Возвращает TelegramUser + флаги инициализации.

        Returns:
            (tg_user, is_new_user, defaults_created_count)
        """
        telegram_id = telegram_user.id
        django_username = f"tg_{telegram_id}"

        # Fast path: TelegramUser exists
        try:
            tg_user = await TelegramUser.objects.aget(telegram_id=telegram_id)
            return tg_user, False, 0
        except TelegramUser.DoesNotExist:
            pass

        # Idempotent bootstrap. Must be resilient to:
        # - partially created auth.User (username exists) without TelegramUser
        # - concurrent updates (/start + /help) racing to create the same records
        django_user, _ = await User.objects.aget_or_create(
            username=django_username,
            defaults={
                "first_name": telegram_user.first_name or "",
                "last_name": telegram_user.last_name or "",
            },
        )

        try:
            tg_user, tg_created = await TelegramUser.objects.aget_or_create(
                telegram_id=telegram_id,
                defaults={
                    "user": django_user,
                    "username": telegram_user.username or "",
                    "first_name": telegram_user.first_name or "",
                    "last_name": telegram_user.last_name or "",
                    "language_code": telegram_user.language_code or "ru",
                    "is_active": True,
                },
            )
        except IntegrityError:
            # Race: someone created it between our check and create.
            tg_user = await TelegramUser.objects.aget(telegram_id=telegram_id)
            tg_created = False

        # Ensure state exists (idempotent)
        await UserState.objects.aget_or_create(telegram_user=tg_user)

        # Ensure categories exist (idempotent). Run after TelegramUser exists,
        # so even if categories fail, user won't get stuck in bootstrap.
        try:
            defaults_created_count = await ensure_default_categories_async(django_user)
        except Exception:
            defaults_created_count = 0

        return tg_user, tg_created, defaults_created_count

    async def get_or_create_telegram_user(
        self,
        telegram_user: TelegramUserModel,
    ) -> TelegramUser:
        """
        Получает или создает пользователя Telegram
        
        Args:
            telegram_user: Объект пользователя из Telegram
            
        Returns:
            Объект TelegramUser
        """
        tg_user, _, _ = await self.get_or_create_telegram_user_with_bootstrap(
            telegram_user
        )
        return tg_user
    
    async def get_user_state(self, telegram_user: TelegramUser) -> UserState:
        """
        Получает состояние пользователя
        
        Args:
            telegram_user: Объект TelegramUser
            
        Returns:
            Состояние пользователя
        """
        state, _ = await UserState.objects.aget_or_create(
            telegram_user=telegram_user
        )
        return state
    
    async def log_message(
        self,
        telegram_user: TelegramUser,
        message_type: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Логирует сообщение для отладки
        
        Args:
            telegram_user: Пользователь Telegram
            message_type: Тип сообщения
            text: Текст сообщения
            metadata: Дополнительные данные
        """
        try:
            await BotMessage.objects.acreate(
                telegram_user=telegram_user,
                message_type=message_type,
                text=text[:1000],  # Ограничиваем длину
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Ошибка логирования сообщения: {e}")
    
    def get_parser(self, user: User) -> TextCommandParser:
        """
        Получает парсер команд для пользователя
        
        Args:
            user: Django User
            
        Returns:
            Экземпляр парсера команд
        """
        if not self.parser or self.parser.user != user:
            self.parser = TextCommandParser(user)
        return self.parser
    
    async def handle_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error: Exception,
    ) -> None:
        """
        Обрабатывает ошибки
        
        Args:
            update: Объект Update
            context: Контекст бота
            error: Исключение
        """
        logger.error(f"Ошибка в обработчике: {error}", exc_info=True)

        try:
            await notify_admins_about_exception(
                context.bot,
                error=error,
                where="BaseHandler.handle_error",
                update=update,
            )
        except Exception:
            # Never break user flow due to alerting.
            pass
        
        if update.effective_chat:
            await retry_telegram_call(
                lambda: context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="😔 Произошла ошибка. Попробуйте еще раз.",
                ),
                operation_name="send_error_message_to_user",
            )