from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Dict, List


class ReportKeyboard:
    """Клавиатуры для отчетов"""
    
    @staticmethod
    def get_report_navigation_keyboard(
        current_period: Dict[str, int],
        available_periods: List[Dict[str, int]],
    ) -> InlineKeyboardMarkup:
        """
        Клавиатура навигации по отчетам
        
        Args:
            current_period: Текущий период {'year': int, 'month': int}
            available_periods: Доступные периоды
            
        Returns:
            InlineKeyboardMarkup с кнопками навигации
        """
        keyboard = []
        
        # Находим индекс текущего периода
        current_index = -1
        for i, period in enumerate(available_periods):
            if (period['year'] == current_period['year'] and 
                period['month'] == current_period['month']):
                current_index = i
                break
        
        # Кнопки навигации
        nav_buttons = []
        
        # Кнопка "Назад"
        if current_index > 0:
            prev_period = available_periods[current_index - 1]
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"report_prev_{prev_period['year']}_{prev_period['month']}"
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="report_disabled"
                )
            )
        
        # Кнопка "Вперед"
        if current_index < len(available_periods) - 1:
            next_period = available_periods[current_index + 1]
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"report_next_{next_period['year']}_{next_period['month']}"
                )
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data="report_disabled"
                )
            )
        
        keyboard.append(nav_buttons)
        
        # Действия для текущего периода
        year = current_period['year']
        month = current_period['month']
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="Файл за месяц",
                    callback_data=f"report_export_excel_{year}_{month}",
                ),
                InlineKeyboardButton(
                    text="Файл за год",
                    callback_data=f"report_export_year_{year}",
                ),
            ]
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="К отчётам",
                    callback_data="show_report",
                ),
            ]
        )

        # Кнопка "Главное меню"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu",
                )
            ]
        )
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_report_main_keyboard() -> InlineKeyboardMarkup:
        """Главная клавиатура отчетов"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="Этот месяц",
                    callback_data="report_current",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Файл за месяц",
                    callback_data="report_export_excel_current",
                ),
                InlineKeyboardButton(
                    text="Файл за год",
                    callback_data="report_export_year_current",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Другие месяцы",
                    callback_data="report_all",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard) 