import logging
from decimal import Decimal
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async

from .base import BaseHandler
from telegram_bot.keyboards.categories import CategoryKeyboard
from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.services.command_executor import CommandExecutor
from telegram_bot.services.transaction_service import TransactionService
from telegram_bot.services.category_management_service import CategoryManagementService
from telegram_bot.services.goal_service import GoalService
from telegram_bot.voice.interpreter import voice_text_parse_candidates
from budgets.models import Budget
from categories.models import Category
from datetime import datetime as _dt

logger = logging.getLogger(__name__)


class TextHandler(BaseHandler):
    """Обработчик текстовых сообщений"""

    def __init__(self) -> None:
        super().__init__()
        self._command_executor = CommandExecutor()

    @staticmethod
    def _parse_money(text: str) -> Decimal:
        cleaned = text.strip().replace(' ', '').replace(',', '.')
        return Decimal(cleaned)

    @staticmethod
    def _is_no_deadline(text: str) -> bool:
        t = text.strip().lower()
        return t in (
            'без срока',
            'без дедлайна',
            'нет',
            '-',
            '0',
        )

    async def _handle_goal_creation_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        message_text: str,
    ) -> None:
        step = context.user_data.get('goal_creation_step')
        data = context.user_data.get('goal_creation_data', {})
        text = message_text.strip()

        from telegram_bot.keyboards.goals import GoalsKeyboard
        from decimal import InvalidOperation
        from django.db import IntegrityError

        if step == 'title':
            if len(text) < 2:
                await update.message.reply_text(
                    "❌ Название слишком короткое.\n\n"
                    "Пример: **iPad**, **Машина**, **Отпуск**",
                    reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                    parse_mode='Markdown',
                )
                return

            data['title'] = text
            context.user_data['goal_creation_data'] = data
            context.user_data['goal_creation_step'] = 'amount'

            await update.message.reply_text(
                "💰 Введите целевую сумму (например: 100000 или 250000.50):",
                reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                parse_mode='Markdown',
            )
            return

        if step == 'amount':
            try:
                amount = self._parse_money(text)
            except (InvalidOperation, ValueError):
                await update.message.reply_text(
                    "❌ Неверный формат суммы.\n\nПримеры: **100000**, **250000.50**",
                    reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                    parse_mode='Markdown',
                )
                return

            if amount <= 0:
                await update.message.reply_text(
                    "❌ Сумма должна быть больше нуля.\n\nПример: **100000**",
                    reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                    parse_mode='Markdown',
                )
                return

            data['target_amount'] = str(amount)
            context.user_data['goal_creation_data'] = data
            context.user_data['goal_creation_step'] = 'deadline'

            await update.message.reply_text(
                "📅 Введите дедлайн (ДД.MM.YYYY) или напишите **«без срока»**:",
                reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                parse_mode='Markdown',
            )
            return

        if step == 'deadline':
            deadline = None
            if not self._is_no_deadline(text):
                try:
                    deadline = _dt.strptime(text, '%d.%m.%Y').date()
                except ValueError:
                    try:
                        deadline = _dt.strptime(text, '%Y-%m-%d').date()
                    except ValueError:
                        await update.message.reply_text(
                            "❌ Неверный формат даты.\n\n"
                            "Примеры: **01.09.2026** или **2026-09-01** или **без срока**",
                            reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                            parse_mode='Markdown',
                        )
                        return

            title = data.get('title')
            try:
                target_amount = Decimal(data.get('target_amount', '0'))
            except (InvalidOperation, ValueError):
                target_amount = Decimal('0')

            if not title or target_amount <= 0:
                # сбрасываем state, чтобы пользователь не застрял в некорректном сценарии
                context.user_data.pop('goal_creation_step', None)
                context.user_data.pop('goal_creation_data', None)
                await update.message.reply_text(
                    "❌ Данные цели потерялись. Начните создание заново.",
                    reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                    parse_mode='Markdown',
                )
                return

            user = await sync_to_async(lambda: telegram_user.user)()
            service = GoalService(user)
            try:
                goal = await service.create_goal(
                    title=title,
                    target_amount=target_amount,
                    deadline=deadline,
                )
            except IntegrityError:
                # цель с таким названием уже есть
                context.user_data['goal_creation_step'] = 'title'
                context.user_data['goal_creation_data'] = {}
                await update.message.reply_text(
                    "❌ Цель с таким названием уже существует.\n\nВведите другое название:",
                    reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
                    parse_mode='Markdown',
                )
                return

            # очищаем state ДО попытки показать карточку (чтобы не застрять)
            context.user_data.pop('goal_creation_step', None)
            context.user_data.pop('goal_creation_data', None)

            from telegram_bot.handlers.goals_handler import GoalsHandler

            handler = GoalsHandler()
            try:
                await update.message.reply_text("✅ Цель создана. Вот её карточка:")
                await handler.handle_goal_view(update, context, telegram_user, goal.id)
            except Exception:
                # Цель создана, но UI мог упасть (Markdown/Telegram ошибки и т.п.).
                # Не маскируем это как "не получилось распознать ввод".
                await update.message.reply_text(
                    "✅ Цель создана, но не удалось показать карточку.\n"
                    "Откройте: **🎯 Цели → 📋 Мои цели**.",
                    parse_mode='Markdown',
                )
            return

        # неизвестный шаг -> сбрасываем
        context.user_data.pop('goal_creation_step', None)
        context.user_data.pop('goal_creation_data', None)
        await update.message.reply_text(
            "❌ Состояние создания цели сброшено. Попробуйте снова.",
            reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback="goals_menu"),
            parse_mode='Markdown',
        )

    async def _handle_goal_deposit_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
        message_text: str,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        try:
            amount = self._parse_money(message_text)
            if amount <= 0:
                raise ValueError("amount<=0")
            user = await sync_to_async(lambda: telegram_user.user)()
            service = GoalService(user)
            entry = await service.add_deposit(goal_id, amount)
            if not entry:
                await update.message.reply_text("❌ Цель не найдена.")
                return
            await update.message.reply_text(f"✅ Внесено {amount:,.0f} ₽")
            handler = GoalsHandler()
            await handler.handle_goal_view(update, context, telegram_user, goal_id)
        except Exception:
            await update.message.reply_text("❌ Неверная сумма. Пример: 5000 или 499.90")
        finally:
            context.user_data.pop('goal_deposit_goal_id', None)

    async def _handle_voice_goal_pending_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        message_text: str,
    ) -> bool:
        """Continue goal picker via text while VOICE_GOAL_PENDING is set."""
        from telegram_bot.services.command_executor import VOICE_GOAL_PENDING_KEY
        from telegram_bot.voice.goal_resolver import GoalResolver, ResolveStatus
        from telegram_bot.voice.intents import ParsedVoiceCommand

        pending = context.user_data.get(VOICE_GOAL_PENDING_KEY)
        if not pending:
            return False

        text = (message_text or '').strip()
        if not text:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Выберите цель кнопкой или напишите название.',
            )
            return True

        if text.lower() in {'отмена', 'cancel', 'стоп'}:
            context.user_data.pop(VOICE_GOAL_PENDING_KEY, None)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='❌ Голосовая команда отменена.',
            )
            return True

        command = pending.get('command')
        if not isinstance(command, ParsedVoiceCommand):
            context.user_data.pop(VOICE_GOAL_PENDING_KEY, None)
            return False

        user = await sync_to_async(lambda: telegram_user.user)()
        resolved = await sync_to_async(GoalResolver(user).resolve)(text)
        if resolved.status == ResolveStatus.MATCHED and resolved.match:
            context.user_data.pop(VOICE_GOAL_PENDING_KEY, None)
            command.goal = resolved.match
            command.goal_title = resolved.match.title
            await self._command_executor.execute_manage_goal(
                update,
                context,
                telegram_user,
                command,
            )
            return True

        command.goal_title = text
        context.user_data[VOICE_GOAL_PENDING_KEY] = {'command': command}
        await self._command_executor.prompt_goal_resolution(
            update,
            context,
            telegram_user,
            command,
        )
        return True

    async def _handle_goal_withdraw_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        goal_id: int,
        message_text: str,
    ) -> None:
        from telegram_bot.handlers.goals_handler import GoalsHandler

        try:
            amount = self._parse_money(message_text)
            if amount <= 0:
                raise ValueError("amount<=0")
            user = await sync_to_async(lambda: telegram_user.user)()
            service = GoalService(user)
            entry = await service.add_withdraw(goal_id, amount)
            if not entry:
                await update.message.reply_text("❌ Цель не найдена.")
                return
            await update.message.reply_text(f"✅ Снято {amount:,.0f} ₽")
            handler = GoalsHandler()
            await handler.handle_goal_view(update, context, telegram_user, goal_id)
        except Exception:
            await update.message.reply_text("❌ Неверная сумма. Пример: 5000 или 499.90")
        finally:
            context.user_data.pop('goal_withdraw_goal_id', None)
    
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
            message_text = context.user_data.pop(
                '_voice_text_override',
                None,
            )
            if message_text is None:
                message_text = update.message.text or ''
            message_text = message_text.strip()
            if not message_text:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text='❌ Пустое сообщение. Введите текст или отправьте голос ещё раз.',
                )
                return
            
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
                    message_text,
                )
                return

            # --- Цели: создание / пополнение / снятие ---
            goal_creation_step = context.user_data.get('goal_creation_step')
            if goal_creation_step:
                await self._handle_goal_creation_input(
                    update,
                    context,
                    telegram_user,
                    message_text,
                )
                return

            if context.user_data.get('goal_deposit_goal_id'):
                goal_id = context.user_data.get('goal_deposit_goal_id')
                await self._handle_goal_deposit_input(
                    update,
                    context,
                    telegram_user,
                    goal_id,
                    message_text,
                )
                return

            if context.user_data.get('goal_withdraw_goal_id'):
                goal_id = context.user_data.get('goal_withdraw_goal_id')
                await self._handle_goal_withdraw_input(
                    update,
                    context,
                    telegram_user,
                    goal_id,
                    message_text,
                )
                return
            
            # --- Обработка состояний редактирования (дата/комментарий) ---
            # Сначала проверим, не находится ли пользователь в режиме редактирования суммы транзакции
            if context.user_data.get('editing_transaction_amount'):
                transaction_id = context.user_data.get('editing_transaction_amount')
                text = message_text.strip().replace(' ', '').replace(',', '.')
                try:
                    new_amount = Decimal(text)
                    if new_amount <= 0:
                        raise ValueError("amount<=0")

                    user = await sync_to_async(lambda: telegram_user.user)()
                    transaction_service = TransactionService(user)
                    updated = await transaction_service.update_transaction_amount(
                        transaction_id,
                        new_amount,
                    )

                    if updated:
                        keyboard = ActionKeyboard.get_transaction_actions_keyboard(transaction_id)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"✅ Сумма транзакции обновлена на {abs(updated.amount):,.2f}₽",
                            reply_markup=keyboard,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text="❌ Транзакция не найдена или недоступна.",
                        )
                except Exception:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Неверный формат суммы. Пример: 5000 или 499.90",
                    )
                finally:
                    context.user_data.pop('editing_transaction_amount', None)
                return

            # Сначала проверим, не находится ли пользователь в режиме редактирования даты транзакции
            if context.user_data.get('editing_transaction_date'):
                transaction_id = context.user_data.get('editing_transaction_date')
                text = message_text.strip()
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
                comment_text = message_text.strip()
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
                    message_text,
                )
                return

            # Wizard flows take priority over stale awaiting_category state.
            if 'limit_creation' in context.user_data:
                await self._handle_limit_amount_input(
                    update,
                    context,
                    telegram_user,
                    message_text,
                )
                return

            if context.user_data.get('waiting_for_budget_amount'):
                await self._handle_budget_amount_input(
                    update,
                    context,
                    telegram_user,
                    message_text,
                )
                return

            if user_state.awaiting_category and user_state.current_amount:
                await self._handle_awaiting_category_input(
                    update,
                    context,
                    telegram_user,
                    message_text,
                    user_state,
                )
                return

            # Voice multi-turn dialog (after wizards / category picker)
            from telegram_bot.voice.dialog import (
                VoiceDialogManager,
                clear_dialog,
                get_dialog,
                is_dialog_expired,
            )

            dialog = get_dialog(context)
            if dialog:
                if is_dialog_expired(dialog):
                    clear_dialog(context)
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text='⏱ Диалог устарел. Отправьте команду заново.',
                    )
                    return
                await VoiceDialogManager().continue_dialog(
                    update,
                    context,
                    telegram_user,
                    message_text,
                )
                return

            from telegram_bot.services.command_executor import (
                VOICE_GOAL_PENDING_KEY,
                VOICE_PENDING_KEY,
            )

            if context.user_data.get(VOICE_PENDING_KEY):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        'Сначала подтвердите или отмените предыдущую '
                        'голосовую команду (✅ / ❌).'
                    ),
                )
                return

            if context.user_data.get(VOICE_GOAL_PENDING_KEY):
                handled = await self._handle_voice_goal_pending_text(
                    update,
                    context,
                    telegram_user,
                    message_text,
                )
                if handled:
                    return

            # Логируем входящее сообщение
            await self.log_message(
                telegram_user,
                'incoming',
                message_text,
            )
            
            # Парсим команду
            user = await sync_to_async(lambda: telegram_user.user)()
            parser = await sync_to_async(self.get_parser)(user)
            parsed_command = await sync_to_async(parser.parse)(message_text)
            
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
    
    async def _handle_awaiting_category_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        message_text: str,
        user_state,
    ) -> None:
        """Завершает amount_only flow: пользователь назвал категорию текстом/голосом."""
        user = await sync_to_async(lambda: telegram_user.user)()
        parser = await sync_to_async(self.get_parser)(user)
        transaction_type = user_state.last_transaction_type or 'expense'
        amount = user_state.current_amount
        raw_text = message_text.strip()

        parsed: dict = {'success': False}
        for candidate in voice_text_parse_candidates(raw_text):
            parsed = await sync_to_async(parser.parse)(candidate)
            if parsed.get('success'):
                break
        if parsed.get('success') and parsed.get('type') == 'amount_only':
            user_state.current_amount = parsed['amount']
            if parsed.get('transaction_type'):
                user_state.last_transaction_type = parsed['transaction_type']
                transaction_type = parsed['transaction_type']
            await user_state.asave()
            await self._command_executor.send_category_selection(
                update,
                context,
                telegram_user,
                user_state.current_amount,
                transaction_type,
                voice_transcript=message_text,
            )
            return

        lookup_name = raw_text
        resolved_category = None
        tx_amount = amount

        if parsed.get('success') and parsed.get('type') == 'amount_category':
            lookup_name = parsed.get('category_name') or raw_text
            if parsed.get('category'):
                resolved_category = parsed['category']
            if parsed.get('amount') is not None and parsed['amount'] != amount:
                tx_amount = parsed['amount']

        if not resolved_category:
            resolved_category = await sync_to_async(parser._find_category)(
                lookup_name,
                transaction_type,
            )
            if not resolved_category:
                resolved_category = await sync_to_async(parser._find_category)(
                    lookup_name,
                    'income' if transaction_type == 'expense' else 'expense',
                )

        if not resolved_category:
            picker_type = transaction_type
            if parsed.get('success') and parsed.get('type') == 'amount_category':
                picker_type = parsed.get('transaction_type') or transaction_type
            user_state.current_amount = tx_amount
            user_state.last_transaction_type = picker_type
            await user_state.asave()
            await self._command_executor.send_category_selection(
                update,
                context,
                telegram_user,
                tx_amount,
                picker_type,
                prefix_message=f"Категория '{lookup_name}' не найдена.",
                voice_transcript=message_text,
            )
            return

        from telegram_bot.services.command_executor import VOICE_CATEGORY_PENDING_KEY
        from telegram_bot.voice.intents import ParsedVoiceCommand, VoiceIntentType

        pending = context.user_data.get(VOICE_CATEGORY_PENDING_KEY)
        pending_command = pending.get('command') if pending else None
        if (
            isinstance(pending_command, ParsedVoiceCommand)
            and pending_command.intent == VoiceIntentType.SET_BUDGET
        ):
            user_state.current_amount = None
            user_state.awaiting_category = False
            user_state.last_transaction_type = 'expense'
            await user_state.asave()
            context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)

            if resolved_category.type != 'expense':
                await self._command_executor.send_error(
                    update,
                    context,
                    'Лимит можно задать только для категории расходов.',
                    voice_transcript=message_text,
                )
                return

            pending_command.category = resolved_category
            pending_command.category_name = resolved_category.name
            pending_command.transaction_type = 'expense'
            pending_command.amount = tx_amount
            await self._command_executor.execute_set_budget(
                update,
                context,
                telegram_user,
                pending_command,
            )
            return

        try:
            transaction = await TransactionService(user).create_transaction(
                amount=tx_amount,
                category=resolved_category,
                transaction_type=resolved_category.type,
            )
            user_state.current_amount = None
            user_state.awaiting_category = False
            user_state.last_transaction_type = resolved_category.type
            await user_state.asave()

            context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)

            await self._command_executor.send_transaction_created(
                update,
                context,
                transaction,
                voice_transcript=message_text,
            )
        except Exception as exc:
            logger.error('Awaiting category transaction error: %s', exc)
            await self._command_executor.send_error(
                update,
                context,
                f'Ошибка создания транзакции: {exc}',
                voice_transcript=message_text,
            )
    
    async def _handle_amount_category(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду с суммой и категорией"""
        await self._command_executor.execute_create_transaction(
            update,
            context,
            telegram_user,
            parsed_command,
        )
    
    async def _handle_amount_only(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict,
    ) -> None:
        """Обрабатывает команду только с суммой"""
        await self._command_executor.execute_create_transaction(
            update,
            context,
            telegram_user,
            parsed_command,
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
        await self._command_executor.send_category_selection(
            update,
            context,
            telegram_user,
            amount,
            transaction_type,
            prefix_message,
        )
    
    async def _send_transaction_created_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        transaction,
    ) -> None:
        """Отправляет сообщение о созданной транзакции"""
        await self._command_executor.send_transaction_created(
            update,
            context,
            transaction,
        )
    
    async def _send_error_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_text: str,
    ) -> None:
        """Отправляет сообщение об ошибке"""
        await self._command_executor.send_error(update, context, error_text)
    
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
            "🎤 Голосом (если включено):\n"
            "• «Запиши расход 300 рублей на продукты»\n\n"
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

            context_data = user_state.context_data or {}
            voice_create_after = bool(context_data.get('voice_create_after'))
            voice_intent = context_data.get('voice_intent') or ''
            pending_amount = user_state.current_amount

            # Сбрасываем состояние создания категории
            user_state.awaiting_category_creation = False
            user_state.context_data = {}
            await user_state.asave()

            logger.info(f"Категория создана успешно: {category.name} ({category.type})")

            if voice_create_after and pending_amount is not None:
                from telegram_bot.services.command_executor import (
                    VOICE_CATEGORY_PENDING_KEY,
                )
                from telegram_bot.voice.intents import (
                    ParsedVoiceCommand,
                    VoiceIntentType,
                )

                context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)
                user_state.current_amount = None
                user_state.awaiting_category = False
                user_state.last_transaction_type = category.type
                await user_state.asave()

                if voice_intent == VoiceIntentType.SET_BUDGET.value:
                    if category.type != 'expense':
                        await self._command_executor.send_error(
                            update,
                            context,
                            (
                                'Категория создана, но лимит можно задать '
                                'только для расходов.'
                            ),
                            voice_transcript=text,
                        )
                        return
                    command = ParsedVoiceCommand(
                        intent=VoiceIntentType.SET_BUDGET,
                        success=True,
                        confidence=1.0,
                        raw_transcript=text,
                        transaction_type='expense',
                        amount=pending_amount,
                        category_name=category.name,
                        category=category,
                        command_type='amount_category',
                    )
                    await self._command_executor.execute_set_budget(
                        update,
                        context,
                        telegram_user,
                        command,
                    )
                    return

                try:
                    transaction = await TransactionService(user).create_transaction(
                        amount=pending_amount,
                        category=category,
                        transaction_type=category.type,
                    )
                    await self._command_executor.send_transaction_created(
                        update,
                        context,
                        transaction,
                        voice_transcript=text,
                    )
                    return
                except Exception as exc:
                    logger.error('Voice create-after transaction error: %s', exc)
                    await self._command_executor.send_error(
                        update,
                        context,
                        f'Категория создана, но транзакция не записана: {exc}',
                        voice_transcript=text,
                    )
                    return

            # Отправляем подтверждение (обычный settings flow)
            type_name = "доходов" if normalized_type == "income" else "расходов"
            display_name = category.name
            message = (
                f"✅ **Категория создана!**\n\n"
                f"**{display_name}**\n"
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
        Разбирает ввод пользователя для категории.

        Возвращает:
            - name: текст БЕЗ первого эмодзи
            - icon: первое найденное эмодзи или дефолт 📁
        """
        raw_text = text.strip()

        def is_emoji(ch: str) -> bool:
            return (
                "\U0001F300" <= ch <= "\U0001FAFF"
                or "\u2600" <= ch <= "\u26FF"
                or "\u2700" <= ch <= "\u27BF"
            )

        icon = None
        name_chars = []

        for ch in raw_text:
            if icon is None and is_emoji(ch):
                # Нашли первый эмодзи - сохраняем как иконку
                icon = ch
                # И пропускаем его (не добавляем в name_chars)
                continue
            # Все остальные символы добавляем в имя
            name_chars.append(ch)

        # Если эмодзи не нашли — дефолтная иконка
        if icon is None:
            icon = "📁"
            name = raw_text  # Весь текст как имя
        else:
            name = "".join(name_chars).strip()  # Текст БЕЗ эмодзи
            # Если после удаления эмодзи осталась пустая строка, используем эмодзи как имя
            if not name:
                name = icon

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
            f"Теперь: {name}"
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