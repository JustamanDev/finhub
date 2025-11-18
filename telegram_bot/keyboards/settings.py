from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List


class SettingsKeyboard:
    """Клавиатуры для настроек"""
    
    @staticmethod
    def get_main_settings_keyboard() -> InlineKeyboardMarkup:
        """Главное меню настроек"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="📂 Категории",
                    callback_data="settings_categories"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Общие настройки",
                    callback_data="settings_general"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_categories_keyboard() -> InlineKeyboardMarkup:
        """Меню управления категориями"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="➕ Добавить категорию",
                    callback_data="category_add"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Доходы",
                    callback_data="category_list_income"
                ),
                InlineKeyboardButton(
                    text="💸 Расходы",
                    callback_data="category_list_expense"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings"
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_category_list_keyboard(
        categories: List,
        action: str = "view"
    ) -> InlineKeyboardMarkup:
        """Клавиатура со списком категорий"""
        keyboard = []
        
        # Группируем категории по типу
        income_categories = [c for c in categories if c.type == 'income']
        expense_categories = [c for c in categories if c.type == 'expense']
        
        # Доходы
        if income_categories:
            keyboard.append([
                InlineKeyboardButton(
                    text="💰 Доходы",
                    callback_data="category_header_income"
                )
            ])
            
            for category in income_categories:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"category_{action}_{category.id}"
                    )
                ])
        
        # Расходы
        if expense_categories:
            keyboard.append([
                InlineKeyboardButton(
                    text="💸 Расходы",
                    callback_data="category_header_expense"
                )
            ])
            
            for category in expense_categories:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"category_{action}_{category.id}"
                    )
                ])
        
        # Навигация
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="settings_categories"
            ),
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_category_actions_keyboard(category_id: int, has_budget: bool = False) -> InlineKeyboardMarkup:
        """Действия с конкретной категорией"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✏️ Переименовать",
                    callback_data=f"category_rename_{category_id}"
                ),
                InlineKeyboardButton(
                    text="🎨 Сменить иконку",
                    callback_data=f"category_icon_{category_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Изменить тип",
                    callback_data=f"category_type_{category_id}"
                ),
                InlineKeyboardButton(
                    text="🗑️ Удалить",
                    callback_data=f"category_delete_{category_id}"
                ),
            ],
        ]
        
        # Добавляем кнопку бюджета только для категорий расходов
        # (проверка будет в обработчике)
        keyboard.append([
            InlineKeyboardButton(
                text="✏️ Изменить лимит" if has_budget else "💰 Установить лимит на месяц",
                callback_data=f"category_budget_{category_id}"
            ),
        ])
        
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="category_edit"
            ),
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_icon_selection_keyboard(
        category_id: int,
        icons: List[str]
    ) -> InlineKeyboardMarkup:
        """Клавиатура выбора иконки"""
        keyboard = []
        
        # Группируем иконки по 5 в ряд
        for i in range(0, len(icons), 5):
            row = []
            for icon in icons[i:i + 5]:
                row.append(
                    InlineKeyboardButton(
                        text=icon,
                        callback_data=f"category_icon_select_{category_id}_{icon}"
                    )
                )
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=f"category_actions_{category_id}"
            ),
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_category_type_keyboard(category_id: int) -> InlineKeyboardMarkup:
        """Клавиатура выбора типа категории"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="💰 Доход",
                    callback_data=f"category_type_select_{category_id}_income"
                ),
                InlineKeyboardButton(
                    text="💸 Расход",
                    callback_data=f"category_type_select_{category_id}_expense"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"category_actions_{category_id}"
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_confirmation_keyboard(
        action: str,
        category_id: int
    ) -> InlineKeyboardMarkup:
        """Клавиатура подтверждения действия"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✅ Да",
                    callback_data=f"category_confirm_{action}_{category_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Нет",
                    callback_data=f"category_actions_{category_id}"
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(keyboard) 

    @staticmethod
    def get_category_type_selection_keyboard(action: str = "add") -> InlineKeyboardMarkup:
        """Клавиатура для выбора типа категории"""
        keyboard = [
            [
                InlineKeyboardButton(
                    text="💰 Доходы",
                    callback_data=f"category_{action}_type_income"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💸 Расходы",
                    callback_data=f"category_{action}_type_expense"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings_categories"
                ),
            ],
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_category_list_by_type_keyboard(
        categories: List,
        category_type: str,
        action: str = "view"
    ) -> InlineKeyboardMarkup:
        """Клавиатура со списком категорий определенного типа"""
        keyboard = []
        
        # Категории уже отфильтрованы, просто создаем кнопки
        if not categories:
            type_name = "доходов" if category_type == "income" else "расходов"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ Нет категорий {type_name}",
                    callback_data="no_action"
                )
            ])
        else:
            for category in categories:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"category_{action}_{category.id}"
                    )
                ])
        
        # Кнопки навигации
        keyboard.append([
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="settings_categories"
            ),
        ])
        
        return InlineKeyboardMarkup(keyboard) 