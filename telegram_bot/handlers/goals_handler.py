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
            "🎯 **Цели и конверты**\n\n"
            "Цель — копите к сумме. Процент растёт, пока откладываете.\n"
            "Конверт — деньги уже лежат отдельно. Процента нет, видно только остаток.\n\n"
            "Пополнение — не расход, а резерв. "
            "Оно уменьшает «свободно для трат» в текущем месяце.\n"
            "Архив прячет запись из списков. Деньги на ней остаются зарезервированы."
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
            message = "📋 **Мои цели и конверты:**\n\nВыберите запись:"
        else:
            message = (
                "📋 **Мои цели и конверты**\n\n"
                "Пока пусто.\n\n"
                "Цель — если копите к сумме. Конверт — если деньги уже отложены и будут тратиться."
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
        from transactions.currencies import base_currency_of

        currency = await sync_to_async(base_currency_of)(telegram_user)
        lines = self._card_lines(data, currency)
        quick_amount = None
        if goal.status != goal.ARCHIVED and not goal.is_envelope:
            recs = data['recommendations']
            if recs:
                top = recs[0]
                quick_amount = top.suggested_amount
                lines.append("")
                lines.append("💡 **Подсказка:**")
                lines.append(top.description)

        if goal.status == goal.ARCHIVED:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="↩️ Вернуть из архива",
                            callback_data=f"goal_restore_{goal_id}",
                        )
                    ],
                ]
            )
            from telegram_bot.keyboards.navigation import attach_persistent_navigation

            keyboard = attach_persistent_navigation(keyboard, back_callback="goals_archive")
        else:
            keyboard = GoalsKeyboard.get_goal_card_keyboard(goal_id, quick_amount=quick_amount)
        await self._send_or_edit_message(update, context, "\n".join(lines), keyboard)

    @staticmethod
    def _card_lines(data: dict, currency: str = 'RUB') -> list[str]:
        from transactions.currencies import symbol_of

        sym = symbol_of(currency)
        goal = data['goal']
        balance = data['balance']
        free_funds = data['free_funds_this_month']
        lines: list[str] = []
        if goal.is_envelope:
            lines.append(f"📦 **{goal.title}**")
            if goal.status == goal.ARCHIVED:
                lines.append("В архиве. Новые траты из него списать нельзя.")
            lines.append("")
            lines.append(f"На конверте лежит **{balance:,.0f} {sym}**")
            deposited = data['deposited_total']
            spent = data['spent']
            withdrawn = data['withdrawn_total']
            if deposited or spent or withdrawn:
                lines.append(
                    f"Внесено {deposited:,.0f} {sym}, потрачено {spent:,.0f} {sym}"
                    + (f", снято {withdrawn:,.0f} {sym}" if withdrawn else "")
                )
        else:
            target = data['target']
            remaining_total = data['remaining_total']
            progress_pct = data['progress_pct']
            lines.append(f"🎯 **{goal.title}**")
            if goal.status == goal.ARCHIVED:
                lines.append("В архиве.")
            if goal.deadline:
                lines.append(f"📅 Дедлайн: {goal.deadline.strftime('%d.%m.%Y')}")
            lines.append("")
            lines.append(
                f"✅ Накоплено: **{data['committed']:,.0f} {sym}** из **{target:,.0f} {sym}** "
                f"({progress_pct:.1f}%)"
            )
            if data['spent']:
                lines.append(f"🛒 Потрачено из цели: **{data['spent']:,.0f} {sym}**")
                lines.append(f"Сейчас лежит: **{balance:,.0f} {sym}**")
            lines.append(f"⏳ Осталось накопить: **{remaining_total:,.0f} {sym}**")

            planned_per_month = data['planned_per_month']
            if planned_per_month is not None:
                lines.append("")
                lines.append("📆 **План / факт (текущий месяц):**")
                lines.append(f"• План: {planned_per_month:,.0f} {sym}")
                lines.append(f"• Внесено: {data['deposited_this_month']:,.0f} {sym}")
                lines.append(f"• Осталось внести: {data['remaining_this_month']:,.0f} {sym}")

            from telegram_bot.services.goal_eta import format_goal_eta_lines

            if data['eta'] is not None:
                eta_lines = format_goal_eta_lines(data['eta'])
                if eta_lines:
                    lines.append("")
                    lines.extend(eta_lines)

        lines.append("")
        lines.append(f"🧾 Свободно для трат в этом месяце: **{free_funds:,.0f} {sym}**")
        return lines

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

        from transactions.currencies import base_currency_of, symbol_of

        sym = symbol_of(await sync_to_async(base_currency_of)(telegram_user))
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
                message += f"{sign} {dt_str} — {abs(e.amount):,.0f} {sym}"
                if e.comment:
                    message += f" — {e.comment}"
                message += "\n"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 К конверту" if goal.is_envelope else "🔙 К цели",
                        callback_data=f"goal_view_{goal_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu",
                    )
                ],
            ]
        )
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )

    async def handle_goals_archive(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        goals = await GoalService(user).list_archived()
        if goals:
            message = (
                "🗄 **Архив**\n\n"
                "Эти цели и конверты скрыты из списков и из кнопки «Из цели».\n"
                "Деньги на них по-прежнему в резерве. Нажмите, чтобы вернуть."
            )
        else:
            message = "🗄 **Архив**\n\nПока пусто."
        keyboard = GoalsKeyboard.get_archive_list_keyboard(goals)
        await self._send_or_edit_message(update, context, message, keyboard)

    async def handle_goal_archive_confirm(
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
            await self.handle_goals_list(update, context, telegram_user)
            return
        from transactions.currencies import base_currency_of, symbol_of

        sym = symbol_of(await sync_to_async(base_currency_of)(telegram_user))
        balance = await service.get_goal_balance(goal_id)
        name = "конверт" if goal.is_envelope else "цель"
        lines = [f"🗄 **Убрать {name} «{goal.title}» в архив?**", ""]
        lines.append("Он пропадёт из списка и из кнопки «Из цели». История останется.")
        if balance > 0:
            lines.append("")
            lines.append(
                f"Сейчас там лежит **{balance:,.0f} {sym}**. "
                "В «свободно» эта сумма не вернётся. Чтобы вернуть деньги, сначала снимите их."
            )
        lines.append("")
        lines.append("Вернуть из архива можно в любой момент.")
        keyboard = GoalsKeyboard.get_archive_confirm_keyboard(goal_id)
        await self._send_or_edit_message(update, context, "\n".join(lines), keyboard)

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

