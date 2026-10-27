from typing import Optional
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from decimal import Decimal
from telegram_bot.keyboards.navigation import attach_persistent_navigation


class ActionKeyboard:
    """Генератор клавиатур для действий с транзакциями"""
    
    @staticmethod
    def get_transaction_actions_keyboard(
        transaction_id: int,
        *,
        from_goal: bool = False,
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с действиями для транзакции
        
        Args:
            transaction_id: ID транзакции
            
        Returns:
            InlineKeyboardMarkup с действиями
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="✏️ Сумма",
                    callback_data=f"edit_amount_{transaction_id}",
                ),
                InlineKeyboardButton(
                    text="📅 Дата",
                    callback_data=f"edit_date_{transaction_id}",
                ),
                InlineKeyboardButton(
                    text="💬 Комментарий",
                    callback_data=f"edit_comment_{transaction_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Отмена",
                    callback_data=f"delete_transaction_{transaction_id}",
                ),
            ],
        ]
        if from_goal:
            buttons.insert(
                1,
                [
                    InlineKeyboardButton(
                        text="Из цели",
                        callback_data=f"tx_goal_{transaction_id}",
                    ),
                ],
            )

        keyboard = InlineKeyboardMarkup(buttons)
        return attach_persistent_navigation(
            keyboard,
            back_callback=f"transaction_actions_{transaction_id}",
        )
    
    @staticmethod
    def get_smart_amount_keyboard(
        category_name: str,
        suggested_amounts: list[Decimal],
    ) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с предлагаемыми суммами
        
        Args:
            category_name: Название категории
            suggested_amounts: Список предлагаемых сумм
            
        Returns:
            InlineKeyboardMarkup с суммами
        """
        buttons = []
        
        # Добавляем кнопки с суммами (по 2 в ряд)
        for i in range(0, len(suggested_amounts), 2):
            row = []
            for amount in suggested_amounts[i:i + 2]:
                button = InlineKeyboardButton(
                    text=f"{amount:,.0f}₽",
                    callback_data=f"amount_{amount}",
                )
                row.append(button)
            buttons.append(row)
        
        # Кнопка "Другая сумма"
        other_amount_button = InlineKeyboardButton(
            text="✏️ Другая сумма",
            callback_data="other_amount",
        )
        buttons.append([other_amount_button])
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру подтверждения действия
        
        Args:
            action: Действие для подтверждения
            
        Returns:
            InlineKeyboardMarkup с подтверждением
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=f"confirm_{action}",
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"cancel_{action}",
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def get_main_menu_keyboard() -> InlineKeyboardMarkup:
        """
        Создает главное меню бота
        
        Returns:
            InlineKeyboardMarkup с главным меню
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="💸 Добавить расход",
                    callback_data="add_expense",
                ),
                InlineKeyboardButton(
                    text="💰 Добавить доход",
                    callback_data="add_income",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="show_stats",
                ),
                InlineKeyboardButton(
                    text="📈 Отчет",
                    callback_data="show_report",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📋 Бюджеты",
                    callback_data="show_budgets",
                ),
                InlineKeyboardButton(
                    text="🎯 Цели",
                    callback_data="goals_menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 Неделя",
                    callback_data="weekly_digest",
                ),
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="settings",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 Повторы",
                    callback_data="recur_menu",
                ),
                InlineKeyboardButton(
                    text="🤝 Долги",
                    callback_data="debts_menu",
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(buttons) 