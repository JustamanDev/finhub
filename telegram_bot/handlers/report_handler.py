import logging
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


def _chat_id(update: Update | CallbackQuery) -> int | None:
    message = getattr(update, 'message', None)
    if message is not None and getattr(message, 'chat_id', None):
        return message.chat_id
    chat = getattr(update, 'effective_chat', None)
    if chat is not None:
        return chat.id
    return None


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
            "Отчёты\n\n"
            "Этот месяц — сводка в чате.\n"
            "Файл за месяц — Excel этого месяца.\n"
            "Файл за год — Excel всего года.\n"
            "Другие месяцы — листать прошлые периоды."
        )
        
        await send_or_edit_message(
            update,
            context,
            text=message,
            reply_markup=keyboard,
        )
    
    async def handle_current_report(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает отчет за текущий месяц"""
        from telegram_bot.services.weekly_digest import vietnam_today

        today = vietnam_today()
        await self._show_monthly_report(
            update,
            context,
            telegram_user,
            today.year,
            today.month,
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
        """Файл месяца отдельным сообщением, сводка в чате остаётся на экране."""
        await self._send_excel(
            update,
            context,
            telegram_user,
            lambda service: service.build_monthly_excel(year, month),
        )

    async def handle_export_excel_year(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        year: int,
    ) -> None:
        """Файл календарного года отдельным сообщением."""
        await self._send_excel(
            update,
            context,
            telegram_user,
            lambda service: service.build_yearly_excel(year),
        )

    async def _send_excel(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        build,
    ) -> None:
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            export_service = ReportExportService(user)

            chat_id = None
            if hasattr(update, 'answer'):
                await update.answer('Готовлю файл…')
                if getattr(update, 'message', None):
                    chat_id = update.message.chat_id

            if chat_id is None and hasattr(update, 'effective_chat') and update.effective_chat:
                chat_id = update.effective_chat.id

            if chat_id is None:
                raise RuntimeError('Не удалось определить chat_id для отправки Excel')

            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            result = await build(export_service)

            buf = io.BytesIO(result.content)
            buf.name = result.filename

            await context.bot.send_document(
                chat_id=chat_id,
                document=buf,
                caption=result.caption,
            )
        except Exception:
            logger.exception('Ошибка экспорта Excel')
            if hasattr(update, 'message') and getattr(update, 'message', None):
                await update.message.reply_text('Не удалось сформировать файл. Попробуйте позже.')
            elif hasattr(update, 'edit_message_text'):
                await safe_edit_message_text(
                    update,
                    text='Не удалось сформировать файл. Попробуйте позже.',
                )
    
    async def _show_monthly_report(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        year: int,
        month: int,
    ) -> None:
        """Месяц отдельной статьёй: старое сообщение с меню не переписывается."""
        from telegram_bot.services.weekly_digest import (
            build_month_digest,
            render_legacy_html,
            render_rich_html,
            send_rich_article,
            vietnam_today,
        )

        user = await sync_to_async(lambda: telegram_user.user)()
        today = vietnam_today()
        digest = await sync_to_async(build_month_digest)(user, year, month, today)
        available_periods = await ReportService(user).get_available_periods()
        keyboard = ReportKeyboard.get_report_navigation_keyboard(
            current_period={'year': year, 'month': month},
            available_periods=available_periods,
        )
        chat_id = _chat_id(update)
        if hasattr(update, 'answer'):
            await update.answer()
        if chat_id is None:
            await send_or_edit_message(
                update,
                context,
                text=render_legacy_html(digest),
                reply_markup=keyboard,
                parse_mode='HTML',
            )
            return
        await send_rich_article(
            context.bot,
            chat_id,
            html=render_rich_html(digest),
            legacy_html=render_legacy_html(digest),
            reply_markup=keyboard,
            fallback_hint='Листать месяц:',
        ) 