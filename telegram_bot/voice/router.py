"""Маршрутизация распознанных голосовых intent-ов."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.services.command_executor import CommandExecutor
from telegram_bot.voice.dialog import (
    VoiceDialogManager,
    missing_slots_for_budget,
    missing_slots_for_create,
    missing_slots_for_goal,
)
from telegram_bot.voice.intents import (
    GOAL_ACTION_CREATE,
    GOAL_ACTION_DEPOSIT,
    GOAL_ACTION_WITHDRAW,
    ParsedVoiceCommand,
    VoiceIntentType,
)

logger = logging.getLogger(__name__)

STUB_MESSAGES = {
    VoiceIntentType.ASK_ADVISOR: (
        '🎤 Финансовый консультант в разработке.\n'
        'Твой вопрос сохранён — вернёмся к этому позже.'
    ),
}


class VoiceRouter:
    def __init__(self) -> None:
        self._executor = CommandExecutor()
        self._dialog = VoiceDialogManager()

    async def route(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        command: ParsedVoiceCommand,
    ) -> None:
        if command.intent == VoiceIntentType.CREATE_TRANSACTION:
            if command.should_reject():
                await self._executor.send_error(
                    update,
                    context,
                    command.error or 'Не понял команду. Попробуй ещё раз.',
                    voice_transcript=command.raw_transcript,
                )
                return

            missing = missing_slots_for_create(command)
            dialog_slots = [
                slot for slot in missing if slot in ('amount', 'transaction_type')
            ]
            if dialog_slots:
                await self._dialog.start_from_command(
                    update,
                    context,
                    telegram_user,
                    command,
                    missing,
                )
                return

            # Named category not resolved → disambiguate / create offer.
            if 'category' in missing:
                await self._executor.prompt_category_resolution(
                    update,
                    context,
                    telegram_user,
                    command,
                )
                return

            if command.needs_confirmation():
                await self._executor.prompt_voice_confirmation(
                    update,
                    context,
                    telegram_user,
                    command,
                )
                return

            await self._executor.execute_create_transaction(
                update,
                context,
                telegram_user,
                command.to_executor_dict(),
                voice_transcript=command.raw_transcript,
            )
            return

        if command.intent == VoiceIntentType.SET_BUDGET:
            if command.should_reject():
                await self._executor.send_error(
                    update,
                    context,
                    command.error or 'Не понял команду лимита. Попробуй ещё раз.',
                    voice_transcript=command.raw_transcript,
                )
                return

            # Budgets are expense-only.
            command.transaction_type = 'expense'
            missing = missing_slots_for_budget(command)

            # Incomplete: no amount, or no category hint at all → dialog.
            if command.amount is None or (
                not command.category and not command.category_name
            ):
                await self._dialog.start_from_command(
                    update,
                    context,
                    telegram_user,
                    command,
                    missing,
                )
                return

            # Named but unresolved → picker / create.
            if not command.category:
                await self._executor.prompt_category_resolution(
                    update,
                    context,
                    telegram_user,
                    command,
                )
                return

            await self._executor.execute_set_budget(
                update,
                context,
                telegram_user,
                command,
            )
            return

        if command.intent == VoiceIntentType.MANAGE_GOAL:
            if command.should_reject():
                await self._executor.send_error(
                    update,
                    context,
                    command.error or 'Не понял команду цели. Попробуй ещё раз.',
                    voice_transcript=command.raw_transcript,
                )
                return

            if not command.goal_action:
                await self._executor.send_error(
                    update,
                    context,
                    (
                        'Уточните действие: пополнить, снять или создать цель.\n'
                        'Пример: «пополни цель отпуск на 5000».'
                    ),
                    voice_transcript=command.raw_transcript,
                )
                return

            missing = missing_slots_for_goal(command)

            # Incomplete slots → dialog (amount / title).
            if command.amount is None or (
                command.goal_action == GOAL_ACTION_CREATE
                and not command.goal_title
            ) or (
                command.goal_action in {
                    GOAL_ACTION_DEPOSIT,
                    GOAL_ACTION_WITHDRAW,
                }
                and not command.goal
                and not command.goal_title
            ):
                await self._dialog.start_from_command(
                    update,
                    context,
                    telegram_user,
                    command,
                    missing,
                )
                return

            # Named but unresolved goal → picker.
            if (
                command.goal_action in {
                    GOAL_ACTION_DEPOSIT,
                    GOAL_ACTION_WITHDRAW,
                }
                and not command.goal
            ):
                await self._executor.prompt_goal_resolution(
                    update,
                    context,
                    telegram_user,
                    command,
                )
                return

            await self._executor.execute_manage_goal(
                update,
                context,
                telegram_user,
                command,
            )
            return

        if command.intent in STUB_MESSAGES:
            if command.intent == VoiceIntentType.ASK_ADVISOR:
                logger.info(
                    'Voice advisor stub query user=%s text=%r',
                    telegram_user.telegram_id,
                    command.raw_transcript,
                )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=STUB_MESSAGES[command.intent],
            )
            return

        await self._executor.send_error(
            update,
            context,
            command.error or 'Не понял команду.',
            voice_transcript=command.raw_transcript,
        )
