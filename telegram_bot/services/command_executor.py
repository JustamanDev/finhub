"""Общая логика создания транзакций (текст + голос)."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from telegram_bot.keyboards.actions import ActionKeyboard
from telegram_bot.keyboards.categories import CategoryKeyboard
from telegram_bot.services.transaction_service import TransactionService
from telegram_bot.voice.intents import ParsedVoiceCommand
from categories.models import Category

logger = logging.getLogger(__name__)

VOICE_PENDING_KEY = 'voice_pending'
VOICE_CATEGORY_PENDING_KEY = 'voice_category_pending'


class CommandExecutor:
    async def execute_create_transaction(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict[str, Any],
        *,
        voice_transcript: str | None = None,
    ) -> None:
        command_type = parsed_command.get('type')
        if command_type == 'amount_category':
            await self._handle_amount_category(
                update,
                context,
                telegram_user,
                parsed_command,
                voice_transcript=voice_transcript,
            )
        elif command_type == 'amount_only':
            await self._handle_amount_only(
                update,
                context,
                telegram_user,
                parsed_command,
                voice_transcript=voice_transcript,
            )
        else:
            await self.send_error(
                update,
                context,
                'Неподдерживаемый тип команды.',
                voice_transcript=voice_transcript,
            )

    async def execute_from_voice_pending(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        pending = context.user_data.pop(VOICE_PENDING_KEY, None)
        if not pending:
            await update.callback_query.answer('Нет данных для подтверждения.')
            return

        command: ParsedVoiceCommand = pending['command']
        await self.execute_create_transaction(
            update,
            context,
            telegram_user,
            command.to_executor_dict(),
            voice_transcript=command.raw_transcript,
        )

    async def prompt_voice_confirmation(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        command: ParsedVoiceCommand,
    ) -> None:
        if context.user_data.get(VOICE_PENDING_KEY):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    'Сначала подтвердите или отмените предыдущую '
                    'голосовую команду (✅ / ❌).'
                ),
            )
            return

        context.user_data[VOICE_PENDING_KEY] = {
            'command': command,
        }

        tx_type = 'расход' if command.transaction_type == 'expense' else 'доход'
        category_label = command.category_name or '—'
        if command.category:
            category_label = f'{command.category.icon} {command.category.name}'

        lines = [
            f'🎤 Распознано: «{command.raw_transcript}»',
            '',
            f'Записать {tx_type} {command.amount:,.0f}₽ → {category_label}?',
        ]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    '✅ Да',
                    callback_data='voice_confirm_yes',
                ),
                InlineKeyboardButton(
                    '❌ Отмена',
                    callback_data='voice_cancel',
                ),
            ],
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(lines),
            reply_markup=keyboard,
        )

    async def prompt_category_resolution(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        command: ParsedVoiceCommand,
    ) -> None:
        """Ask user to pick / create category when voice name did not auto-match."""
        from telegram_bot.voice.category_resolver import (
            CategoryResolver,
            ResolveStatus,
        )

        user = await sync_to_async(lambda: telegram_user.user)()
        transaction_type = command.transaction_type or 'expense'
        query_name = command.category_name or ''

        resolved = await sync_to_async(CategoryResolver(user).resolve)(
            query_name,
            transaction_type,
        )

        context.user_data[VOICE_CATEGORY_PENDING_KEY] = {
            'command': command,
        }
        # Keep amount ready for create-category / full-list flows.
        from telegram_bot.handlers.base import BaseHandler

        base = BaseHandler()
        user_state = await base.get_user_state(telegram_user)
        user_state.current_amount = command.amount
        user_state.awaiting_category = True
        user_state.last_transaction_type = transaction_type
        await user_state.asave()

        tx_type = 'расход' if transaction_type == 'expense' else 'доход'
        lines = [
            f'🎤 Распознано: «{command.raw_transcript}»',
            '',
        ]
        if resolved.status == ResolveStatus.AMBIGUOUS:
            lines.append(
                f'Несколько похожих категорий для {tx_type} '
                f'{command.amount:,.0f}₽ («{query_name}»). Выбери:',
            )
        else:
            lines.append(
                f"Категория «{query_name}» не найдена для {tx_type} "
                f'{command.amount:,.0f}₽.',
            )

        rows: list[list[InlineKeyboardButton]] = []
        for candidate in resolved.candidates:
            cat = candidate.category
            rows.append([
                InlineKeyboardButton(
                    text=f'{cat.icon} {cat.name}',
                    callback_data=f'voice_cat_pick_{cat.id}',
                ),
            ])
        rows.append([
            InlineKeyboardButton(
                text='📂 Все категории',
                callback_data='voice_cat_all',
            ),
        ])
        create_label = (
            f'➕ Создать «{query_name}»'
            if query_name
            else '➕ Создать категорию'
        )
        rows.append([
            InlineKeyboardButton(
                text=create_label[:64],
                callback_data='voice_cat_create',
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                text='❌ Отмена',
                callback_data='voice_cancel',
            ),
        ])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(lines),
            reply_markup=InlineKeyboardMarkup(rows),
        )

    async def apply_voice_category_pick(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        category_id: int,
    ) -> None:
        pending = context.user_data.pop(VOICE_CATEGORY_PENDING_KEY, None)
        if not pending:
            await update.callback_query.answer('Нет данных для выбора категории.')
            return

        command: ParsedVoiceCommand = pending['command']
        user = await sync_to_async(lambda: telegram_user.user)()
        try:
            category = await Category.objects.aget(id=category_id, user=user)
        except Category.DoesNotExist:
            await update.callback_query.answer('Категория не найдена')
            return

        command.category = category
        command.category_name = category.name
        command.transaction_type = category.type
        command.command_type = 'amount_category'

        from telegram_bot.handlers.base import BaseHandler

        base = BaseHandler()
        user_state = await base.get_user_state(telegram_user)
        user_state.awaiting_category = False
        user_state.current_amount = None
        await user_state.asave()

        await self.execute_create_transaction(
            update,
            context,
            telegram_user,
            command.to_executor_dict(),
            voice_transcript=command.raw_transcript,
        )

    async def show_voice_all_categories(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        pending = context.user_data.get(VOICE_CATEGORY_PENDING_KEY)
        if not pending:
            await update.callback_query.answer('Нет данных.')
            return
        command: ParsedVoiceCommand = pending['command']
        await self.send_category_selection(
            update,
            context,
            telegram_user,
            command.amount,
            command.transaction_type or 'expense',
            voice_transcript=command.raw_transcript,
        )

    async def start_voice_category_create(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
    ) -> None:
        pending = context.user_data.get(VOICE_CATEGORY_PENDING_KEY)
        if not pending:
            await update.callback_query.answer('Нет данных.')
            return

        command: ParsedVoiceCommand = pending['command']
        transaction_type = command.transaction_type or 'expense'
        suggested = (command.category_name or '').strip()

        from telegram_bot.handlers.base import BaseHandler

        base = BaseHandler()
        user_state = await base.get_user_state(telegram_user)
        user_state.awaiting_category_creation = True
        user_state.awaiting_category = True
        user_state.current_amount = command.amount
        user_state.last_transaction_type = transaction_type
        user_state.context_data = {
            'category_type': transaction_type,
            'voice_create_after': True,
            'suggested_name': suggested,
        }
        await user_state.asave()

        hint = (
            f'Отправьте название (можно с эмодзи).\n'
            f'Подсказка: «{suggested}»'
            if suggested
            else 'Отправьте название новой категории (можно с эмодзи).'
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f'➕ Создание категории для {command.amount:,.0f}₽\n\n'
                f'{hint}'
            ),
        )

    async def _handle_amount_category(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict[str, Any],
        *,
        voice_transcript: str | None = None,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        transaction_service = TransactionService(user)

        if parsed_command.get('category'):
            try:
                transaction = await transaction_service.create_transaction(
                    amount=parsed_command['amount'],
                    category=parsed_command['category'],
                    transaction_type=parsed_command['transaction_type'],
                    description=parsed_command.get('description') or '',
                )
                from telegram_bot.handlers.base import BaseHandler

                base = BaseHandler()
                user_state = await base.get_user_state(telegram_user)
                user_state.last_transaction_type = parsed_command['transaction_type']
                await user_state.asave()

                await self.send_transaction_created(
                    update,
                    context,
                    transaction,
                    voice_transcript=voice_transcript,
                )
            except Exception as exc:
                logger.error('Transaction create error: %s', exc)
                await self.send_error(
                    update,
                    context,
                    f'Ошибка создания транзакции: {exc}',
                    voice_transcript=voice_transcript,
                )
        else:
            # Text path / confirm path: fall back to full keyboard.
            # Voice unresolved names go through prompt_category_resolution in router.
            await self.send_category_selection(
                update,
                context,
                telegram_user,
                parsed_command['amount'],
                parsed_command['transaction_type'],
                prefix_message=(
                    f"Категория '{parsed_command['category_name']}' не найдена."
                ),
                voice_transcript=voice_transcript,
            )

    async def _handle_amount_only(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        parsed_command: dict[str, Any],
        *,
        voice_transcript: str | None = None,
    ) -> None:
        from telegram_bot.handlers.base import BaseHandler

        base = BaseHandler()
        user_state = await base.get_user_state(telegram_user)
        transaction_type = (
            parsed_command.get('transaction_type')
            or user_state.last_transaction_type
            or 'expense'
        )
        user_state.current_amount = parsed_command['amount']
        user_state.awaiting_category = True
        user_state.last_transaction_type = transaction_type
        await user_state.asave()

        await self.send_category_selection(
            update,
            context,
            telegram_user,
            parsed_command['amount'],
            transaction_type,
            voice_transcript=voice_transcript,
        )

    async def send_category_selection(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        amount,
        transaction_type: str,
        prefix_message: str = '',
        *,
        voice_transcript: str | None = None,
    ) -> None:
        keyboard_generator = CategoryKeyboard(telegram_user)
        keyboard = await keyboard_generator.get_frequent_categories_keyboard(
            transaction_type,
        )

        transaction_emoji = '💸' if transaction_type == 'expense' else '💰'
        type_name = 'расход' if transaction_type == 'expense' else 'доход'

        parts: list[str] = []
        if voice_transcript:
            parts.append(f'🎤 Распознано: «{voice_transcript}»')
        if prefix_message:
            parts.append(prefix_message)
        parts.append(
            f'{transaction_emoji} {amount:,.0f}₽ - выбери категорию ({type_name}):',
        )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(parts),
            reply_markup=keyboard,
        )

    async def send_transaction_created(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        transaction,
        *,
        voice_transcript: str | None = None,
    ) -> None:
        transaction_emoji = (
            '💸' if transaction.category.type == 'expense' else '💰'
        )
        lines = []
        if voice_transcript:
            lines.append(f'🎤 Распознано: «{voice_transcript}»')
        lines.append(
            f'✅ {abs(transaction.amount):,.0f}₽ → '
            f'{transaction.category.icon} {transaction.category.name}',
        )
        lines.append(f'Добавлено {transaction.date.strftime("%d.%m.%Y")}')

        keyboard = ActionKeyboard.get_transaction_actions_keyboard(transaction.id)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(lines),
            reply_markup=keyboard,
        )

    async def send_error(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        error_text: str,
        *,
        voice_transcript: str | None = None,
    ) -> None:
        lines = []
        if voice_transcript:
            lines.append(f'🎤 Распознано: «{voice_transcript}»')
        lines.append(f'❌ {error_text}')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(lines),
        )
