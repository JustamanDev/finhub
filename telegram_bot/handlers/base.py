import logging
from typing import (
    Dict,
    Any,
    Optional,
)
from telegram import (
    Update,
    User as TelegramUserModel,
)
from telegram.ext import ContextTypes
from django.contrib.auth.models import User

from telegram_bot.models import (
    TelegramUser,
    UserState,
    BotMessage,
)
from telegram_bot.utils.text_parser import TextCommandParser

logger = logging.getLogger(__name__)


class BaseHandler:
    """Базовый класс для всех обработчиков команд"""
    
    def __init__(self):
        self.parser = None
        
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
        try:
            tg_user = await TelegramUser.objects.aget(
                telegram_id=telegram_user.id
            )
        except TelegramUser.DoesNotExist:
            # Создаем Django User
            django_user = await User.objects.acreate(
                username=f"tg_{telegram_user.id}",
                first_name=telegram_user.first_name or '',
                last_name=telegram_user.last_name or '',
            )
            
            # Создаем TelegramUser
            tg_user = await TelegramUser.objects.acreate(
                user=django_user,
                telegram_id=telegram_user.id,
                username=telegram_user.username or '',
                first_name=telegram_user.first_name or '',
                last_name=telegram_user.last_name or '',
                language_code=telegram_user.language_code or 'ru',
            )
            
            # Создаем UserState
            await UserState.objects.acreate(telegram_user=tg_user)
            
        return tg_user
    
    async def get_user_state(self, telegram_user: TelegramUser) -> UserState:
        """
        Получает состояние пользователя
        
        Args:
            telegram_user: Объект TelegramUser
            
        Returns:
            Состояние пользователя
        """
        state, created = await UserState.objects.aget_or_create(
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
        
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="😔 Произошла ошибка. Попробуйте еще раз.",
            ) 