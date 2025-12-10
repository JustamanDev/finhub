import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.categories import CategoryKeyboard
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.transaction_service import TransactionService
from telegram_bot.services.category_management_service import CategoryManagementService
from budgets.models import Budget
from categories.models import Category
from datetime import datetime as _dt

logger = logging.getLogger(__name__)


class TextHandler(BaseHandler):
    """Обработчик текстовых сообщений"""
    
    async def handle_text_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Обрабатывает текстовые сообщения
        
        Args:
            update: Объект Update
            context: Контекст бота
        """
        try:
            # Логируем входящее сообщение для отладки
            logger.info(f"Получено текстовое сообщение: {update.message.text}")
            
            # Получаем пользователя
            telegram_user = await self.get_or_create_telegram_user(
                update.effective_user
            )

            # --- Переименование категории ---
            # Если установлен флаг renaming_category_id, любое сообщение
            # трактуем как новое имя категории.
            renaming_category_id = context.user_data.get("renaming_category_id")
            if renaming_category_id:
                await self._handle_category_rename_input(
                    update,
                    context,
                    telegram_user,
                    renaming_category_id,
                    update.message.text,
                )
                return
            
            # --- Обработка состояний редактирования (дата/комментарий) ---
            # Сначала проверим, не находится ли пользователь в режиме редактирования даты транзакции
            if context.user_data.get('editing_transaction_date'):
                transaction_id = context.user_data.get('editing_transaction_date')
                text = update.message.text.strip()
                try:
                    # Пытаемся распарсить дату в формате ДД.ММ.ГГГГ или YYYY-MM-DD
                    try:
                        new_date = _dt.strptime(text, '%d.%m.%Y').date()
                    except ValueError:
                        new_date = _dt.strptime(text, '%Y-%m-%d').date()

                    user = await sync_to_async(lambda: telegram_user.user)()
                    transaction_service = TransactionService(user)
                    updated = await transaction_service.update_transaction_date(transaction_id, new_date)

                    if updated:
                        keyboard = ActionKeyboard.get_transaction_actions_keyboard(transaction_id)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"✅ Дата транзакции обновлена на {new_date.strftime('%d.%m.%Y')}",
                            reply_markup=keyboard,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="❌ Транзакция не найдена или недоступна.",
                        )
                except ValueError:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Неверный формат даты. Используйте ДД.MM.YYYY или YYYY-MM-DD",
                    )
                finally:
                    # Очищаем состояние редактирования
                    if 'editing_transaction_date' in context.user_data:
                        del context.user_data['editing_transaction_date']
                return

            # Проверяем, ожидается ли ввод комментария для редактирования транзакции
            if context.user_data.get('editing_transaction_comment'):
                transaction_id = context.user_data.get('editing_transaction_comment')
                comment_text = update.message.text.strip()
                user = await sync_to_async(lambda: telegram_user.user)()
                transaction_service = TransactionService(user)
                updated = await transaction_service.update_transaction_description(transaction_id, comment_text)

                if updated:
                    keyboard = ActionKeyboard.get_transaction_actions_keyboard(transaction_id)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="✅ Комментарий обновлён.",
                        reply_markup=keyboard,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Транзакция не найдена или недоступна.",
                    )

                if 'editing_transaction_comment' in context.user_data:
                    del context.user_data['editing_transaction_comment']
                return

            # Проверяем, ожидается ли создание категории
            user_state = await self.get_user_state(telegram_user)
            
            if user_state.awaiting_category_creation:
                await self._handle_category_creation(
                    update,
                    context,
                    telegram_user,
                    update.message.text,
                )
                return
            
            # Проверяем, ожидается ли ввод суммы лимита
            if 'limit_creation' in context.user_data:
                await self._handle_limit_amount_input(
                    update,
                    context,
                    telegram_user,
                    update.message.text,
                )
                return
            
            # Проверяем, ожидается ли ввод суммы бюджета
            if context.user_data.get('waiting_for_budget_amount'):
                await self._handle_budget_amount_input(
                    update,
                    context,
                    telegram_user,
                    update.message.text,
                )
                return
            
            # Логируем входящее сообщение
            await self.log_message(
                telegram_user,
                'incoming',
                update.message.text,
            )
            
            # Парсим команду
            user = await sync_to_async(lambda: telegram_user.user)()
            parser = await sync_to_async(self.get_parser)(user)
            parsed_command = await sync_to_async(parser.parse)(update.message.text)
            
            if not parsed_command['success']:
                await self._send_error_message(
                    update,
                    context,
                    parsed_command['error'],
                )
                return
            
            # Обрабатываем команду по типу
            if parsed_command['type'] == 'amount_category':
                await self._handle_amount_category(
                    update,
                    context,
                    telegram_user,
                    parsed_command,
                )
            elif parsed_command['type'] == 'amount_only':
                await self._handle_amount_only(
                    update,
                    context,
                    telegram_user,
                    parsed_command,
                )
            elif parsed_command['type'] == 'category_only':
                await self._handle_category_only(
                    update,
                    context,
                    telegram_user,
                    parsed_command,
                )
            elif parsed_command['type'] == 'alias':
                await self._handle_alias(
                    update,
                    context,
                    telegram_user,
                    parsed_command,
                )
            else:
                await self._send_help_message(update, context)
                
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_text_message: {e}")
            await self.handle_error(update, context, e)
    
    async def _handle_amount_category(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду с суммой и категорией"""
        user = await sync_to_async(lambda: telegram_user.user)()
        transaction_service = TransactionService(user)
        
        if parsed_command['category']:
            # Категория найдена - создаем транзакцию
            try:
                transaction = await transaction_service.create_transaction(
                    amount=parsed_command['amount'],
                    category=parsed_command['category'],
                    transaction_type=parsed_command['transaction_type'],
                )
                
                # Обновляем состояние пользователя
                user_state = await self.get_user_state(telegram_user)
                user_state.last_transaction_type = parsed_command['transaction_type']
                await user_state.asave()
                
                await self._send_transaction_created_message(
                    update,
                    context,
                    transaction,
                )
            except Exception as e:
                logger.error(f"❌ Ошибка создания транзакции: {e}")
                await self._send_error_message(
                    update,
                    context,
                    f"Ошибка создания транзакции: {e}",
                )
        else:
            # Категория не найдена - предлагаем выбрать
            await self._send_category_selection(
                update,
                context,
                telegram_user,
                parsed_command['amount'],
                parsed_command['transaction_type'],
                f"Категория '{parsed_command['category_name']}' не найдена.",
            )
    
    async def _handle_amount_only(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду только с суммой"""
        # Сохраняем сумму в состоянии
        user_state = await self.get_user_state(telegram_user)
        user_state.current_amount = parsed_command['amount']
        user_state.awaiting_category = True
        await user_state.asave()
        
        # Определяем тип транзакции
        if parsed_command.get('transaction_type'):
            transaction_type = parsed_command['transaction_type']
        else:
            transaction_type = user_state.last_transaction_type
        
        await self._send_category_selection(
            update,
            context,
            telegram_user,
            parsed_command['amount'],
            transaction_type,
        )
    
    async def _send_category_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        amount,
        transaction_type: str,
        prefix_message: str = "",
    ) -> None:
        """Отправляет сообщение с выбором категории"""
        keyboard_generator = CategoryKeyboard(telegram_user)
        keyboard = await keyboard_generator.get_frequent_categories_keyboard(
            transaction_type
        )
        
        transaction_emoji = "💸" if transaction_type == "expense" else "💰"
        type_name = "расход" if transaction_type == "expense" else "доход"
        
        message = f"{prefix_message}\n" if prefix_message else ""
        message += f"{transaction_emoji} {amount:,.0f}₽ - выбери категорию ({type_name}):"
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=keyboard,
        )
    
    async def _send_transaction_created_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        transaction,
    ) -> None:
        """Отправляет сообщение о созданной транзакции"""
        transaction_emoji = "💸" if transaction.category.type == "expense" else "💰"
        
        message = (
            f"✅ {abs(transaction.amount):,.0f}₽ → "
            f"{transaction.category.icon} {transaction.category.name}\n"
            f"Добавлено {transaction.date.strftime('%d.%m.%Y')}"
        )
        
        keyboard = ActionKeyboard.get_transaction_actions_keyboard(
            transaction.id
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=keyboard,
        )
    
    async def _send_error_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_text: str,
    ) -> None:
        """Отправляет сообщение об ошибке"""
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ {error_text}",
        )
    
    async def _send_help_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Отправляет справочное сообщение"""
        help_text = (
            "💡 Как пользоваться ботом:\n\n"
            "📝 Быстрый ввод:\n"
            "• 500 кофе - добавить расход\n"
            "• +1000 зарплата - добавить доход\n"
            "• 500 - выбрать категорию\n\n"
            "🔧 Команды:\n"
            "• /start - главное меню\n"
            "• /stats - статистика\n"
            "• /help - эта справка"
        )
        
        keyboard = ActionKeyboard.get_main_menu_keyboard()
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_text,
            reply_markup=keyboard,
        )
    
    async def _handle_category_only(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду только с категорией"""
        # TODO: Реализовать умные предложения
        await self._send_help_message(update, context)
    
    async def _handle_alias(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду с алиасом"""
        await self._send_error_message(
            update,
            context,
            "Алиасы пока не поддерживаются",
        )
    
    async def _handle_category_creation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        text: str,
    ) -> None:
        """Обрабатывает создание новой категории"""
        from telegram_bot.services.category_management_service import CategoryManagementService
        
        logger.info(f"Начинаем создание категории: {text}")
        
        try:
            if not text.strip():
                await self._send_error_message(
                    update,
                    context,
                    "Неверный формат. Используйте: `название [иконка]`\n"
                    "**Примеры:**\n"
                    "• `🥕 Продукты`\n"
                    "• `Продукты 🥕`\n"
                    "• `Продукты`"
                )
                return
            
            # Разбираем имя и иконку (эмодзи может быть в начале/конце/внутри)
            name, icon = self._parse_category_name_and_icon(text)
            logger.info(f"Парсинг категории (создание): name={name!r}, icon={icon!r}")
            
            # Получаем тип категории из состояния
            user_state = await self.get_user_state(telegram_user)
            category_type = user_state.context_data.get("category_type", "expense")
            
            logger.info(f"Тип категории из состояния: {category_type}")
            
            # Нормализуем тип
            if category_type == "income":
                normalized_type = "income"
            else:
                normalized_type = "expense"
            
            logger.info(f"Нормализованный тип: {normalized_type}")
            
            # Создаем категорию
            user = await sync_to_async(lambda: telegram_user.user)()
            category_service = CategoryManagementService(user)
            
            logger.info(f"Создаем категорию для пользователя {user.id}")
            
            category = await category_service.create_category(
                name=name,
                category_type=normalized_type,
                icon=icon,
            )
            
            # Сбрасываем состояние
            user_state.awaiting_category_creation = False
            user_state.context_data = {}
            await user_state.asave()
            
            logger.info(f"Категория создана успешно: {category.name} ({category.type})")
            
            # Отправляем подтверждение
            type_name = "доходов" if normalized_type == "income" else "расходов"
            message = (
                f"✅ **Категория создана!**\n\n"
                f"**{category.icon} {category.name}**\n"
                f"Тип: {type_name}\n\n"
                f"Теперь вы можете добавлять {type_name} в эту категорию."
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="➕ Добавить еще",
                        callback_data="category_add"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📂 Категории",
                        callback_data="settings_categories"
                    ),
                ],
            ]
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
            )
            
        except Exception as e:
            logger.error(f"Ошибка при создании категории: {e}")
            
            # Сбрасываем состояние в случае ошибки
            user_state = await self.get_user_state(telegram_user)
            user_state.awaiting_category_creation = False
            user_state.context_data = {}
            await user_state.asave()
            
            await self._send_error_message(
                update,
                context,
                f"Ошибка при создании категории: {str(e)}"
            ) 
    
    async def _handle_budget_amount_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        text: str,
    ) -> None:
        """Обрабатывает ввод суммы бюджета"""
        logger = logging.getLogger('text_handler')
        
        try:
            logger.info(f"🔍 Начало обработки ввода бюджета: {text}")
            
            # Импорты в начале метода
            from asgiref.sync import sync_to_async
            from django.utils import timezone
            from datetime import datetime, timedelta
            
            logger.info("✅ Импорты выполнены успешно")
            
            # Парсим сумму
            amount = float(text.replace(',', '.'))
            if amount <= 0:
                raise ValueError("Сумма должна быть больше нуля")
            
            logger.info(f"✅ Сумма распарсена: {amount}")
            
            user = await sync_to_async(lambda: telegram_user.user)()
            logger.info(f"✅ Пользователь получен: {user.username}")
            
            # Проверяем, редактируем ли мы существующий бюджет
            editing_budget_id = context.user_data.get('editing_budget_id')
            logger.info(f"🔍 ID редактируемого бюджета: {editing_budget_id}")
            
            if editing_budget_id:
                logger.info("🔄 Режим редактирования бюджета")
                # При редактировании получаем категорию из бюджета
                try:
                    logger.info(f"🔍 Получаем бюджет с ID: {editing_budget_id}")
                    budget = await sync_to_async(lambda: Budget.objects.get(
                        id=editing_budget_id,
                        user=user,
                        is_active=True,
                    ), thread_sensitive=True)()
                    logger.info(f"✅ Бюджет найден: {budget}")
                    category = await sync_to_async(lambda: budget.category)()
                    category_name = await sync_to_async(lambda: category.name)()
                    logger.info(f"✅ Категория получена: {category_name}")
                    
                    # Обновляем сумму бюджета
                    budget_amount = await sync_to_async(lambda: budget.amount)()
                    logger.info(f"🔄 Обновляем сумму с {budget_amount} на {amount}")
                    await sync_to_async(lambda: setattr(budget, 'amount', amount))()
                    await sync_to_async(budget.save)()
                    logger.info("✅ Бюджет обновлен успешно")
                    
                    action_text = "обновлен"
                    period_display = "текущий месяц"
                    
                    # Очищаем ID редактируемого бюджета
                    if 'editing_budget_id' in context.user_data:
                        del context.user_data['editing_budget_id']
                        logger.info("✅ ID редактируемого бюджета очищен")
                        
                except Exception as e:
                    if "DoesNotExist" in str(type(e).__name__):
                        logger.error(f"❌ Бюджет с ID {editing_budget_id} не найден")
                        await self._send_error_message(
                            update,
                            context,
                            "❌ Бюджет для редактирования не найден."
                        )
                        return
                    else:
                        logger.error(f"❌ Ошибка при редактировании бюджета: {e}")
                        await self._send_error_message(
                            update,
                            context,
                            f"❌ Ошибка при редактировании бюджета: {str(e)}"
                        )
                        return
            else:
                logger.info("🆕 Режим создания нового бюджета")
                # Получаем ID категории из контекста для создания нового бюджета
                category_id = context.user_data.get('budget_category_id')
                logger.info(f"🔍 ID категории из контекста: {category_id}")
                
                if not category_id:
                    logger.error("❌ ID категории не найден в контексте")
                    await self._send_error_message(
                        update,
                        context,
                        "❌ Категория не выбрана. Попробуйте еще раз."
                    )
                    return
                
                try:
                    logger.info(f"🔍 Получаем категорию с ID: {category_id}")
                    category = await sync_to_async(lambda: Category.objects.get(
                        id=category_id,
                        user=user
                    ), thread_sensitive=True)()
                    category_name = await sync_to_async(lambda: category.name)()
                    logger.info(f"✅ Категория получена: {category_name}")
                    
                    # Проверяем, есть ли уже бюджет для этой категории в текущем месяце
                    logger.info("🔍 Проверяем существующие бюджеты")
                    today = await sync_to_async(timezone.now, thread_sensitive=True)()
                    today = today.date()
                    logger.info(f"✅ Сегодня: {today}")
                    
                    # Вычисляем даты через sync_to_async
                    start_date = await sync_to_async(lambda: datetime(today.year, today.month, 1).date())()
                    logger.info(f"✅ Дата начала: {start_date}")
                    
                    # Последний день месяца
                    if today.month == 12:
                        end_date = await sync_to_async(lambda: datetime(today.year + 1, 1, 1).date())()
                    else:
                        end_date = await sync_to_async(lambda: datetime(today.year, today.month + 1, 1).date())()
                    end_date = await sync_to_async(lambda: end_date - timedelta(days=1))()
                    logger.info(f"✅ Дата окончания: {end_date}")
                    
                    # Проверяем существующий бюджет
                    budget_queryset = await sync_to_async(lambda: Budget.objects.filter(
                        user=user,
                        category=category,
                        start_date=start_date,
                        end_date=end_date,
                        is_active=True
                    ), thread_sensitive=True)()
                    existing_budget = await sync_to_async(lambda: budget_queryset.first(), thread_sensitive=True)()
                    
                    if existing_budget:
                        logger.info("🔄 Найден существующий бюджет: id=%s", existing_budget.id)
                        # Обновляем существующий бюджет
                        await sync_to_async(lambda: setattr(existing_budget, 'amount', amount))()
                        await sync_to_async(existing_budget.save, thread_sensitive=True)()
                        logger.info("✅ Существующий бюджет обновлен")
                        action_text = "обновлен"
                    else:
                        logger.info("🆕 Создаем новый бюджет")
                        # Создаем новый бюджет
                        budget = await sync_to_async(lambda: Budget.objects.create(
                            user=user,
                            category=category,
                            amount=amount,
                            period_type='monthly',
                            start_date=start_date,
                            end_date=end_date
                        ), thread_sensitive=True)()
                        logger.info(f"✅ Новый бюджет создан: {budget}")
                        action_text = "создан"
                    
                    period_display = "текущий месяц"
                    
                except Exception as e:
                    if "DoesNotExist" in str(type(e).__name__):
                        logger.exception(f"❌ Категория с ID {category_id} не найдена")
                        await self._send_error_message(
                            update,
                            context,
                            "❌ Категория не найдена."
                        )
                        return
                    else:
                        raise
                except Exception as e:
                    logger.exception("❌ Ошибка при создании бюджета")
                    await self._send_error_message(
                        update,
                        context,
                        f"❌ Ошибка при создании бюджета: {str(e)}"
                    )
                    return
            
            # Получаем иконку и название категории
            logger.info("🔍 Получаем данные категории для отображения")
            category_icon = await sync_to_async(lambda: category.icon)()
            category_name = await sync_to_async(lambda: category.name)()
            logger.info(f"✅ Данные категории: {category_icon} {category_name}")
            
            # Формируем сообщение в зависимости от типа операции
            if editing_budget_id:
                logger.info("📝 Формируем сообщение для редактирования")
                message = (
                    f"✅ **Бюджет {action_text}!**\n\n"
                    f"💰 **Категория:** {category_icon} {category_name}\n"
                    f"💸 **Сумма:** {amount:,.2f} ₽\n"
                    f"📅 **Период:** {period_display}\n\n"
                    f"Бюджет обновлен успешно."
                )
            else:
                logger.info("📝 Формируем сообщение для создания")
                message = (
                    f"✅ **Бюджет {action_text}!**\n\n"
                    f"💰 **Категория:** {category_icon} {category_name}\n"
                    f"💸 **Сумма:** {amount:,.2f} ₽\n"
                    f"📅 **Период:** {period_display}\n"
                    f"📆 **Даты:** {start_date} - {end_date}\n\n"
                    f"Бюджет поможет контролировать расходы по этой категории."
                )
            
            logger.info("✅ Сообщение сформировано")
            
            # Очищаем контекст
            if 'waiting_for_budget_amount' in context.user_data:
                del context.user_data['waiting_for_budget_amount']
                logger.info("✅ waiting_for_budget_amount очищен")
            if 'budget_category_id' in context.user_data:
                del context.user_data['budget_category_id']
                logger.info("✅ budget_category_id очищен")
            
            logger.info("✅ Контекст очищен")
            
            # Отправляем сообщение
            logger.info("📤 Отправляем сообщение пользователю")
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text="📊 К списку бюджетов",
                        callback_data="budgets_view"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu"
                    ),
                ],
            ])

            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            logger.info("✅ Сообщение отправлено успешно")
            
        except Exception as e:
            logger.exception("❌ КРИТИЧЕСКАЯ ОШИБКА при создании бюджета")
            await self._send_error_message(
                update,
                context,
                f"❌ Произошла ошибка при создании бюджета: {str(e)}"
            )
    
    async def _handle_limit_amount_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        text: str,
    ) -> None:
        """Обрабатывает ввод суммы лимита"""
        try:
            # Парсим сумму
            amount_text = text.strip().replace(',', '.').replace(' ', '')
            
            try:
                amount = float(amount_text)
                if amount <= 0:
                    raise ValueError("Сумма должна быть больше нуля")
            except ValueError:
                message = (
                    "❌ **Неверный формат суммы**\n\n"
                    "Введите сумму в рублях (например: 5000 или 5000.50):"
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
                return
            
            # Получаем данные о создании лимита
            limit_data = context.user_data.get('limit_creation', {})
            category_id = limit_data.get('category_id')
            
            if not category_id:
                message = "❌ Ошибка: не найдена категория"
                keyboard = [
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад",
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
                await self._send_or_edit_message(
                    update,
                    context,
                    message,
                    keyboard,
                )
                return
            
            # Создаем бюджет (лимит) в базе данных
            from datetime import date
            
            # Создаем месячный бюджет для текущего месяца
            current_date = date.today()
            budget = await sync_to_async(lambda: Budget.objects.create(
                user=user,
                category=category,
                amount=amount,
                period_type='monthly',
                start_date=current_date.replace(day=1),  # Первый день месяца
                end_date=current_date.replace(day=28),   # Последний день месяца
                is_active=True,
            ))()
            
            message = (
                f"✅ **Бюджет создан**\n\n"
                f"Категория: {category.icon} {category.name}\n"
                f"Сумма: {amount:,.2f} ₽\n"
                f"Период: Месячный\n\n"
                f"Бюджет будет применяться к расходам в этой категории."
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
                        text="➕ Добавить еще",
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
            
            # Очищаем состояние
            if 'limit_creation' in context.user_data:
                del context.user_data['limit_creation']
            
            await self._send_or_edit_message(
                update,
                context,
                message,
                keyboard,
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_limit_amount_input: {e}")
            message = "❌ Произошла ошибка при создании лимита"
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="🔙 Назад",
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

    def _parse_category_name_and_icon(self, text: str) -> tuple[str, str]:
        """
        Разбирает ввод пользователя для категории:
        - name: полная строка как есть
        - icon: первое встреченное эмодзи или дефолт
        """
        raw_text = text.strip()

        def is_emoji(ch: str) -> bool:
            return (
                "\U0001F300" <= ch <= "\U0001FAFF"
                or "\u2600" <= ch <= "\u26FF"
                or "\u2700" <= ch <= "\u27BF"
            )

        icon = "📁"
        for ch in raw_text:
            if is_emoji(ch):
                icon = ch
                break

        name = raw_text
        return name, icon

    async def _handle_category_rename_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
        text: str,
    ) -> None:
        """Обрабатывает ввод нового названия категории"""
        from telegram_bot.services.category_management_service import CategoryManagementService

        logger.info(f"Переименование категории {category_id}: {text!r}")

        if not text.strip():
            await self._send_error_message(
                update,
                context,
                "Название категории не может быть пустым.",
            )
            return

        name, icon = self._parse_category_name_and_icon(text)
        user = await sync_to_async(lambda: telegram_user.user)()
        category_service = CategoryManagementService(user)

        category = await category_service.get_category_by_id(category_id)
        if not category:
            await self._send_error_message(
                update,
                context,
                "Категория не найдена.",
            )
            context.user_data.pop("renaming_category_id", None)
            return

        # Обновляем категорию
        await category_service.update_category(
            category_id=category_id,
            name=name,
            icon=icon,
        )

        context.user_data.pop("renaming_category_id", None)

        message = (
            "✅ **Категория переименована!**\n\n"
            f"Теперь: {icon} {name}"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
        ) 
    
    async def _send_or_edit_message(
        self,
        update: Update,
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
        
        try:
            # Для текстовых сообщений всегда отправляем новое сообщение
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения: {e}")
            # Отправляем простое сообщение без форматирования
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                reply_markup=reply_markup,
            ) 