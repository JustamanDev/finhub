import logging
from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


class CommandHandler(BaseHandler):
    """Обработчик команд бота"""
    
    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Обрабатывает команду /start
        
        Args:
            update: Объект Update
            context: Контекст бота
        """
        try:
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user
            )
            
            welcome_text = (
                f"👋 Привет, {update.effective_user.first_name}!\n\n"
                "💰 Я твой личный финансовый помощник FinHub!\n\n"
                "📝 Как добавлять операции:\n"
                "• 500 кофе - быстрый расход\n"
                "• +1000 зарплата - быстрый доход\n"
                "• 1500 - выбрать категорию\n\n"
                "🎯 Используй кнопки ниже или просто пиши суммы!"
            )
            
            keyboard = ActionKeyboard.get_main_menu_keyboard()
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=welcome_text,
                reply_markup=keyboard,
            )
            
            await self.log_message(
                telegram_user,
                'incoming',
                '/start',
            )
            
        except Exception as e:
            await self.handle_error(update, context, e)
    
    async def help_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Обрабатывает команду /help
        
        Args:
            update: Объект Update
            context: Контекст бота
        """
        try:
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user
            )
            
            help_text = (
                "🆘 Справка по использованию FinHub\n\n"
                "📝 Способы добавления операций:\n\n"
                "🚀 Быстрый ввод:\n"
                "• 500 кофе - расход на кофе\n"
                "• +2000 подработка - доход от подработки\n"
                "• 1500 - выбрать категорию\n\n"
                "⚡ Алиасы (настраиваются):\n"
                "• п500 - продукты 500₽\n"
                "• к200 - кофе 200₽\n"
                "• т100 - транспорт 100₽\n\n"
                "🎯 Категории автоматически определяются по словам!\n\n"
                "📊 Команды:\n"
                "• /start - главное меню\n"
                "• /stats - статистика за сегодня\n"
                "• /help - эта справка"
            )
            
            keyboard = ActionKeyboard.get_main_menu_keyboard()
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=help_text,
                reply_markup=keyboard,
            )
            
            await self.log_message(
                telegram_user,
                'incoming',
                '/help',
            )
            
        except Exception as e:
            await self.handle_error(update, context, e)
    
    async def stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Обрабатывает команду /stats
        
        Args:
            update: Объект Update
            context: Контекст бота
        """
        try:
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user
            )
            # Достаем связанного Django-пользователя через sync_to_async,
            # чтобы не дергать ORM напрямую из async-контекста
            user = await sync_to_async(lambda: telegram_user.user)()
            transaction_service = TransactionService(user)
            stats = await transaction_service.get_today_statistics()
            
            stats_text = (
                f"📊 Статистика за сегодня:\n\n"
                f"💸 Расходы: {stats['expenses']:,.0f}₽\n"
                f"💰 Доходы: {stats['income']:,.0f}₽\n"
                f"💵 Баланс: {stats['balance']:,.0f}₽\n\n"
            )
            
            if stats['balance'] > 0:
                stats_text += "✅ Сегодня в плюсе!"
            elif stats['balance'] < 0:
                stats_text += "⚠️ Сегодня трат больше доходов"
            else:
                stats_text += "⚖️ Доходы равны расходам"
            
            keyboard = ActionKeyboard.get_main_menu_keyboard()
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=stats_text,
                reply_markup=keyboard,
            )
            
            await self.log_message(
                telegram_user,
                'incoming',
                '/stats',
            )
            
        except Exception as e:
            await self.handle_error(update, context, e) 