import logging
from datetime import datetime
import io
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async
from telegram.constants import ChatAction

from .base import BaseHandler
from telegram_bot.keyboards.reports import ReportKeyboard
from telegram_bot.services.report_service import ReportService
from telegram_bot.services.report_export_service import ReportExportService
from telegram_bot.utils.telegram_resilience import (
    safe_edit_message_text,
    send_or_edit_message,
)

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
        
        await send_or_edit_message(
            update,
            context,
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

    async def handle_export_excel_month(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        year: int,
        month: int,
    ) -> None:
        """
        Генерирует и отправляет Excel-файл за указанный месяц.

        UX:
        - не редактируем текущее сообщение с отчетом
        - отправляем файл отдельным сообщением, чтобы отчет оставался на экране
        """
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            export_service = ReportExportService(user)

            chat_id = None
            # CallbackQuery (чаще всего экспорт вызывается именно так)
            if hasattr(update, "answer"):
                await update.answer("Готовлю Excel…")
                if getattr(update, "message", None):
                    chat_id = update.message.chat_id

            # Обычное сообщение/Update
            if chat_id is None and hasattr(update, "effective_chat") and update.effective_chat:
                chat_id = update.effective_chat.id

            if chat_id is None:
                raise RuntimeError("Не удалось определить chat_id для отправки Excel")

            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            result = await export_service.build_monthly_excel(year, month)

            buf = io.BytesIO(result.content)
            buf.name = result.filename

            await context.bot.send_document(
                chat_id=chat_id,
                document=buf,
                caption=f"📥 Excel-отчет за {month:02d}.{year}",
            )
        except Exception:
            logger.exception("Ошибка экспорта Excel")
            # Пытаемся показать ошибку пользователю максимально мягко
            if hasattr(update, "message") and getattr(update, "message", None):
                await update.message.reply_text("❌ Не удалось сформировать Excel. Попробуйте позже.")
            elif hasattr(update, "edit_message_text"):
                await safe_edit_message_text(
                    update,
                    text="❌ Не удалось сформировать Excel. Попробуйте позже.",
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
        
        await send_or_edit_message(
            update,
            context,
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