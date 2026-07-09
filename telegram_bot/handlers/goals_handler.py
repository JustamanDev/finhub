import logging
from datetime import datetime
from decimal import Decimal

from asgiref.sync import sync_to_async
from telegram import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from telegram_bot.handlers.base import BaseHandler
from telegram_bot.keyboards.goals import GoalsKeyboard
from telegram_bot.services.goal_service import GoalService

logger = logging.getLogger(__name__)


class GoalsHandler(BaseHandler):
    async def handle_goals_menu(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        message = (
            "🎯 **Цели (конверты)**\n\n"
            "Цели помогают откладывать деньги на важные покупки и планы.\n\n"
            "• ➕ Создать цель\n"
            "• 📋 Посмотреть прогресс\n"
            "• ➕/↩️ Вносить и снимать средства\n\n"
            "💡 Важно: «пополнение цели» — это не расход, а резервирование. "
            "Оно уменьшает «свободно для трат» в текущем месяце."
        )
        keyboard = GoalsKeyboard.get_goals_menu_keyboard()
        await self._send_or_edit_message(update, context, message, keyboard)

    async def handle_goals_list(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        service = GoalService(user)
        goals = await service.list_goals()

        if goals:
            message = "📋 **Мои цели:**\n\nВыберите цель:"
        else:
            message = (
                "📋 **Мои цели**\n\n"
                "Пока целей нет.\n\n"
                "Нажмите «➕ Создать цель», чтобы начать откладывать."
            )

        keyboard = GoalsKeyboard.get_goals_list_keyboard(goals)
        await self._send_or_edit_message(update, context, message, keyboard)

    async def handle_goal_view(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        service = GoalService(user)
        data = await service.get_goal_card_data(goal_id)
        if not data:
            await self._send_or_edit_message(
                update,
                context,
                "❌ Цель не найдена или недоступна.",
                GoalsKeyboard.get_goals_list_keyboard([]),
            )
            return

        goal = data['goal']
        balance = data['balance']
        target = data['target']
        remaining_total = data['remaining_total']
        progress_pct = data['progress_pct']

        # план/факт
        planned_per_month = data['planned_per_month']
        deposited_this_month = data['deposited_this_month']
        remaining_this_month = data['remaining_this_month']
        free_funds = data['free_funds_this_month']

        lines = []
        lines.append(f"🎯 **{goal.title}**")
        if goal.deadline:
            lines.append(f"📅 Дедлайн: {goal.deadline.strftime('%d.%m.%Y')}")
        lines.append("")
        lines.append(f"✅ Накоплено: **{balance:,.0f} ₽** из **{target:,.0f} ₽** ({progress_pct:.1f}%)")
        lines.append(f"⏳ Осталось: **{remaining_total:,.0f} ₽**")

        if planned_per_month is not None:
            lines.append("")
            lines.append("📆 **План / факт (текущий месяц):**")
            lines.append(f"• План: {planned_per_month:,.0f} ₽")
            lines.append(f"• Внесено: {deposited_this_month:,.0f} ₽")
            lines.append(f"• Осталось внести: {remaining_this_month:,.0f} ₽")

        lines.append("")
        lines.append(f"🧾 Свободно для трат в этом месяце: **{free_funds:,.0f} ₽**")

        quick_amount = None
        recs = data['recommendations']
        if recs:
            top = recs[0]
            quick_amount = top.suggested_amount
            lines.append("")
            lines.append("💡 **Подсказка:**")
            lines.append(top.description)

        keyboard = GoalsKeyboard.get_goal_card_keyboard(goal_id, quick_amount=quick_amount)
        await self._send_or_edit_message(update, context, "\n".join(lines), keyboard)

    async def handle_goal_history(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        service = GoalService(user)
        goal = await service.get_goal(goal_id)
        if not goal:
            await self._send_or_edit_message(
                update,
                context,
                "❌ Цель не найдена.",
                GoalsKeyboard.get_goals_list_keyboard([]),
            )
            return

        entries = await service.get_recent_entries(goal_id, limit=20)
        message = f"🕓 **История: {goal.title}**\n\n"
        if not entries:
            message += "Пока нет операций."
        else:
            for e in entries:
                dt = e.occurred_at
                if isinstance(dt, datetime):
                    dt_str = dt.strftime("%d.%m.%Y")
                else:
                    dt_str = str(dt)
                sign = "➕" if e.amount >= 0 else "↩️"
                message += f"{sign} {dt_str} — {abs(e.amount):,.0f} ₽"
                if e.comment:
                    message += f" — {e.comment}"
                message += "\n"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 К цели",
                        callback_data=f"goal_view_{goal_id}",
                    )
                ]
            ]
        )
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )

    async def _send_or_edit_message(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        message: str,
        keyboard,
    ) -> None:
        from telegram_bot.utils.telegram_resilience import send_or_edit_message

        await send_or_edit_message(
            update,
            context,
            text=message,
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

