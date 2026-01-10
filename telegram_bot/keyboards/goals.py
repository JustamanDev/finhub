from decimal import Decimal

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram_bot.keyboards.navigation import attach_persistent_navigation


class GoalsKeyboard:
    @staticmethod
    def get_goals_menu_keyboard() -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="➕ Создать цель",
                        callback_data="goal_create",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📋 Мои цели",
                        callback_data="goals_list",
                    ),
                ],
            ]
        )
        return attach_persistent_navigation(keyboard, back_callback=None)

    @staticmethod
    def get_goals_list_keyboard(goals: list) -> InlineKeyboardMarkup:
        rows = []
        for g in goals:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🎯 {g.title}",
                        callback_data=f"goal_view_{g.id}",
                    )
                ]
            )
        if not rows:
            rows = [
                [
                    InlineKeyboardButton(
                        text="➕ Создать цель",
                        callback_data="goal_create",
                    )
                ]
            ]
        keyboard = InlineKeyboardMarkup(rows)
        return attach_persistent_navigation(keyboard, back_callback="goals_menu")

    @staticmethod
    def get_goal_card_keyboard(
        goal_id: int,
        quick_amount: Decimal | None = None,
    ) -> InlineKeyboardMarkup:
        rows = []
        if quick_amount is not None and quick_amount > 0:
            rub = int(quick_amount.to_integral_value())
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"⚡ Перевести {rub:,.0f} ₽",
                        callback_data=f"goal_quick_deposit_{goal_id}_{rub}",
                    ),
                ]
            )
        rows.extend(
            [
                [
                    InlineKeyboardButton(
                        text="➕ Внести",
                        callback_data=f"goal_deposit_{goal_id}",
                    ),
                    InlineKeyboardButton(
                        text="↩️ Снять",
                        callback_data=f"goal_withdraw_{goal_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🕓 История",
                        callback_data=f"goal_history_{goal_id}",
                    ),
                ],
            ]
        )
        keyboard = InlineKeyboardMarkup(rows)
        return attach_persistent_navigation(keyboard, back_callback="goals_list")

    @staticmethod
    def get_goal_input_keyboard(cancel_callback: str) -> InlineKeyboardMarkup:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="🔙 Отмена",
                        callback_data=cancel_callback,
                    ),
                ],
            ]
        )
        return attach_persistent_navigation(keyboard, back_callback=None)

