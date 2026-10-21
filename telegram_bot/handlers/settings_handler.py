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
            "• 📦 Архив - спрятать категорию из меню, операции останутся в отчётах"
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
        context.user_data.pop('renaming_category_id', None)
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
        
        user = await sync_to_async(lambda: telegram_user.user)()
        category = await CategoryManagementService(user).get_category_by_id(category_id)
        if category is None:
            await self._send_error_message(update, context, "Категория не найдена")
            return

        if action == 'delete':
            message = (
                f"📦 **Убрать {category.icon} {category.name} в архив?**\n\n"
                "Категория пропадёт из меню и быстрого ввода. "
                "Новую операцию в неё записать не получится.\n\n"
                "Уже записанные операции останутся. В отчётах за месяцы, "
                "где они были, категория будет видна со своими суммами.\n\n"
                "Текущий лимит по ней тоже спрячется. "
                "Вернуть категорию можно из архива."
            )
        elif action == 'restore':
            message = (
                f"📦 **Вернуть {category.icon} {category.name} в меню?**\n\n"
                "Снова можно будет записывать в неё операции. "
                "Текущий лимит тоже вернётся. "
                "Прошлые суммы в отчётах и так на месте."
            )
        else:
            action_names = {
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
        user_state = await self.get_user_state(telegram_user)
        if user_state.awaiting_category_creation:
            user_state.awaiting_category_creation = False
            user_state.awaiting_category = False
            user_state.current_amount = None
            data = dict(user_state.context_data or {})
            for key in (
                'category_type',
                'voice_create_after',
                'voice_intent',
                'suggested_name',
            ):
                data.pop(key, None)
            user_state.context_data = data
            await user_state.asave(
                update_fields=[
                    'awaiting_category_creation',
                    'awaiting_category',
                    'current_amount',
                    'context_data',
                    'updated_at',
                ],
            )

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
        """Базовая валюта отчётов и набор валют для ввода суммы."""
        from transactions.currencies import button_label, prefs_tuple

        base, inputs = await sync_to_async(prefs_tuple)(telegram_user)
        names = ', '.join(button_label(code) for code in inputs)
        message = (
            "⚙️ **Общие настройки**\n\n"
            f"Базовая валюта: **{button_label(base)}**. "
            "В ней отчёты, лимиты и цели.\n"
            f"После суммы бот предлагает: {names}.\n"
            "Если валюта названа в тексте и она в этом списке, вопрос не задаётся.\n"
            "Курс берётся у ЦБ раз в сутки по Москве и фиксируется на операции."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    text="Базовая валюта",
                    callback_data="settings_base",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Валюты ввода",
                    callback_data="settings_inputs",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings",
                ),
            ],
        ]
        await self._send_or_edit_message(update, context, message, keyboard)

    async def handle_currency_toggle(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        await self.handle_general_settings(update, context, telegram_user)

    async def handle_base_currency_menu(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from transactions.currencies import CATALOG, button_label, prefs_tuple

        base, _inputs = await sync_to_async(prefs_tuple)(telegram_user)
        rows = []
        pair = []
        for spec in CATALOG:
            mark = '✓ ' if spec.code == base else ''
            pair.append(
                InlineKeyboardButton(
                    text=f'{mark}{button_label(spec.code)}',
                    callback_data=f'settings_base_{spec.code}',
                )
            )
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        rows.append([
            InlineKeyboardButton(text='🔙 Назад', callback_data='settings_general'),
        ])
        await self._send_or_edit_message(
            update,
            context,
            "Базовая валюта — в ней отчёты, лимиты и цели.",
            rows,
        )

    async def handle_base_currency_pick(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        code: str,
    ) -> None:
        from transactions.currencies import button_label, is_known, prefs_tuple

        if not is_known(code):
            await self.handle_base_currency_menu(update, context, telegram_user)
            return
        base, _inputs = await sync_to_async(prefs_tuple)(telegram_user)
        if code == base:
            await self.handle_general_settings(update, context, telegram_user)
            return
        message = (
            f"Сменить базовую валюту на **{button_label(code)}**?\n\n"
            "Уже записанные операции, лимиты и цели пересчитаются "
            "по сегодняшнему курсу ЦБ. Новые отчёты будут в этой валюте."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    text='Да, пересчитать',
                    callback_data=f'settings_base_yes_{code}',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Отмена',
                    callback_data='settings_base',
                ),
            ],
        ]
        await self._send_or_edit_message(update, context, message, keyboard)

    async def handle_base_currency_confirm(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        code: str,
    ) -> None:
        from transactions.currencies import button_label, is_known
        from transactions.exchange import ExchangeRateUnavailable, change_base_currency

        if not is_known(code):
            await self.handle_base_currency_menu(update, context, telegram_user)
            return
        try:
            await sync_to_async(change_base_currency, thread_sensitive=True)(
                telegram_user,
                code,
            )
        except ExchangeRateUnavailable as exc:
            await self._send_or_edit_message(
                update,
                context,
                f'Не сменил базовую валюту.\n{exc}',
                [[InlineKeyboardButton(text='🔙 Назад', callback_data='settings_general')]],
            )
            return
        await self._send_or_edit_message(
            update,
            context,
            f'Базовая валюта теперь **{button_label(code)}**. '
            'Уже записанные суммы пересчитаны.',
            [[InlineKeyboardButton(text='К настройкам', callback_data='settings_general')]],
        )

    async def handle_input_currencies(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from transactions.currencies import CATALOG, button_label, prefs_tuple

        _base, inputs = await sync_to_async(prefs_tuple)(telegram_user)
        rows = []
        pair = []
        for spec in CATALOG:
            mark = '✓ ' if spec.code in inputs else ''
            pair.append(
                InlineKeyboardButton(
                    text=f'{mark}{button_label(spec.code)}',
                    callback_data=f'settings_input_{spec.code}',
                )
            )
            if len(pair) == 2:
                rows.append(pair)
                pair = []
        if pair:
            rows.append(pair)
        rows.append([
            InlineKeyboardButton(text='🔙 Назад', callback_data='settings_general'),
        ])
        await self._send_or_edit_message(
            update,
            context,
            'Отметьте валюты, которые бот предлагает после суммы. '
            'Хотя бы одна должна остаться.',
            rows,
        )

    async def handle_input_currency_toggle(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        code: str,
    ) -> None:
        from transactions.currencies import input_codes_of, is_known, ordered_codes

        if not is_known(code):
            await self.handle_input_currencies(update, context, telegram_user)
            return

        def _toggle():
            current = input_codes_of(telegram_user)
            if code in current:
                if len(current) == 1:
                    return False
                current = [item for item in current if item != code]
            else:
                current = ordered_codes([*current, code])
            telegram_user.input_currencies = current
            telegram_user.save(update_fields=['input_currencies', 'updated_at'])
            return True

        changed = await sync_to_async(_toggle, thread_sensitive=True)()
        query = update if isinstance(update, CallbackQuery) else getattr(update, 'callback_query', None)
        if not changed and query is not None:
            await query.answer('Нужна хотя бы одна валюта')
        await self.handle_input_currencies(update, context, telegram_user)
    
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
                category__is_active=True,
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
        context.user_data.pop('limit_creation', None)
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
                category__is_active=True,
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
                archived = await category_service.archive_category(category_id)
                if archived:
                    message = (
                        f"✅ **{archived.icon} {archived.name} в архиве**\n\n"
                        "В меню и быстром вводе её больше нет. "
                        "Операции на месте: отчёты за прошлые месяцы покажут те же суммы."
                    )
                else:
                    message = "❌ **Не удалось убрать категорию в архив.**"
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="📦 Архив",
                            callback_data="category_archive"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад к категориям",
                            callback_data="settings_categories"
                        ),
                    ],
                ]
            elif action == "restore":
                restored = await category_service.restore_category(category_id)
                if restored:
                    message = (
                        f"✅ **{restored.icon} {restored.name} снова в меню**\n\n"
                        "Можно записывать новые операции. Прошлые суммы не менялись."
                    )
                else:
                    message = "❌ **Не удалось вернуть категорию.**"
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад к категориям",
                            callback_data="settings_categories"
                        ),
                    ],
                ]

            if action in ("delete", "restore"):
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

    async def handle_category_archive(
        self,
        update: Update | CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Список категорий, скрытых из меню."""
        user = await sync_to_async(lambda: telegram_user.user)()
        archived = await CategoryManagementService(user).get_archived_categories()
        if not archived:
            message = (
                "📦 **Архив пуст**\n\n"
                "Сюда попадают категории, которые больше не нужны в меню. "
                "Их операции остаются в отчётах."
            )
            keyboard = SettingsKeyboard.get_categories_keyboard()
        else:
            message = (
                "📦 **Архив**\n\n"
                "Эти категории скрыты из меню и быстрого ввода. "
                "Операции по ним на месте. Нажмите, чтобы вернуть."
            )
            buttons = [
                [
                    InlineKeyboardButton(
                        text=f"{category.icon} {category.name}",
                        callback_data=f"category_restore_{category.id}",
                    ),
                ]
                for category in archived
            ]
            buttons.append([
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="settings_categories",
                ),
            ])
            keyboard = buttons
        await self._send_or_edit_message(update, context, message, keyboard)

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