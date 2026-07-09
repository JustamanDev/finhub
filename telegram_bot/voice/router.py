"""Маршрутизация распознанных голосовых intent-ов."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.services.command_executor import CommandExecutor
from telegram_bot.voice.intents import ParsedVoiceCommand, VoiceIntentType

logger = logging.getLogger(__name__)

STUB_MESSAGES = {
    VoiceIntentType.SET_BUDGET: (
        '🎤 Голосовое управление бюджетами скоро будет доступно.\n'
        'Пока используй меню «Бюджеты» или настройки категории.'
    ),
    VoiceIntentType.MANAGE_GOAL: (
        '🎤 Голосовое управление целями скоро будет доступно.\n'
        'Пока используй раздел «Цели» в меню.'
    ),
    VoiceIntentType.ASK_ADVISOR: (
        '🎤 Финансовый консультант в разработке.\n'
        'Твой вопрос сохранён — вернёмся к этому позже.'
    ),
}


class VoiceRouter:
    def __init__(self) -> None:
        self._executor = CommandExecutor()

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

            # Named category not resolved → disambiguate / create offer (no binary confirm).
            if (
                command.command_type == 'amount_category'
                and command.category_name
                and not command.category
            ):
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
