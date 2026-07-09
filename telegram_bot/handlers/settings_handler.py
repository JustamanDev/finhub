import logging
from telegram import Update, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.settings import SettingsKeyboard
from telegram_bot.services.category_management_service import CategoryManagementService

logger = logging.getLogger(__name__)


class SettingsHandler(BaseHandler):
    """Обработчик настроек"""
    
    async def handle_main_settings(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает главное меню настроек"""
        keyboard = SettingsKeyboard.get_main_settings_keyboard()
        
        message = (
            "⚙️ **Настройки FinHub**\n\n"
            "Выберите раздел для настройки:\n"
            "• 📂 Категории - управление категориями\n"
            "• 🎯 Лимиты - настройка месячных лимитов\n"
            "• ⚙️ Общие настройки - основные параметры"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_categories_settings(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает меню управления категориями"""
        keyboard = SettingsKeyboard.get_categories_keyboard()
        
        message = (
            "📂 **Управление категориями**\n\n"
            "Выберите действие:\n"
            "• ➕ Добавить категорию - создать новую\n"
            "• 📝 Редактировать - изменить существующие\n"
            "• 🗑️ Удалить - удалить категории"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_list(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        action: str = "view",
    ) -> None:
        """Показывает список категорий"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        categories = await category_service.get_user_categories()
        
        if not categories:
            message = "📂 **Категории**\n\n❌ У вас пока нет категорий.\n\nНажмите '➕ Добавить категорию' для создания первой категории."
            keyboard = SettingsKeyboard.get_categories_keyboard()
        else:
            message = f"📂 **Категории** ({len(categories)})\n\nВыберите категорию для {action}:"
            keyboard = SettingsKeyboard.get_category_list_keyboard(
                categories,
                action,
            )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_actions(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает действия с категорией"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        # Получаем информацию о категории
        category_stats = await category_service.get_category_stats(category_id)
        
        if not category_stats:
            await self._send_error_message(update, context, "Категория не найдена")
            return
        
        category = category_stats['category']
        keyboard = SettingsKeyboard.get_category_actions_keyboard(category_id)
        
        message = (
            f"📂 **Категория: {category.icon} {category.name}**\n\n"
            f"**Тип:** {'💰 Доход' if category.type == 'income' else '💸 Расход'}\n"
            f"**Транзакций:** {category_stats['transaction_count']}\n"
            f"**Общая сумма:** {category_stats['total_amount']:,.0f}₽\n\n"
            "Выберите действие:"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_icon_selection(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает выбор иконки"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        icons = await category_service.get_available_icons()
        keyboard = SettingsKeyboard.get_icon_selection_keyboard(
            category_id,
            icons,
        )
        
        message = (
            f"🎨 **Выбор иконки**\n\n"
            "Выберите новую иконку для категории:"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_type_selection(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает выбор типа категории"""
        keyboard = SettingsKeyboard.get_category_type_keyboard(category_id)
        
        message = (
            f"🔄 **Изменение типа категории**\n\n"
            "Выберите новый тип категории:"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_confirmation(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        action: str,
        category_id: int,
    ) -> None:
        """Показывает подтверждение действия"""
        keyboard = SettingsKeyboard.get_confirmation_keyboard(
            action,
            category_id,
        )
        
        action_names = {
            'delete': 'удаления',
            'rename': 'переименования',
            'icon': 'смены иконки',
            'type': 'изменения типа',
        }
        
        action_name = action_names.get(action, action)
        
        message = (
            f"⚠️ **Подтверждение {action_name}**\n\n"
            f"Вы уверены, что хотите {action_name} эту категорию?\n\n"
            "Это действие нельзя отменить."
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_add(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает выбор типа категории для добавления"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Начинаем создание категории для пользователя {telegram_user.id}")
        
        message = (
            "➕ **Создание новой категории**\n\n"
            "Выберите тип категории:\n"
            "• 💰 Доходы - для источников дохода\n"
            "• 💸 Расходы - для трат и покупок"
        )
        
        keyboard = SettingsKeyboard.get_category_type_selection_keyboard("add")
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
        
        logger.info("Показан выбор типа категории")
    
    async def handle_category_add_type_selection(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_type: str,
    ) -> None:
        """Показывает форму создания категории выбранного типа"""
        import logging
        logger = logging.getLogger(__name__)
        
        type_name = "доходов" if category_type == "income" else "расходов"
        type_icon = "💰" if category_type == "income" else "💸"
        
        logger.info(f"Выбран тип категории: {category_type}")
        
        message = (
            f"{type_icon} **Создание категории {type_name}**\n\n"
            "Отправьте название новой категории **в любой форме** "
            "(можно с эмодзи):\n\n"
            "**Примеры:**\n"
            "• `🥕 Продукты`\n"
            "• `Продукты 🥕`\n"
            "• `Продукты`"
        )
        
        # Устанавливаем состояние ожидания создания категории
        user_state = await self.get_user_state(telegram_user)
        user_state.awaiting_category_creation = True
        user_state.context_data = {"category_type": category_type}
        await user_state.asave()
        
        logger.info(f"Состояние установлено: awaiting_category_creation=True, type={category_type}")
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="category_add"
                ),
            ],
        ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
        
        logger.info("Форма создания категории отображена")
    
    async def handle_category_list_by_type(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_type: str,
    ) -> None:
        """Показывает список категорий определенного типа"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        categories = await category_service.get_user_categories()
        type_name = "доходов" if category_type == "income" else "расходов"
        type_icon = "💰" if category_type == "income" else "💸"
        
        filtered_categories = [c for c in categories if c.type == category_type]
        
        if not filtered_categories:
            message = f"{type_icon} **Категории {type_name}**\n\n❌ У вас пока нет категорий {type_name}.\n\nНажмите '➕ Добавить категорию' для создания первой категории."
            keyboard = SettingsKeyboard.get_categories_keyboard()
        else:
            message = f"{type_icon} **Категории {type_name}** ({len(filtered_categories)})\n\nВыберите категорию для редактирования:"
            keyboard = SettingsKeyboard.get_category_list_by_type_keyboard(
                filtered_categories,  # Передаем только отфильтрованные категории
                category_type,
                "edit"
            )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_edit_selection(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает меню редактирования категории"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        # Получаем информацию о категории
        category_stats = await category_service.get_category_stats(category_id)
        
        if not category_stats:
            await self._send_error_message(update, context, "Категория не найдена")
            return
        
        category = category_stats['category']
        
        # Проверяем наличие бюджета для категории расходов
        has_budget = False
        if category.type == 'expense':
            from budgets.models import Budget
            from django.utils import timezone
            
            today = timezone.now().date()
            has_budget = await sync_to_async(Budget.objects.filter(
                user=user,
                category=category,
                start_date__lte=today,
                end_date__gte=today,
                is_active=True,
            ).exists)()
        
        keyboard = SettingsKeyboard.get_category_actions_keyboard(category_id, has_budget)
        
        message = (
            f"📝 **Редактирование категории**\n\n"
            f"**{category.icon} {category.name}**\n"
            f"Тип: {'доход' if category.type == 'income' else 'расход'}\n"
            f"Иконка: {category.icon}\n\n"
            f"Выберите что хотите изменить:"
        )
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
            )
    
    async def handle_category_icon_change(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
        icon: str,
    ) -> None:
        """Сохраняет новую иконку для категории"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        
        # Используем метод update_category вместо прямого изменения
        category = await category_service.update_category(
            category_id=category_id,
            icon=icon,
        )

        if not category:
            await self._send_error_message(update, context, "Категория не найдена")
            return

        message = (
            "✅ **Иконка обновлена!**\n\n"
            f"Теперь: {category.icon} {category.name}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔙 Назад к категории",
                    callback_data=f"category_edit_{category_id}",
                ),
            ],
        ]

        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_general_settings(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает общие настройки"""
        message = (
            "⚙️ **Общие настройки**\n\n"
            "Здесь вы можете настроить основные параметры:\n"
            "• 🔔 Уведомления - настройка уведомлений\n"
            "• 📊 Отчеты - настройка отчетов\n"
            "• 🎯 Цели - управление финансовыми целями\n"
            "• 🔐 Безопасность - настройки безопасности\n\n"
            "Функционал находится в разработке."
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings"
                ),
            ],
        ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limits_settings(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает настройки лимитов"""
        message = (
            "🎯 **Управление лимитами**\n\n"
            "Здесь вы можете настроить месячные лимиты для категорий:\n"
            "• 📊 Просмотр текущих лимитов\n"
            "• ➕ Добавить новый лимит\n"
            "• ✏️ Редактировать существующие лимиты\n"
            "• 🗑️ Удалить лимиты\n\n"
            "Лимиты помогают контролировать расходы и получать уведомления при превышении."
        )
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="📊 Просмотр лимитов",
                    callback_data="limits_view"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Добавить лимит",
                    callback_data="limits_add"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings"
                ),
            ],
        ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limits_view(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает список лимитов"""
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
                "📊 **Текущие лимиты**\n\n"
                "У вас пока нет установленных лимитов.\n\n"
                "Лимиты помогают контролировать расходы по категориям. "
                "При превышении лимита вы получите уведомление."
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="➕ Добавить лимит",
                        callback_data="limits_add"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings_limits"
                    ),
                ],
            ]
        else:
            # Формируем список бюджетов
            budgets_text = "📊 **Ваши лимиты:**\n\n"
            for budget in budgets:
                # Оборачиваем свойства в sync_to_async
                spent_percent = await sync_to_async(lambda b: b.spent_percentage)(budget)
                spent_amount = await sync_to_async(lambda b: b.spent_amount)(budget)
                
                status_icon = "🟢" if spent_percent < 80 else "🟡" if spent_percent < 100 else "🔴"
                
                budgets_text += (
                    f"• {budget.category.icon} {budget.category.name}\n"
                    f"  {budget.amount:,.2f} ₽ ({spent_percent:.1f}%)\n"
                    f"  {status_icon} {spent_amount:,.2f} / {budget.amount:,.2f} ₽\n\n"
                )
            
            message = (
                f"{budgets_text}\n"
                f"Всего лимитов: {len(budgets)}"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="➕ Добавить лимит",
                        callback_data="limits_add"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🗑️ Удалить лимит",
                        callback_data="limits_delete"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings_limits"
                    ),
                ],
            ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limits_add(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает форму добавления лимита"""
        message = (
            "➕ **Добавление лимита**\n\n"
            "Выберите категорию для установки лимита:\n\n"
            "Лимит будет применяться к расходам в выбранной категории."
        )
        
        # Получаем категории пользователя
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        categories = await category_service.get_user_categories()
        
        # Фильтруем только категории расходов
        expense_categories = [c for c in categories if c.type == 'expense']
        
        if not expense_categories:
            message = (
                "❌ **Нет доступных категорий**\n\n"
                "Для установки лимита нужны категории расходов. "
                "Сначала создайте категории в разделе 'Категории'."
            )
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings_limits"
                    ),
                ],
            ]
        else:
            keyboard = []
            for category in expense_categories:
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"limit_add_{category.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings_limits"
                ),
            ])
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limit_add_for_category(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает форму добавления лимита для конкретной категории"""
        # Извлекаем ID категории из callback_data
        if isinstance(update, CallbackQuery):
            callback_data = update.data
        else:
            return
        
        # Парсим limit_add_<category_id>
        if not callback_data.startswith("limit_add_"):
            return
        
        try:
            category_id = int(callback_data.replace("limit_add_", ""))
        except ValueError:
            return
        
        # Получаем категорию
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        category = await category_service.get_category_by_id(category_id)
        
        if not category:
            message = "❌ Категория не найдена"
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="limits_add"
                    ),
                ],
            ]
        else:
            # Сохраняем состояние для ввода суммы лимита
            context.user_data['limit_creation'] = {
                'category_id': category_id,
                'step': 'amount_input'
            }
            
            message = (
                f"➕ **Добавление лимита**\n\n"
                f"Категория: {category.icon} {category.name}\n\n"
                f"Введите сумму лимита в рублях (например: 5000):"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Отмена",
                        callback_data="limits_add"
                    ),
                ],
            ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limits_delete(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает список лимитов для удаления"""
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
                "🗑️ **Удаление лимитов**\n\n"
                "У вас нет активных лимитов для удаления."
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="settings_limits"
                    ),
                ],
            ]
        else:
            # Формируем список бюджетов для удаления
            message = "🗑️ **Выберите лимит для удаления:**\n\n"
            
            keyboard = []
            for budget in budgets:
                # Оборачиваем свойства в sync_to_async
                spent_percent = await sync_to_async(lambda b: b.spent_percentage)(budget)
                spent_amount = await sync_to_async(lambda b: b.spent_amount)(budget)
                
                status_icon = "🟢" if spent_percent < 80 else "🟡" if spent_percent < 100 else "🔴"
                
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"{budget.category.icon} {budget.category.name} - {budget.amount:,.0f} ₽ ({spent_percent:.0f}%)",
                        callback_data=f"limit_delete_{budget.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings_limits"
                ),
            ])
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limit_delete_confirmation(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает подтверждение удаления лимита"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get)(
                id=budget_id,
                user=user,
                is_active=True,
            )
            
            spent_percent = await sync_to_async(lambda b: b.spent_percentage)(budget)
            spent_amount = await sync_to_async(lambda b: b.spent_amount)(budget)
            
            message = (
                f"🗑️ **Подтверждение удаления**\n\n"
                f"Лимит: {budget.category.icon} {budget.category.name}\n"
                f"Сумма: {budget.amount:,.2f} ₽\n"
                f"Потрачено: {spent_amount:,.2f} ₽ ({spent_percent:.1f}%)\n"
                f"Период: {budget.start_date.strftime('%d.%m.%Y')} - {budget.end_date.strftime('%d.%m.%Y')}\n\n"
                f"Вы уверены, что хотите удалить этот лимит?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="✅ Да, удалить",
                        callback_data=f"limit_delete_confirm_{budget_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="limits_delete"
                    ),
                ],
            ]
            
        except Budget.DoesNotExist:
            message = "❌ Лимит не найден"
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
                        callback_data="limits_delete"
                    ),
                ],
            ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_limit_delete_execution(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Выполняет удаление лимита"""
        from asgiref.sync import sync_to_async
        from budgets.models import Budget
        
        user = await sync_to_async(lambda: telegram_user.user)()
        
        try:
            budget = await sync_to_async(Budget.objects.get)(
                id=budget_id,
                user=user,
                is_active=True,
            )
            
            # Сохраняем информацию для сообщения
            category_name = budget.category.name
            amount = budget.amount
            
            # Удаляем бюджет
            await sync_to_async(budget.delete)()
            
            message = (
                f"✅ **Лимит удален!**\n\n"
                f"Лимит для категории '{category_name}' "
                f"на сумму {amount:,.2f} ₽ был успешно удален."
            )
            
        except Budget.DoesNotExist:
            message = "❌ Лимит не найден"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔙 К лимитам",
                    callback_data="settings_limits"
                ),
            ],
        ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_type(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает меню выбора типа категории"""
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            category_service = CategoryManagementService(user)
            category = await category_service.get_category_by_id(category_id)
            
            if not category:
                await self._send_error_message(
                    update,
                    context,
                    "Категория не найдена"
                )
                return
        except Exception as e:
            await self._send_error_message(
                update,
                context,
                f"Ошибка при получении категории: {str(e)}"
            )
            return
        
        message = (
            f"📝 **Изменение типа категории**\n\n"
            f"Категория: {category.icon} {category.name}\n"
            f"Текущий тип: {'💰 Доход' if category.type == 'income' else '💸 Расход'}\n\n"
            f"Выберите новый тип:"
        )
        
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
                    callback_data=f"category_edit_{category_id}"
                ),
            ],
        ]
        
        await self._send_or_edit_message(
            update,
            context,
            message,
            keyboard,
        )
    
    async def handle_category_type_change(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
        new_type: str,
    ) -> None:
        """Изменяет тип категории"""
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            category_service = CategoryManagementService(user)
            category = await category_service.get_category_by_id(category_id)
            
            if not category:
                await self._send_error_message(
                    update,
                    context,
                    "Категория не найдена"
                )
                return
            
            # Изменяем тип
            category.type = new_type
            await category_service.save_category(category)
            
            type_name = "доход" if new_type == "income" else "расход"
            message = (
                f"✅ **Тип категории изменен!**\n\n"
                f"Категория: {category.icon} {category.name}\n"
                f"Новый тип: {type_name.capitalize()}"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад к категории",
                        callback_data=f"category_edit_{category_id}"
                    ),
                ],
            ]
            
            await self._send_or_edit_message(
                update,
                context,
                message,
                keyboard,
            )
            
        except Exception as e:
            await self._send_error_message(
                update,
                context,
                f"Ошибка при изменении типа: {str(e)}"
            )
    
    async def handle_category_action_execution(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        action: str,
        category_id: int,
    ) -> None:
        """Выполняет действие с категорией"""
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            category_service = CategoryManagementService(user)
            
            if action == "delete":
                # Удаляем категорию
                success = await category_service.delete_category(category_id)
                
                if success:
                    message = (
                        "✅ **Категория удалена!**\n\n"
                        "Категория была успешно удалена из вашего списка."
                    )
                else:
                    message = (
                        "❌ **Не удалось удалить категорию**\n\n"
                        "Возможно, у категории есть связанные транзакции. "
                        "Сначала удалите все транзакции в этой категории."
                    )
                
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад к категориям",
                            callback_data="settings_categories"
                        ),
                    ],
                ]
                
                await self._send_or_edit_message(
                    update,
                    context,
                    message,
                    keyboard,
                )
            else:
                await self._send_error_message(
                    update,
                    context,
                    f"Действие '{action}' не поддерживается"
                )
                
        except Exception as e:
            await self._send_error_message(
                update,
                context,
                f"Ошибка при выполнении действия: {str(e)}"
            )

    async def handle_category_rename_prompt(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает форму переименования категории и ставит флаг"""
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)
        category = await category_service.get_category_by_id(category_id)

        if not category:
            await self._send_error_message(update, context, "Категория не найдена")
            return

        # Сохраняем ID категории в user_data для TextHandler
        context.user_data["renaming_category_id"] = category_id

        message = (
            "✏️ **Переименование категории**\n\n"
            f"Текущая категория: {category.icon} {category.name}\n\n"
            "Отправьте новое название категории **в любой форме** "
            "(можно с эмодзи):\n\n"
            "Примеры:\n"
            "• `🥕 Продукты`\n"
            "• `Продукты 🥕`\n"
            "• `Продукты`"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"category_actions_{category_id}",
                ),
            ],
        ]

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
        # Обрабатываем клавиатуру
        reply_markup = None
        if keyboard:
            if hasattr(keyboard, 'inline_keyboard'):
                # Это уже InlineKeyboardMarkup
                reply_markup = keyboard
            else:
                # Это список кнопок, создаем InlineKeyboardMarkup
                from telegram import InlineKeyboardMarkup
                reply_markup = InlineKeyboardMarkup(keyboard)
        
        from telegram_bot.utils.telegram_resilience import send_or_edit_message

        await send_or_edit_message(
            update,
            context,
            text=message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
        )
    
    async def _send_error_message(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        message: str,
    ) -> None:
        """Отправляет сообщение об ошибке"""
        if hasattr(update, 'answer'):
            await update.answer(message, show_alert=True)
        else:
            await self._send_or_edit_message(
                update,
                context,
                f"❌ {message}",
                None,
            ) 