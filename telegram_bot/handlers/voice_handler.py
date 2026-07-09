"""Обработчик голосовых сообщений Telegram."""

from __future__ import annotations

import asyncio
import logging

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.handlers.base import BaseHandler
from telegram_bot.handlers.text_handler import TextHandler
from telegram_bot.services.command_executor import VOICE_PENDING_KEY
from telegram_bot.voice.audio_download import (
    cleanup_paths,
    extract_incoming_audio,
    resolve_audio_file,
)
from telegram_bot.voice.config import voice_enabled
from telegram_bot.voice.interpreter import VoiceInterpreter
from telegram_bot.voice.intents import ParsedVoiceCommand
from telegram_bot.voice.router import VoiceRouter
from telegram_bot.voice.transcription import TranscriptionError, transcribe

logger = logging.getLogger(__name__)


def _is_interactive_state(context: ContextTypes.DEFAULT_TYPE) -> bool:
    interactive_keys = (
        'renaming_category_id',
        'goal_creation_step',
        'goal_deposit_goal_id',
        'goal_withdraw_goal_id',
        'editing_transaction_amount',
        'editing_transaction_date',
        'editing_transaction_comment',
        'limit_creation',
        'waiting_for_budget_amount',
    )
    return any(context.user_data.get(key) for key in interactive_keys)


class VoiceHandler(BaseHandler):
    def __init__(self) -> None:
        super().__init__()
        self._router = VoiceRouter()
        self._text_handler = TextHandler()

    async def handle_voice_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not voice_enabled():
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    'Голосовой ввод отключён. '
                    'Включите VOICE_ENABLED в настройках или введите текстом.'
                ),
            )
            return

        if not update.message:
            return

        incoming = extract_incoming_audio(update.message)
        if not incoming:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Отправьте голосовое сообщение или аудиофайл.',
            )
            return

        telegram_user = await self.get_or_create_telegram_user(
            update.effective_user,
        )

        status_message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='🎤 Распознаю…',
        )

        cleanup: list = []
        try:
            audio_path, cleanup = await resolve_audio_file(
                context.bot,
                incoming,
            )
            transcript = await asyncio.to_thread(transcribe, audio_path)

            await status_message.edit_text(f'🎤 Распознано: «{transcript.strip()}»')

            if context.user_data.get(VOICE_PENDING_KEY):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        'Есть неподтверждённая голосовая команда. '
                        'Нажмите ✅ Да или ❌ Отмена в сообщении выше.'
                    ),
                )
                return

            user_state = await self.get_user_state(telegram_user)
            if user_state.awaiting_category or user_state.awaiting_category_creation:
                context.user_data['_voice_text_override'] = transcript.strip()
                await self._text_handler.handle_text_message(update, context)
                return

            if _is_interactive_state(context):
                context.user_data['_voice_text_override'] = transcript.strip()
                await self._text_handler.handle_text_message(update, context)
                return

            user = await sync_to_async(lambda: telegram_user.user)()

            def _interpret() -> ParsedVoiceCommand:
                return VoiceInterpreter(user).interpret(transcript.strip())

            command = await sync_to_async(_interpret)()
            await self._router.route(
                update,
                context,
                telegram_user,
                command,
            )
        except TranscriptionError as exc:
            logger.warning('Voice transcription failed: %s', exc)
            await status_message.edit_text(
                f'❌ Не удалось распознать аудио.\n{exc}',
            )
        except ValueError as exc:
            await status_message.edit_text(f'❌ {exc}')
        except Exception as exc:
            logger.error('Voice handler error: %s', exc, exc_info=True)
            await self.handle_error(update, context, exc)
            try:
                await status_message.edit_text(
                    '❌ Ошибка обработки голосового сообщения.',
                )
            except Exception:
                pass
        finally:
            cleanup_paths(cleanup)
