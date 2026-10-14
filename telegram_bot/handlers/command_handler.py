import logging
from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

DEFAULT_WELCOME_MESSAGE = (
    "👋 Привет, {first_name}!\n\n"
    "💰 Я твой личный финансовый помощник FinHub!\n\n"
    "📝 Как добавлять операции:\n"
    "• 500 кофе - быстрый расход\n"
    "• +1000 зарплата - быстрый доход\n"
    "• 1500 - выбрать категорию\n\n"
    "🎯 Используй кнопки ниже или просто пиши суммы!"
)

DEFAULT_DEFAULT_CATEGORIES_MESSAGE = (
    "Для экономии времени я уже создал базовые категории доходов и расходов.\n"
    "Ты можешь переименовать их, добавить свои или удалить лишние — как удобно."
)


class CommandHandler(BaseHandler):
    """Обработчик команд бота"""

    @staticmethod
    def _render_template(template: str, first_name: str) -> str:
        """
        Рендерит шаблон текста из админки безопасно.

        Поддерживаем плейсхолдеры:
        - {first_name}
        - {firstName} (алиас)
        """
        # поддержка алиаса, чтобы пользователь мог писать camelCase
        normalized = template.replace("{firstName}", "{first_name}")
        try:
            return normalized.format(first_name=first_name)
        except Exception:
            # если в тексте встретились неизвестные {placeholders} — не падаем
            return template

    async def _get_bot_text(self, slug: str, default: str) -> str:
        from telegram_bot.models import BotText

        try:
            obj = await sync_to_async(
                lambda: BotText.objects.filter(
                    slug=slug,
                    is_active=True,
                ).first()
            )()
        except Exception:
            return default

        if not obj or not obj.text:
            return default
        return obj.text
    
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
            telegram_user, is_new_user, defaults_created_count = (
                await self.get_or_create_telegram_user_with_bootstrap(
                    update.effective_user
                )
            )

            welcome_template = await self._get_bot_text(
                slug="welcome_message",
                default=DEFAULT_WELCOME_MESSAGE,
            )
            welcome_text = self._render_template(
                welcome_template,
                first_name=update.effective_user.first_name or "",
            )

            if is_new_user and defaults_created_count > 0:
                defaults_message = await self._get_bot_text(
                    slug="default_categories_message",
                    default=DEFAULT_DEFAULT_CATEGORIES_MESSAGE,
                )
                welcome_text = f"{welcome_text}\n\n{defaults_message}"
            
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
                "• 500 кофе - расход на кофе, бот спросит валюту\n"
                "• +2000 подработка - доход от подработки\n"
                "• 1500 - выбрать категорию\n"
                "• 50000д кофе - сразу в донгах\n"
                "• 1500 руб такси - сразу в рублях\n\n"
                "Отчёты всегда в рублях. Донги пересчитываются по курсу ЦБ.\n\n"
                "⚡ Алиасы (настраиваются):\n"
                "• п500 - продукты 500₽\n"
                "• к200 - кофе 200₽\n"
                "• т100 - транспорт 100₽\n\n"
                "🎯 Категории автоматически определяются по словам!\n\n"
                "📊 Команды:\n"
                "• /start - главное меню\n"
                "• /stats - статистика за сегодня\n"
                "• /week - сводка текущей недели\n"
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

    async def week_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Показывает сводку текущей недели статьёй с таблицами."""
        try:
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user,
            )
            from telegram_bot.services.weekly_digest import push_current_week

            await push_current_week(
                context.bot,
                telegram_user,
                update.effective_chat.id,
            )
            await self.log_message(
                telegram_user,
                'incoming',
                '/week',
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