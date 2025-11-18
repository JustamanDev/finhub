import logging
from datetime import datetime
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.reports import ReportKeyboard
from telegram_bot.services.report_service import ReportService

logger = logging.getLogger(__name__)


class ReportHandler(BaseHandler):
    """Обработчик отчетов"""
    
    async def handle_show_report(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает главное меню отчетов"""
        keyboard = ReportKeyboard.get_report_main_keyboard()
        
        message = (
            "📈 **Отчеты FinHub**\n\n"
            "Выберите тип отчета:\n"
            "• 📊 Текущий месяц - детальный отчет за текущий месяц\n"
            "• 📈 Все отчеты - навигация по всем периодам"
        )
        
        # Проверяем, является ли update CallbackQuery или Update
        if hasattr(update, 'callback_query'):
            # Это Update с callback_query
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
        elif hasattr(update, 'edit_message_text'):
            # Это CallbackQuery напрямую
            await update.edit_message_text(
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
        else:
            # Это обычное сообщение
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
    
    async def handle_current_report(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает отчет за текущий месяц"""
        now = datetime.now()
        await self._show_monthly_report(
            update,
            context,
            telegram_user,
            now.year,
            now.month,
        )
    
    async def handle_report_navigation(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        year: int,
        month: int,
    ) -> None:
        """Показывает отчет за указанный период"""
        await self._show_monthly_report(
            update,
            context,
            telegram_user,
            year,
            month,
        )
    
    async def _show_monthly_report(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        year: int,
        month: int,
    ) -> None:
        """Показывает месячный отчет"""
        user = await sync_to_async(lambda: telegram_user.user)()
        report_service = ReportService(user)
        
        # Получаем отчет
        report = await report_service.get_monthly_report(year, month)
        
        # Получаем доступные периоды для навигации
        available_periods = await report_service.get_available_periods()
        
        # Формируем сообщение
        message = self._format_report_message(report)
        
        # Создаем клавиатуру навигации
        keyboard = ReportKeyboard.get_report_navigation_keyboard(
            current_period={'year': year, 'month': month},
            available_periods=available_periods,
        )
        
        # Проверяем, является ли update CallbackQuery или Update
        if hasattr(update, 'callback_query'):
            # Это Update с callback_query
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
        elif hasattr(update, 'edit_message_text'):
            # Это CallbackQuery напрямую
            await update.edit_message_text(
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
        else:
            # Это обычное сообщение
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown',
            )
    
    def _format_report_message(self, report: dict) -> str:
        """Форматирует сообщение отчета"""
        message = f"📊 **Отчет за {report['period_name']}**\n\n"
        
        # Общая статистика
        message += "💰 **Общая статистика:**\n"
        message += f"• Доходы: {report['total_income']:,.0f}₽\n"
        message += f"• Расходы: {report['total_expenses']:,.0f}₽\n"
        message += f"• Баланс: {report['balance']:,.0f}₽\n\n"
        
        # Категории с остатками
        message += "📋 **Категории:**\n"
        
        # Сортируем категории по типу и остатку
        income_categories = []
        expense_categories = []
        
        for category_name, stats in report['categories'].items():
            category = stats['category']
            # Безопасно получаем тип категории
            category_type = getattr(category, 'type', 'expense')
            
            if category_type == 'income':
                income_categories.append((category_name, stats))
            else:
                expense_categories.append((category_name, stats))
        
        # Доходы
        if income_categories:
            message += "\n💰 **Доходы:**\n"
            for category_name, stats in sorted(income_categories):
                emoji = getattr(stats['category'], 'icon', '💰')
                message += (
                    f"• {emoji} {category_name}: "
                    f"{stats['income']:,.0f}₽"
                )
                # Показываем остаток только если он больше 0 (для доходов это не должно быть)
                if stats['balance'] > 0:
                    message += f" (остаток: {stats['balance']:,.0f}₽)"
                message += "\n"
        
        # Расходы
        if expense_categories:
            message += "\n💸 **Расходы:**\n"
            for category_name, stats in sorted(expense_categories):
                emoji = getattr(stats['category'], 'icon', '💸')
                message += (
                    f"• {emoji} {category_name}: "
                    f"{stats['expense']:,.0f}₽"
                )
                # Показываем остаток только для категорий с бюджетом
                if stats['balance'] > 0:
                    message += f" (остаток: {stats['balance']:,.0f}₽)"
                elif stats['balance'] < 0:
                    message += f" (превышен на {abs(stats['balance']):,.0f}₽)"
                message += "\n"
        
        return message 