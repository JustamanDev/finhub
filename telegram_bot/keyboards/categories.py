import logging
from typing import List
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from asgiref.sync import sync_to_async

from telegram_bot.models import TelegramUser
from telegram_bot.services.quick_categories import select_quick_categories
from telegram_bot.services.weekly_digest import vietnam_today
from categories.models import Category

logger = logging.getLogger(__name__)


class CategoryKeyboard:
    """Генератор клавиатур для выбора категорий"""
    
    MAX_COLUMNS = 2
    MAX_CATEGORIES_PER_PAGE = 10
    
    def __init__(self, telegram_user: TelegramUser):
        self.telegram_user = telegram_user
        self.user = None  # Будет установлен асинхронно
    
    async def get_categories_keyboard(
        self,
        transaction_type: str,
        _page: int = 0,
    ) -> InlineKeyboardMarkup:
        """Все активные категории этого типа, по две в ряд.

        Номер страницы оставлен для старых кнопок листания: список больше не режется.
        """
        categories = await self._get_user_categories(transaction_type)

        buttons = []
        for i in range(0, len(categories), self.MAX_COLUMNS):
            row = []
            for category in categories[i:i + self.MAX_COLUMNS]:
                button = InlineKeyboardButton(
                    text=f"{category.icon} {category.name}",
                    callback_data=f"category_{category.id}",
                )
                row.append(button)
            buttons.append(row)

        buttons.append([
            InlineKeyboardButton(
                text="⭐ Назад",
                callback_data=f"quick_back_{transaction_type}",
            ),
        ])

        switch_button = await self._get_switch_button(transaction_type)
        buttons.append([switch_button])
        
        # Кнопка "Главное меню"
        main_menu_button = InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu",
        )
        buttons.append([main_menu_button])
        
        return InlineKeyboardMarkup(buttons)
    
    async def get_frequent_categories_keyboard(
        self,
        transaction_type: str,
    ) -> InlineKeyboardMarkup:
        """
        Шесть категорий: отмеченные в настройках или самые частые за 30 дней.
        Остальные открываются кнопкой «Все категории».
        """
        if self.user is None:
            self.user = await sync_to_async(lambda: self.telegram_user.user)()

        menu = await sync_to_async(select_quick_categories)(
            self.user,
            transaction_type,
            vietnam_today(),
        )

        buttons = []
        for i in range(0, len(menu.categories), self.MAX_COLUMNS):
            row = []
            for category in menu.categories[i:i + self.MAX_COLUMNS]:
                row.append(InlineKeyboardButton(
                    text=f"{category.icon} {category.name}",
                    callback_data=f"category_{category.id}",
                ))
            buttons.append(row)

        if menu.total_active > len(menu.categories):
            buttons.append([
                InlineKeyboardButton(
                    text="📋 Все категории",
                    callback_data=f"all_categories_{transaction_type}",
                ),
            ])

        switch_button = await self._get_switch_button(transaction_type)
        buttons.append([switch_button])
        buttons.append([
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="main_menu",
            ),
        ])
        return InlineKeyboardMarkup(buttons)

    async def _get_user_categories(self, transaction_type: str) -> List[Category]:
        """
        Получает категории пользователя по типу
        
        Args:
            transaction_type: 'expense' или 'income'
            
        Returns:
            Список категорий пользователя
        """
        # Получаем пользователя асинхронно
        if self.user is None:
            self.user = await sync_to_async(lambda: self.telegram_user.user)()
        
        # Получаем категории асинхронно
        categories = await sync_to_async(list)(
            Category.objects.filter(
                user=self.user,
                type=transaction_type,
                is_active=True,
            ).order_by('name')
        )
        
        return categories
    
    async def _get_navigation_buttons(
        self,
        transaction_type: str,
        current_page: int,
        total_categories: int,
    ) -> List[List[InlineKeyboardButton]]:
        """
        Создает кнопки навигации по страницам
        
        Args:
            transaction_type: Тип транзакции
            current_page: Текущая страница
            total_categories: Общее количество категорий
            
        Returns:
            Список рядов с кнопками навигации
        """
        total_pages = (total_categories - 1) // self.MAX_CATEGORIES_PER_PAGE + 1
        
        if total_pages <= 1:
            return []
        
        navigation_row = []
        
        # Кнопка "Назад"
        if current_page > 0:
            prev_button = InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"page_{transaction_type}_{current_page - 1}",
            )
            navigation_row.append(prev_button)
        
        # Кнопка "Вперед"
        if current_page < total_pages - 1:
            next_button = InlineKeyboardButton(
                text="Вперед ➡️",
                callback_data=f"page_{transaction_type}_{current_page + 1}",
            )
            navigation_row.append(next_button)
        
        return [navigation_row] if navigation_row else []
    
    async def _get_switch_button(self, current_type: str) -> InlineKeyboardButton:
        """
        Создает кнопку переключения типа транзакции
        
        Args:
            current_type: Текущий тип транзакции
            
        Returns:
            Кнопка переключения
        """
        if current_type == 'expense':
            return InlineKeyboardButton(
                text="💰 ← К доходам",
                callback_data="switch_to_income",
            )
        else:
            return InlineKeyboardButton(
                text="💸 ← К расходам",
                callback_data="switch_to_expense",
            ) 