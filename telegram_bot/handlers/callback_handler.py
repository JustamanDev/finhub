import logging
from decimal import Decimal
from datetime import (
    date,
    datetime,
)
from telegram import (
    Update,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.categories import CategoryKeyboard
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.command_executor import CommandExecutor
from telegram_bot.utils.telegram_resilience import safe_edit_message_text
from telegram_bot.services.transaction_service import (
    TransactionService,
    SmartSuggestionsService,
)
from categories.models import Category
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class CallbackHandler(BaseHandler):
    """Обработчик callback запросов от inline клавиатур"""

    def __init__(self) -> None:
        super().__init__()
        self._command_executor = CommandExecutor()
    
    async def handle_callback_query(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Обрабатывает callback запросы"""
        try:
            query = update.callback_query
            logger.info(f"Получен callback: {query.data}")
            
            # Получаем пользователя
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user
            )
            
            # Обрабатываем callback по типу
            if query.data == 'voice_confirm_yes':
                await self._handle_voice_confirm(
                    update,
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'voice_cancel':
                await self._handle_voice_cancel(query, context)
            elif query.data.startswith('voice_dialog_type_'):
                await self._handle_voice_dialog_type(
                    update,
                    query,
                    context,
                    telegram_user,
                )
            elif query.data.startswith('voice_cat_pick_'):
                await self._handle_voice_cat_pick(
                    update,
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'voice_cat_all':
                await self._handle_voice_cat_all(
                    update,
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'voice_cat_create':
                await self._handle_voice_cat_create(
                    update,
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'add_expense':
                await self._handle_add_expense(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'add_income':
                await self._handle_add_income(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'show_stats':
                await self._handle_show_stats(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'show_budgets':
                await self._handle_show_budgets(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'budgets_view':
                await self._handle_budgets_view(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'budgets_add':
                await self._handle_budgets_add(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'goals_menu':
                await self._handle_goals_menu(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'goals_list':
                await self._handle_goals_list(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == 'goal_create':
                await self._handle_goal_create_prompt(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data.startswith('goal_view_'):
                goal_id = int(query.data.split('_')[2])
                await self._handle_goal_view(
                    query,
                    context,
                    telegram_user,
                    goal_id,
                )
            elif query.data.startswith('goal_history_'):
                goal_id = int(query.data.split('_')[2])
                await self._handle_goal_history(
                    query,
                    context,
                    telegram_user,
                    goal_id,
                )
            elif query.data.startswith('goal_deposit_'):
                goal_id = int(query.data.split('_')[2])
                await self._handle_goal_deposit_prompt(
                    query,
                    context,
                    telegram_user,
                    goal_id,
                )
            elif query.data.startswith('goal_withdraw_'):
                goal_id = int(query.data.split('_')[2])
                await self._handle_goal_withdraw_prompt(
                    query,
                    context,
                    telegram_user,
                    goal_id,
                )
            elif query.data.startswith('goal_quick_deposit_'):
                parts = query.data.split('_')
                goal_id = int(parts[3])
                amount = int(parts[4])
                await self._handle_goal_quick_deposit(
                    query,
                    context,
                    telegram_user,
                    goal_id,
                    amount,
                )
            elif query.data in ('switch_to_income', 'switch_to_expense'):
                # Переключение типа транзакции (расход/доход)
                await self._handle_type_switch(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data.startswith('budget_detail_'):
                budget_id = int(query.data.split('_')[2])
                await self._handle_budget_detail(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            elif query.data.startswith('budget_add_for_category_'):
                category_id = int(query.data.split('_')[4])
                await self._handle_budget_add_for_category(
                    query,
                    context,
                    telegram_user,
                    category_id,
                )
            elif query.data.startswith('budget_edit_'):
                budget_id = int(query.data.split('_')[2])
                await self._handle_budget_edit(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            elif query.data.startswith('budget_delete_'):
                budget_id = int(query.data.split('_')[2])
                await self._handle_budget_delete_confirmation(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            elif query.data.startswith('confirm_budget_delete_'):
                budget_id = int(query.data.split('_')[3])
                await self._handle_budget_delete_execution(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            elif query.data.startswith('category_budget_'):
                category_id = int(query.data.split('_')[2])
                await self._handle_category_budget(
                    query,
                    context,
                    telegram_user,
                    category_id,
                )
            elif query.data == 'settings':
                logger.info("Вызываем _handle_settings")
                await self._handle_settings(query, context, telegram_user)
            elif (
                query.data.startswith('edit_amount_')
                or query.data.startswith('edit_date_')
                or query.data.startswith('edit_comment_')
            ):
                # Редактирование транзакции (дата/комментарий)
                await self._handle_transaction_edit(
                    query,
                    context,
                    telegram_user,
                )
            elif query.data == "settings_categories":
                logger.info("Вызываем _handle_settings_categories")
                await self._handle_settings_categories(query, context, telegram_user)
            elif query.data == "settings_limits":
                logger.info("Вызываем _handle_settings_limits")
                await self._handle_settings_limits(query, context, telegram_user)
            elif query.data == "limits_view":
                logger.info("Вызываем _handle_limits_view")
                await self._handle_limits_view(query, context, telegram_user)
            elif query.data == "limits_add":
                logger.info("Вызываем _handle_limits_add")
                await self._handle_limits_add(query, context, telegram_user)
            elif query.data == "limits_delete":
                logger.info("Вызываем _handle_limits_delete")
                await self._handle_limits_delete(query, context, telegram_user)
            elif query.data.startswith("limit_delete_"):
                logger.info(f"Вызываем _handle_limit_delete для {query.data}")
                await self._handle_limit_delete(query, context, telegram_user)
            elif query.data.startswith("limit_add_"):
                logger.info(f"Вызываем _handle_limit_add для {query.data}")
                await self._handle_limit_add(query, context, telegram_user)
            elif query.data == "settings_general":
                logger.info("Вызываем _handle_settings_general")
                await self._handle_settings_general(query, context, telegram_user)
            elif query.data == "category_add":
                logger.info("Вызываем _handle_category_add")
                await self._handle_category_add(query, context, telegram_user)
            elif query.data.startswith("category_add_type_"):
                await self._handle_category_add_type_selection(query, context, telegram_user)
            elif query.data.startswith("category_list_"):
                await self._handle_category_list_by_type(query, context, telegram_user)
            elif query.data == "category_edit":
                logger.info("Вызываем _handle_category_edit")
                await self._handle_category_edit(query, context, telegram_user)
            elif query.data == "category_delete":
                logger.info("Вызываем _handle_category_delete")
                await self._handle_category_delete(query, context, telegram_user)
            elif query.data.startswith("category_edit_"):
                await self._handle_category_edit_selection(query, context, telegram_user)
            elif query.data.startswith("category_actions_"):
                logger.info("Вызываем _handle_category_actions")
                await self._handle_category_actions(query, context, telegram_user)
            elif query.data.startswith("category_rename_"):
                logger.info("Вызываем _handle_category_rename")
                await self._handle_category_rename(query, context, telegram_user)
            elif query.data.startswith("category_icon_"):
                logger.info("Вызываем _handle_category_icon")
                await self._handle_category_icon(query, context, telegram_user)
            elif query.data.startswith("category_icon_select_"):
                logger.info("Вызываем _handle_category_icon_select")
                await self._handle_category_icon_select(query, context, telegram_user)
            elif query.data.startswith("category_type_select_"):
                logger.info("Вызываем _handle_category_type_select")
                await self._handle_category_type_select(query, context, telegram_user)
            elif query.data.startswith("category_type_"):
                logger.info("Вызываем _handle_category_type")
                await self._handle_category_type(query, context, telegram_user)
            elif query.data.startswith("category_confirm_"):
                logger.info("Вызываем _handle_category_confirm")
                await self._handle_category_confirm(query, context, telegram_user)
            elif query.data.startswith("category_delete_"):
                logger.info("Вызываем _handle_category_delete")
                await self._handle_category_delete(query, context, telegram_user)
            elif query.data.startswith("category_income_"):
                await self._handle_category_edit_selection(query, context, telegram_user)
            elif query.data.startswith("category_expense_"):
                await self._handle_category_edit_selection(query, context, telegram_user)
            elif query.data.startswith("category_"):
                logger.info("Вызываем _handle_category_selection")
                await self._handle_category_selection(query, context, telegram_user)
            elif query.data.startswith("transaction_actions_"):
                try:
                    transaction_id = int(query.data.replace("transaction_actions_", ""))
                    user = await sync_to_async(lambda: telegram_user.user)()
                    transaction = await sync_to_async(lambda: Transaction.objects.get(
                        id=transaction_id,
                        user=user
                    ), thread_sensitive=True)()
                    await self._send_transaction_confirmation(query, context, transaction)
                except Exception:
                    await query.answer("Транзакция не найдена")
            elif query.data == "main_menu":
                logger.info("Вызываем _handle_main_menu")
                await self._handle_main_menu(query, context, telegram_user)
            elif query.data == "show_report":
                logger.info("Вызываем _handle_show_report")
                await self._handle_show_report(query, context, telegram_user)
            elif query.data == "report_current":
                logger.info("Вызываем _handle_report_current")
                await self._handle_report_current(query, context, telegram_user)
            elif query.data == "report_all":
                logger.info("Вызываем _handle_report_all")
                await self._handle_report_all(query, context, telegram_user)
            elif query.data == "report_export_excel_current":
                logger.info("Вызываем _handle_report_export_excel_current")
                await self._handle_report_export_excel_current(query, context, telegram_user)
            elif query.data.startswith("report_export_excel_"):
                logger.info("Вызываем _handle_report_export_excel_period")
                await self._handle_report_export_excel_period(query, context, telegram_user)
            elif query.data.startswith("report_prev_"):
                logger.info("Вызываем _handle_report_navigation")
                await self._handle_report_navigation(query, context, telegram_user)
            elif query.data.startswith("report_next_"):
                logger.info("Вызываем _handle_report_navigation")
                await self._handle_report_navigation(query, context, telegram_user)
            elif query.data == "report_disabled":
                await query.answer("Нет доступных отчетов для навигации")
            else:
                logger.info("Вызываем _handle_unknown_callback")
                await self._handle_unknown_callback(query, context)
                
        except Exception as e:
            await self.handle_error(update, context, e)
    
    async def _handle_category_selection(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор категории"""
        try:
            category_id = int(query.data.split('_')[1])
        except (ValueError, IndexError):
            # Если не удается получить ID, значит это не выбор категории
            await self._handle_unknown_callback(query, context)
            return
        
        try:
            user = await sync_to_async(lambda: telegram_user.user)()
            category = await Category.objects.aget(
                id=category_id,
                user=user,
            )
        except Category.DoesNotExist:
            await safe_edit_message_text(query, text="❌ Категория не найдена")
            return
        
        # Получаем состояние пользователя
        user_state = await self.get_user_state(telegram_user)
        
        if user_state.awaiting_category and user_state.current_amount:
            # Создаем транзакцию
            user = await sync_to_async(lambda: telegram_user.user)()
            transaction_service = TransactionService(user)
            transaction = await transaction_service.create_transaction(
                amount=user_state.current_amount,
                category=category,
                transaction_type=category.type,
            )
            
            # Обновляем состояние
            user_state.last_transaction_type = category.type
            user_state.current_amount = None
            user_state.awaiting_category = False
            await user_state.asave()

            from telegram_bot.services.command_executor import VOICE_CATEGORY_PENDING_KEY
            context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)
            
            # Отправляем подтверждение
            await self._send_transaction_confirmation(
                query,
                context,
                transaction,
            )
        else:
            await safe_edit_message_text(query,
                text="❌ Сначала укажите сумму",
            )
    
    async def _handle_type_switch(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает переключение типа транзакции"""
        new_type = query.data.split('_')[2]  # switch_to_expense -> expense
        
        # Получаем состояние
        user_state = await self.get_user_state(telegram_user)
        
        if user_state.current_amount:
            # Обновляем клавиатуру с новым типом
            keyboard_generator = CategoryKeyboard(telegram_user)
            keyboard = await keyboard_generator.get_frequent_categories_keyboard(
                new_type
            )
            
            transaction_emoji = "💸" if new_type == "expense" else "💰"
            type_name = "расход" if new_type == "expense" else "доход"
            
            message = (
                f"{transaction_emoji} {user_state.current_amount:,.0f}₽ - "
                f"выбери категорию ({type_name}):"
            )
            
            await safe_edit_message_text(query,
                text=message,
                reply_markup=keyboard,
            )
        else:
            await safe_edit_message_text(query,
                text="❌ Сначала укажите сумму",
            )
    
    async def _handle_page_navigation(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает навигацию по страницам категорий"""
        # page_expense_1 -> ['page', 'expense', '1']
        parts = query.data.split('_')
        transaction_type = parts[1]
        page = int(parts[2])
        
        keyboard_generator = CategoryKeyboard(telegram_user)
        keyboard = await keyboard_generator.get_categories_keyboard(
            transaction_type,
            page,
        )
        
        await query.edit_message_reply_markup(reply_markup=keyboard)
    
    async def _handle_all_categories(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает все категории"""
        transaction_type = query.data.split('_')[2]
        
        keyboard_generator = CategoryKeyboard(telegram_user)
        keyboard = await keyboard_generator.get_categories_keyboard(
            transaction_type,
            page=0,
        )
        
        user_state = await self.get_user_state(telegram_user)
        transaction_emoji = "💸" if transaction_type == "expense" else "💰"
        type_name = "расход" if transaction_type == "expense" else "доход"
        
        message = (
            f"{transaction_emoji} {user_state.current_amount:,.0f}₽ - "
            f"все категории ({type_name}):"
        )
        
        await safe_edit_message_text(query,
            text=message,
            reply_markup=keyboard,
        )
    
    async def _send_transaction_confirmation(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        transaction,
    ) -> None:
        """Отправляет подтверждение создания транзакции"""
        transaction_emoji = "💸" if transaction.category.type == "expense" else "💰"
        
        message = (
            f"✅ {abs(transaction.amount):,.0f}₽ → "
            f"{transaction.category.icon} {transaction.category.name}\n"
            f"Добавлено {transaction.date.strftime('%d.%m.%Y')}"
        )
        
        keyboard = ActionKeyboard.get_transaction_actions_keyboard(
            transaction.id
        )
        
        await safe_edit_message_text(query,
            text=message,
            reply_markup=keyboard,
        )
    
    async def _handle_transaction_edit(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает редактирование транзакции"""
        # edit_amount_123 / edit_date_123 / edit_comment_123
        parts = query.data.split('_')
        edit_type = parts[1]
        transaction_id = int(parts[2])

        if edit_type == 'amount':
            context.user_data['editing_transaction_amount'] = transaction_id

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="🔙 Отмена",
                        callback_data=f"transaction_actions_{transaction_id}",
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu",
                    ),
                ],
            ])

            await safe_edit_message_text(query,
                text="✏️ Введите новую сумму (например: 5000 или 499.90):",
                reply_markup=keyboard,
            )
        elif edit_type == 'date':
            # Устанавливаем состояние ожидания ввода даты
            context.user_data['editing_transaction_date'] = transaction_id

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="🔙 Отмена",
                        callback_data=f"transaction_actions_{transaction_id}"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu"
                    ),
                ],
            ])

            await safe_edit_message_text(query,
                text="📅 Введите новую дату в формате ДД.MM.YYYY\nНапример: 25.12.2024",
                reply_markup=keyboard,
            )
        elif edit_type == 'comment':
            # Устанавливаем состояние ожидания ввода комментария
            context.user_data['editing_transaction_comment'] = transaction_id

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="🔙 Отмена",
                        callback_data=f"transaction_actions_{transaction_id}"
                    ),
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu"
                    ),
                ],
            ])

            await safe_edit_message_text(query,
                text="💬 Введите комментарий к транзакции:",
                reply_markup=keyboard,
            )
    
    async def _handle_transaction_delete(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает удаление транзакции"""
        transaction_id = int(query.data.split('_')[2])
        
        user = await sync_to_async(lambda: telegram_user.user)()
        transaction_service = TransactionService(user)
        success = await transaction_service.delete_transaction(transaction_id)
        
        if success:
            await safe_edit_message_text(query, text="🗑️ Транзакция удалена")
        else:
            await safe_edit_message_text(query, text="❌ Транзакция не найдена")
    
    async def _handle_unknown_callback(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Обрабатывает неизвестные callback"""
        await safe_edit_message_text(query,
            text="❌ Неизвестная команда",
        )
    
    async def _handle_amount_selection(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор суммы"""
        # TODO: Реализовать выбор суммы
        await safe_edit_message_text(query, text="❌ Функция в разработке")
    
    async def _handle_add_expense(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Добавить расход'"""
        message = "💸 Введите сумму расхода:\n\nПримеры:\n• 500 кофе\n• 1500 продукты\n• 2000"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="🔙 Отмена",
                    callback_data="main_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                ),
            ],
        ])

        await safe_edit_message_text(query,text=message, reply_markup=keyboard)
    
    async def _handle_add_income(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Добавить доход'"""
        message = "💰 Введите сумму дохода:\n\nПримеры:\n• +5000 зарплата\n• +2000 подработка\n• +1000"
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="🔙 Отмена",
                    callback_data="main_menu"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Главное меню",
                    callback_data="main_menu"
                ),
            ],
        ])

        await safe_edit_message_text(query,text=message, reply_markup=keyboard)
    
    async def _handle_show_stats(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Статистика'"""
        from telegram_bot.services.transaction_service import TransactionService
        
        user = await sync_to_async(lambda: telegram_user.user)()
        transaction_service = TransactionService(user)
        stats = await transaction_service.get_today_statistics()
        
        stats_text = (
            f"📊 Статистика за сегодня:\n\n"
            f"💸 Расходы: {stats['expenses']:,.0f}₽\n"
            f"💰 Доходы: {stats['income']:,.0f}₽\n"
            f"💵 Баланс: {stats['balance']:,.0f}₽\n\n"
        )
        
        if stats['balance'] > 0:
            stats_text += "✅ Сегодня в плюсе!"
        elif stats['balance'] < 0:
            stats_text += "⚠️ Сегодня трат больше доходов"
        else:
            stats_text += "⚖️ Доходы равны расходам"
        
        from telegram_bot.keyboards.actions import ActionKeyboard
        keyboard = ActionKeyboard.get_main_menu_keyboard()
        
        await safe_edit_message_text(
            query,
            text=stats_text,
            reply_markup=keyboard,
        )
    
    async def _handle_show_budgets(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Бюджеты'"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        
        budget_handler = BudgetHandler()
        await budget_handler.handle_show_budgets(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_settings(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Настройки'"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_main_settings(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_settings_categories(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает раздел 'Категории' в настройках"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_categories_settings(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_settings_limits(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает раздел 'Лимиты' в настройках"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_limits_settings(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_limits_view(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает просмотр лимитов"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_limits_view(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_limits_add(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает добавление лимита"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_limits_add(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_limit_add(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает добавление лимита для конкретной категории"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_limit_add_for_category(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_limits_delete(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает удаление лимитов"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_limits_delete(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_limit_delete(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает удаление конкретного лимита"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим данные из callback
        callback_data = query.data
        
        if callback_data.startswith("limit_delete_confirm_"):
            # Подтверждение удаления
            try:
                budget_id = int(callback_data.replace("limit_delete_confirm_", ""))
                settings_handler = SettingsHandler()
                await settings_handler.handle_limit_delete_execution(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            except ValueError:
                await query.answer("Ошибка: неверный ID лимита")
        elif callback_data.startswith("limit_delete_"):
            # Выбор лимита для удаления
            try:
                budget_id = int(callback_data.replace("limit_delete_", ""))
                settings_handler = SettingsHandler()
                await settings_handler.handle_limit_delete_confirmation(
                    query,
                    context,
                    telegram_user,
                    budget_id,
                )
            except ValueError:
                await query.answer("Ошибка: неверный ID лимита")
        else:
            await query.answer("Неизвестная команда")
    
    async def _handle_settings_general(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает раздел 'Общие настройки' в настройках"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_general_settings(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_category_add(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Добавить категорию' в настройках"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Вызван _handle_category_add для пользователя {telegram_user.id}")
        
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_category_add(
            query,
            context,
            telegram_user,
        )
        
        logger.info("_handle_category_add завершен")
    
    async def _handle_category_add_type_selection(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор типа категории при добавлении"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим тип категории
        parts = query.data.split('_')
        if len(parts) >= 4:
            category_type = parts[3]  # 'income' или 'expense'
            
            settings_handler = SettingsHandler()
            await settings_handler.handle_category_add_type_selection(
                query,
                context,
                telegram_user,
                category_type,
            )
        else:
            await query.answer("Ошибка: неверный тип категории")
    
    async def _handle_category_list_by_type(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает отображение списка категорий по типу"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим данные из callback
        parts = query.data.split('_')
        if len(parts) >= 3:
            category_type = parts[2] # 'expense' или 'income'
            
            settings_handler = SettingsHandler()
            await settings_handler.handle_category_list_by_type(
                query,
                context,
                telegram_user,
                category_type,
            )
        else:
            await query.answer("Ошибка: неверный тип категории")
    
    async def _handle_category_edit(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает редактирование категорий"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        settings_handler = SettingsHandler()
        await settings_handler.handle_category_list(
            query,
            context,
            telegram_user,
            "edit",
        )
    
    async def _handle_category_edit_selection(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор категории для редактирования"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим ID категории
        parts = query.data.split('_')
        if len(parts) >= 3:
            try:
                category_id = int(parts[2])
                
                settings_handler = SettingsHandler()
                await settings_handler.handle_category_edit_selection(
                    query,
                    context,
                    telegram_user,
                    category_id,
                )
            except ValueError:
                await query.answer("Ошибка: неверный ID категории")
        else:
            await query.answer("Ошибка: неверный ID категории")
    
    async def _handle_category_delete(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает удаление категорий"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим ID категории
        parts = query.data.split('_')
        if len(parts) >= 3:
            try:
                category_id = int(parts[2])
                
                settings_handler = SettingsHandler()
                await settings_handler.handle_category_confirmation(
                    query,
                    context,
                    telegram_user,
                    "delete",
                    category_id,
                )
            except ValueError:
                await query.answer("Ошибка: неверный ID категории")
        else:
            await query.answer("Ошибка: неверный ID категории")
    
    async def _handle_category_actions(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает действия с категорией"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим ID категории
        parts = query.data.split('_')
        if len(parts) >= 3:
            category_id = int(parts[2])
            
            settings_handler = SettingsHandler()
            await settings_handler.handle_category_actions(
                query,
                context,
                telegram_user,
                category_id,
            )
        else:
            await query.answer("Ошибка: неверный ID категории")
    
    async def _handle_category_icon(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор иконки категории"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим ID категории
        parts = query.data.split('_')
        if len(parts) >= 3:
            category_id = int(parts[2])
            
            settings_handler = SettingsHandler()
            await settings_handler.handle_icon_selection(
                query,
                context,
                telegram_user,
                category_id,
            )
        else:
            await query.answer("Ошибка: неверный ID категории")
    
    async def _handle_category_icon_select(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор новой иконки из сетки"""
        from telegram_bot.handlers.settings_handler import SettingsHandler

        # Формат: category_icon_select_{category_id}_{icon}
        parts = query.data.split("_", 4)
        if len(parts) < 5:
            await query.answer("Ошибка: неверные данные иконки")
            return

        try:
            category_id = int(parts[3])
        except ValueError:
            await query.answer("Ошибка: неверный ID категории")
            return

        icon = parts[4]

        settings_handler = SettingsHandler()
        await settings_handler.handle_category_icon_change(
            query,
            context,
            telegram_user,
            category_id,
            icon,
        )
    
    async def _handle_category_rename(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает нажатие 'Переименовать'"""
        from telegram_bot.handlers.settings_handler import SettingsHandler

        parts = query.data.split('_')
        if len(parts) < 3:
            await query.answer("Ошибка: неверный ID категории")
            return

        try:
            category_id = int(parts[2])
        except ValueError:
            await query.answer("Ошибка: неверный ID категории")
            return

        settings_handler = SettingsHandler()
        await settings_handler.handle_category_rename_prompt(
            query,
            context,
            telegram_user,
            category_id,
        )
    
    async def _handle_category_type(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает изменение типа категории"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим ID категории
        parts = query.data.split('_')
        if len(parts) >= 3:
            try:
                category_id = int(parts[2])
                
                settings_handler = SettingsHandler()
                await settings_handler.handle_category_type(
                    query,
                    context,
                    telegram_user,
                    category_id,
                )
            except ValueError:
                await query.answer("Ошибка: неверный ID категории")
        else:
            await query.answer("Ошибка: неверный ID категории")
    
    async def _handle_category_type_select(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает выбор нового типа категории"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим данные: category_type_select_14_expense
        parts = query.data.split('_')
        if len(parts) >= 4:
            try:
                category_id = int(parts[3])
                new_type = parts[4]  # 'income' или 'expense'
                
                settings_handler = SettingsHandler()
                await settings_handler.handle_category_type_change(
                    query,
                    context,
                    telegram_user,
                    category_id,
                    new_type,
                )
            except (ValueError, IndexError):
                await query.answer("Ошибка: неверные данные категории")
        else:
            await query.answer("Ошибка: неверные данные категории")
    
    async def _handle_category_confirm(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает подтверждение действия с категорией"""
        from telegram_bot.handlers.settings_handler import SettingsHandler
        
        # Парсим данные: category_confirm_delete_14
        parts = query.data.split('_')
        if len(parts) >= 4:
            action = parts[2]  # 'delete'
            category_id = int(parts[3])  # 14
            
            settings_handler = SettingsHandler()
            await settings_handler.handle_category_action_execution(
                query,
                context,
                telegram_user,
                action,
                category_id,
            )
        else:
            await query.answer("Ошибка: неверные данные")
    
    async def _handle_main_menu(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает возврат в главное меню"""
        from telegram_bot.keyboards.actions import ActionKeyboard
        
        keyboard = ActionKeyboard.get_main_menu_keyboard()

        # Вариант A: не редактируем текущее сообщение (иначе исчезнут кнопки
        # действий по транзакции/редактированию). Вместо этого отправляем новое.
        #
        # При этом сбрасываем transient-состояния ввода, чтобы следующий текст
        # не был случайно обработан как "введите дату/комментарий/сумму".
        for key in (
            'editing_transaction_amount',
            'editing_transaction_date',
            'editing_transaction_comment',
            'waiting_for_budget_amount',
            'budget_category_id',
            'editing_budget_id',
            'limit_creation',
            'renaming_category_id',
            'goal_creation_step',
            'goal_creation_data',
            'goal_deposit_goal_id',
            'goal_withdraw_goal_id',
        ):
            context.user_data.pop(key, None)

        await query.answer()
        await query.message.reply_text(
            text="🏠 Главное меню FinHub\n\nВыберите действие:",
            reply_markup=keyboard,
        )

    async def _handle_goals_menu(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        for key in (
            'goal_creation_step',
            'goal_creation_data',
            'goal_deposit_goal_id',
            'goal_withdraw_goal_id',
        ):
            context.user_data.pop(key, None)

        handler = GoalsHandler()
        await handler.handle_goals_menu(query, context, telegram_user)

    async def _handle_goals_list(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        for key in (
            'goal_creation_step',
            'goal_creation_data',
            'goal_deposit_goal_id',
            'goal_withdraw_goal_id',
        ):
            context.user_data.pop(key, None)

        handler = GoalsHandler()
        await handler.handle_goals_list(query, context, telegram_user)

    async def _handle_goal_view(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        for key in (
            'goal_creation_step',
            'goal_creation_data',
            'goal_deposit_goal_id',
            'goal_withdraw_goal_id',
        ):
            context.user_data.pop(key, None)

        handler = GoalsHandler()
        await handler.handle_goal_view(query, context, telegram_user, goal_id)

    async def _handle_goal_history(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        for key in (
            'goal_creation_step',
            'goal_creation_data',
            'goal_deposit_goal_id',
            'goal_withdraw_goal_id',
        ):
            context.user_data.pop(key, None)

        handler = GoalsHandler()
        await handler.handle_goal_history(query, context, telegram_user, goal_id)

    async def _handle_goal_create_prompt(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from telegram_bot.keyboards.goals import GoalsKeyboard

        # Сбрасываем, если ранее уже был начат flow
        context.user_data.pop('goal_creation_data', None)
        context.user_data['goal_creation_step'] = 'title'
        context.user_data['goal_creation_data'] = {}

        keyboard = GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu")
        await safe_edit_message_text(query,
            text="➕ **Создать цель**\n\nВведите название цели (например: iPad / Машина / Отпуск):",
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

    async def _handle_goal_deposit_prompt(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        from telegram_bot.keyboards.goals import GoalsKeyboard

        context.user_data['goal_deposit_goal_id'] = goal_id
        keyboard = GoalsKeyboard.get_goal_input_keyboard(cancel_callback=f"goal_view_{goal_id}")
        await safe_edit_message_text(query,
            text="➕ **Внести в цель**\n\nВведите сумму (например: 5000 или 499.90):",
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

    async def _handle_goal_withdraw_prompt(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
    ) -> None:
        from telegram_bot.keyboards.goals import GoalsKeyboard

        context.user_data['goal_withdraw_goal_id'] = goal_id
        keyboard = GoalsKeyboard.get_goal_input_keyboard(cancel_callback=f"goal_view_{goal_id}")
        await safe_edit_message_text(query,
            text="↩️ **Снять из цели**\n\nВведите сумму, которую хотите снять:",
            reply_markup=keyboard,
            parse_mode='Markdown',
        )

    async def _handle_goal_quick_deposit(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
        amount: int,
    ) -> None:
        from decimal import Decimal
        from asgiref.sync import sync_to_async
        from telegram_bot.handlers.goals_handler import GoalsHandler
        from telegram_bot.services.goal_service import GoalService

        user = await sync_to_async(lambda: telegram_user.user)()
        service = GoalService(user)
        entry = await service.add_deposit(goal_id, Decimal(amount))
        if not entry:
            await query.answer("Цель не найдена")
            return

        await query.answer("✅ Переведено")
        handler = GoalsHandler()
        await handler.handle_goal_view(query, context, telegram_user, goal_id)
    
    async def _handle_show_report(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Отчет'"""
        from telegram_bot.handlers.report_handler import ReportHandler
        
        report_handler = ReportHandler()
        await report_handler.handle_show_report(
            query,  # Передаем CallbackQuery напрямую
            context,
            telegram_user,
        )
    
    async def _handle_report_current(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает отчет за текущий месяц"""
        from telegram_bot.handlers.report_handler import ReportHandler
        
        report_handler = ReportHandler()
        await report_handler.handle_current_report(
            query,  # Передаем CallbackQuery напрямую
            context,
            telegram_user,
        )
    
    async def _handle_report_all(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает кнопку 'Все отчеты'"""
        from telegram_bot.handlers.report_handler import ReportHandler
        
        # Показываем первый доступный отчет
        report_handler = ReportHandler()
        await report_handler.handle_current_report(
            query,
            context,
            telegram_user,
        )

    async def _handle_report_export_excel_current(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Экспорт Excel за текущий месяц"""
        from datetime import datetime
        from telegram_bot.handlers.report_handler import ReportHandler

        now = datetime.now()
        report_handler = ReportHandler()
        await report_handler.handle_export_excel_month(
            query,
            context,
            telegram_user,
            now.year,
            now.month,
        )

    async def _handle_report_export_excel_period(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Экспорт Excel за выбранный период"""
        from telegram_bot.handlers.report_handler import ReportHandler

        # report_export_excel_2026_01
        parts = query.data.split('_')
        if len(parts) >= 5:
            year = int(parts[3])
            month = int(parts[4])
            report_handler = ReportHandler()
            await report_handler.handle_export_excel_month(
                query,
                context,
                telegram_user,
                year,
                month,
            )
        else:
            await query.answer("Ошибка: неверный период для экспорта")
    
    async def _handle_report_navigation(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Обрабатывает навигацию по отчетам"""
        from telegram_bot.handlers.report_handler import ReportHandler
        
        # Парсим данные из callback
        parts = query.data.split('_')
        if len(parts) >= 4:
            year = int(parts[2])
            month = int(parts[3])
            
            report_handler = ReportHandler()
            await report_handler.handle_report_navigation(
                query,  # Передаем CallbackQuery напрямую
                context,
                telegram_user,
                year,
                month,
            )
        else:
            await query.answer("Ошибка навигации по отчетам")
    
    # Методы для обработки бюджетов
    async def _handle_budgets_view(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает список бюджетов"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budgets_view(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_budgets_add(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        """Показывает форму добавления бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budgets_add(
            query,
            context,
            telegram_user,
        )
    
    async def _handle_budget_detail(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает детали бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budget_detail(
            query,
            context,
            telegram_user,
            budget_id,
        )
    
    async def _handle_budget_add_for_category(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Показывает форму для ввода суммы бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budget_add_for_category(
            query,
            context,
            telegram_user,
            category_id,
        )
    
    async def _handle_budget_delete_confirmation(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Показывает подтверждение удаления бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budget_delete_confirmation(
            query,
            context,
            telegram_user,
            budget_id,
        )
    
    async def _handle_budget_delete_execution(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Выполняет удаление бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budget_delete_execution(
            query,
            context,
            telegram_user,
            budget_id,
        )
    
    async def _handle_budget_edit(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        budget_id: int,
    ) -> None:
        """Обрабатывает редактирование бюджета"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        
        budget_handler = BudgetHandler()
        await budget_handler.handle_budget_edit(
            query,
            context,
            telegram_user,
            budget_id,
        )
    
    async def _handle_category_budget(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        """Обрабатывает кнопку бюджета в настройках категории"""
        from telegram_bot.handlers.budget_handler import BudgetHandler
        budget_handler = BudgetHandler()
        
        await budget_handler.handle_budget_add_for_category(
            query,
            context,
            telegram_user,
            category_id,
        )

    async def _handle_voice_confirm(
        self,
        update: Update,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        await query.answer()
        await self._command_executor.execute_from_voice_pending(
            update,
            context,
            telegram_user,
        )

    async def _handle_voice_cat_pick(
        self,
        update: Update,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        await query.answer()
        try:
            category_id = int(query.data.split('_')[-1])
        except (ValueError, IndexError):
            await query.answer('Ошибка данных')
            return
        await self._command_executor.apply_voice_category_pick(
            update,
            context,
            telegram_user,
            category_id,
        )

    async def _handle_voice_cat_all(
        self,
        update: Update,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        await query.answer()
        await self._command_executor.show_voice_all_categories(
            update,
            context,
            telegram_user,
        )

    async def _handle_voice_cat_create(
        self,
        update: Update,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        await query.answer()
        await self._command_executor.start_voice_category_create(
            update,
            context,
            telegram_user,
        )

    async def _handle_voice_dialog_type(
        self,
        update: Update,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        from telegram_bot.voice.dialog import VoiceDialogManager

        tx_type = 'income' if query.data.endswith('income') else 'expense'
        await VoiceDialogManager().set_type_callback(
            update,
            context,
            telegram_user,
            tx_type,
        )

    async def _handle_voice_cancel(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        from telegram_bot.services.command_executor import (
            VOICE_CATEGORY_PENDING_KEY,
            VOICE_PENDING_KEY,
        )
        from telegram_bot.voice.dialog import clear_dialog

        context.user_data.pop(VOICE_PENDING_KEY, None)
        context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)
        clear_dialog(context)
        await query.answer('Отменено')
        await safe_edit_message_text(query, text='❌ Голосовая команда отменена.') 