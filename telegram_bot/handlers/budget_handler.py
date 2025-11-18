import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.keyboards.navigation import attach_persistent_navigation

logger = logging.getLogger(__name__)


class BudgetHandler(BaseHandler):
    """Обработчик управления бюджетами"""
    
    async def handle_show_budgets(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает главное меню бюджетов"""
        message = (
            "🎯 **Управление бюджетами**\n\n"
            "Здесь вы можете настроить месячные бюджеты для категорий:\n"
            "• 📊 Просмотр текущих бюджетов\n"
            "• ➕ Добавить новый бюджет\n"
            "• ✏️ Редактировать существующие бюджеты\n"
            "• 🗑️ Удалить бюджеты\n\n"
            "Бюджеты помогают контролировать расходы и получать уведомления при превышении."
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="📊 Просмотр бюджетов",
                    callback_data="budgets_view"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить бюджет",
                    callback_data="budgets_add"
                ),
            ],
        ])
        keyboard = attach_persistent_navigation(keyboard, back_callback=None)
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_budgets_view(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает список бюджетов"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        # Получаем активные бюджеты пользователя
        budgets = await sync_to_async(list)(
            Budget.objects.filter(
                user=user,
                is_active=True,
            ).select_related('category')
        )
        
        if not budgets:
            message = (
                "📊 **Текущие бюджеты**\n\n"
                "У вас пока нет установленных бюджетов.\n\n"
                "Бюджеты помогают контролировать расходы по категориям. "
                "При превышении бюджета вы получите уведомление."
            )
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="➕ Добавить бюджет",
                        callback_data="budgets_add"
                    ),
                ],
            ])
            keyboard = attach_persistent_navigation(keyboard, back_callback="show_budgets")
        else:
            # Формируем список бюджетов
            budgets_text = "📊 **Ваши бюджеты:**\n\n"
            keyboard_buttons = []
            
            for budget in budgets:
                # Оборачиваем свойства в sync_to_async
                spent_percent = await sync_to_async(lambda b: b.spent_percentage)(budget)
                spent_amount = await sync_to_async(lambda b: b.spent_amount)(budget)
                remaining_amount = await sync_to_async(lambda b: b.remaining_amount)(budget)
                
                status_icon = "🟢" if spent_percent < 80 else "🟡" if spent_percent < 100 else "🔴"
                
                budgets_text += (
                    f"• {budget.category.icon} {budget.category.name}\n"
                    f"  {budget.amount:,.2f} ₽ ({spent_percent:.1f}%)\n"
                    f"  Потрачено: {spent_amount:,.2f} ₽\n"
                    f"  Остаток: {remaining_amount:,.2f} ₽\n"
                    f"  {status_icon} {budget.get_period_type_display()}\n\n"
                )
                
                # Добавляем кнопку для каждого бюджета
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{budget.category.icon} {budget.category.name}",
                        callback_data=f"budget_detail_{budget.id}"
                    ),
                ])
            
            # Добавляем кнопки управления
            keyboard_buttons.extend([
                [
                    InlineKeyboardButton(
                        text="➕ Добавить бюджет",
                        callback_data="budgets_add"
                    ),
                ],
            ])
            
            message = budgets_text
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            keyboard = attach_persistent_navigation(keyboard, back_callback="show_budgets")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_budget_detail(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает детали бюджета"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get, thread_sensitive=True)(
                id=budget_id,
                user=user,
                is_active=True,
            )
        except Budget.DoesNotExist:
            await self._send_error_message(
                update,
                context,
                "❌ Бюджет не найден или недоступен."
            )
            return
        
        # Получаем свойства бюджета
        spent_percent = await sync_to_async(lambda b: b.spent_percentage)(budget)
        spent_amount = await sync_to_async(lambda b: b.spent_amount)(budget)
        remaining_amount = await sync_to_async(lambda b: b.remaining_amount)(budget)
        days_remaining = await sync_to_async(lambda b: b.days_remaining)(budget)
        daily_budget = await sync_to_async(lambda b: b.daily_budget_remaining)(budget)
        
        status_icon = "🟢" if spent_percent < 80 else "🟡" if spent_percent < 100 else "🔴"
        
        message = (
            f"📊 **Бюджет: {budget.category.icon} {budget.category.name}**\n\n"
            f"💰 **План:** {budget.amount:,.2f} ₽\n"
            f"💸 **Потрачено:** {spent_amount:,.2f} ₽\n"
            f"✅ **Остаток:** {remaining_amount:,.2f} ₽\n"
            f"📈 **Выполнение:** {spent_percent:.1f}% {status_icon}\n"
            f"📅 **Период:** {budget.get_period_type_display()}\n"
            f"📆 **Даты:** {budget.start_date} - {budget.end_date}\n"
            f"⏰ **Дней осталось:** {days_remaining}\n"
            f"💡 **Дневной бюджет:** {daily_budget:,.2f} ₽"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"budget_edit_{budget.id}"
                ),
                InlineKeyboardButton(
                    text="🗑️ Удалить",
                    callback_data=f"budget_delete_{budget.id}"
                ),
            ],
        ])
        keyboard = attach_persistent_navigation(keyboard, back_callback="budgets_view")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_budgets_add(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает форму добавления бюджета"""
        from asgiref.sync import sync_to_async
        from categories.models import Category
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        # Получаем категории расходов пользователя
        expense_categories = await sync_to_async(list)(
            Category.objects.filter(
                user=user,
                type='expense',
                is_active=True,
            )
        )
        
        if not expense_categories:
            message = (
                "❌ **Нет доступных категорий**\n\n"
                "Для создания бюджета нужны категории расходов. "
                "Сначала создайте категории в настройках."
            )
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="show_budgets"
                    ),
                ],
            ])
            keyboard = attach_persistent_navigation(keyboard, back_callback="show_budgets")
        else:
            message = (
                "➕ **Добавить бюджет**\n\n"
                "Выберите категорию для создания бюджета:"
            )
            
            keyboard_buttons = []
            for category in expense_categories:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"budget_add_for_category_{category.id}"
                    ),
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="show_budgets"
                ),
            ])
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            keyboard = attach_persistent_navigation(keyboard, back_callback="show_budgets")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_budget_add_for_category(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает форму для ввода суммы бюджета"""
        from asgiref.sync import sync_to_async
        from categories.models import Category
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            category = await sync_to_async(Category.objects.get)(
                id=category_id,
                user=user,
                type='expense',
                is_active=True,
            )
        except Category.DoesNotExist:
            await self._send_error_message(
                update,
                context,
                "❌ Категория не найдена."
            )
            return
        
        # Сохраняем выбранную категорию в контексте
        context.user_data['budget_category_id'] = category_id
        
        message = (
            f"💰 **Создание бюджета для {category.icon} {category.name}**\n\n"
            "Введите сумму бюджета на месяц (в рублях):\n\n"
            "Примеры: 5000, 10000, 15000"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="budgets_add"
                ),
            ],
        ])
        keyboard = attach_persistent_navigation(keyboard, back_callback="budgets_add")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
        
        # Устанавливаем состояние ожидания ввода суммы
        context.user_data['waiting_for_budget_amount'] = True
    
    async def handle_budget_edit(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает форму для редактирования бюджета"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get, thread_sensitive=True)(
                id=budget_id,
                user=user,
                is_active=True,
            )
        except Budget.DoesNotExist:
            await self._send_error_message(
                update,
                context,
                "❌ Бюджет не найден."
            )
            return
        
        # Сохраняем ID бюджета для редактирования в контексте
        context.user_data['editing_budget_id'] = budget_id
        
        # Получаем данные категории через sync_to_async
        category_icon = await sync_to_async(lambda: budget.category.icon)()
        category_name = await sync_to_async(lambda: budget.category.name)()
        
        message = (
            f"✏️ **Редактирование бюджета**\n\n"
            f"💰 **Категория:** {category_icon} {category_name}\n"
            f"💸 **Текущая сумма:** {budget.amount:,.2f} ₽\n\n"
            "Введите новую сумму бюджета (в рублях):\n\n"
            "Примеры: 5000, 10000, 15000"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"budget_detail_{budget_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                ),
            ],
        ])
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
        
        # Устанавливаем состояние ожидания ввода суммы
        context.user_data['waiting_for_budget_amount'] = True
    
    async def handle_budget_delete_confirmation(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает подтверждение удаления бюджета"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get)(
                id=budget_id,
                user=user,
                is_active=True,
            )
        except Budget.DoesNotExist:
            await self._send_error_message(
                update,
                context,
                "❌ Бюджет не найден."
            )
            return
        
        # Получаем данные категории через sync_to_async
        category_icon = await sync_to_async(lambda: budget.category.icon)()
        category_name = await sync_to_async(lambda: budget.category.name)()
        period_display = await sync_to_async(lambda: budget.get_period_type_display())()
        
        message = (
            f"🗑️ **Удаление бюджета**\n\n"
            f"Вы уверены, что хотите удалить бюджет для категории "
            f"'{category_icon} {category_name}'?\n\n"
            f"💰 Сумма: {budget.amount:,.2f} ₽\n"
            f"📅 Период: {period_display}\n\n"
            "⚠️ Это действие нельзя отменить."
        )
        
        keyboard = ActionKeyboard.get_confirmation_keyboard(f"budget_delete_{budget_id}")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_budget_delete_execution(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Выполняет удаление бюджета"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get)(
                id=budget_id,
                user=user,
                is_active=True,
            )
        except Budget.DoesNotExist:
            await self._send_error_message(
                update,
                context,
                "❌ Бюджет не найден."
            )
            return
        
        # Получаем данные категории до удаления
        category_icon = await sync_to_async(lambda: budget.category.icon)()
        category_name = await sync_to_async(lambda: budget.category.name)()
        
        # Удаляем бюджет
        await sync_to_async(budget.delete)()
        
        message = (
            f"✅ **Бюджет удален**\n\n"
            f"Бюджет для категории '{category_icon} {category_name}' "
            f"был успешно удален."
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="📊 К списку бюджетов",
                    callback_data="budgets_view"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Главное меню",
                    callback_data="main_menu"
                ),
            ],
        ])
        
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
        """Отправляет или редактирует сообщение"""
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
    
    async def _send_error_message(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        message: str,
    ) -> None:
        """Отправляет сообщение об ошибке"""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="show_budgets"
                ),
            ],
        ])
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        ) 