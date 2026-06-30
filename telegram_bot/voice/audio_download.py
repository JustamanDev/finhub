"""Скачивание и подготовка аудио из Telegram."""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from telegram import Audio, Document, Message, Voice
from telegram.ext import ExtBot

from telegram_bot.voice.transcription import (
    SUPPORTED_EXTENSIONS,
    TELEGRAM_VOICE_EXTENSIONS,
    convert_to_supported_format,
)

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = SUPPORTED_EXTENSIONS | TELEGRAM_VOICE_EXTENSIONS
LARGE_FILE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class IncomingAudio:
    file_id: str
    title: str
    suffix: str
    file_size: int | None = None


def _timestamp_title(prefix: str) -> str:
    return f'{prefix}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'


def extract_incoming_audio(message: Message) -> IncomingAudio | None:
    if message.voice:
        voice: Voice = message.voice
        return IncomingAudio(
            file_id=voice.file_id,
            title=_timestamp_title('voice'),
            suffix='.ogg',
            file_size=voice.file_size,
        )

    if message.audio:
        audio: Audio = message.audio
        file_name = audio.file_name or f'{_timestamp_title("audio")}.mp3'
        suffix = Path(file_name).suffix.lower() or '.mp3'
        return IncomingAudio(
            file_id=audio.file_id,
            title=Path(file_name).stem,
            suffix=suffix,
            file_size=audio.file_size,
        )

    if message.document:
        document: Document = message.document
        file_name = document.file_name or ''
        suffix = Path(file_name).suffix.lower()
        if suffix not in AUDIO_EXTENSIONS:
            return None
        return IncomingAudio(
            file_id=document.file_id,
            title=Path(file_name).stem or _timestamp_title('document'),
            suffix=suffix,
            file_size=document.file_size,
        )

    return None


def cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            try:
                path.unlink()
            except OSError:
                logger.debug('Could not delete temp file %s', path)


async def resolve_audio_file(
    bot: ExtBot,
    incoming: IncomingAudio,
) -> tuple[Path, list[Path]]:
    """Скачивает аудио во временную папку и при необходимости конвертирует."""
    if incoming.file_size and incoming.file_size > LARGE_FILE_BYTES:
        raise ValueError(
            'Файл слишком большой для стандартного Bot API (лимит 20 MB).',
        )

    tg_file = await bot.get_file(incoming.file_id)
    cleanup: list[Path] = []
    temp_dir = Path(tempfile.mkdtemp(prefix='finhub_voice_'))
    cleanup.append(temp_dir)

    source = temp_dir / f'input{incoming.suffix}'
    await tg_file.download_to_drive(custom_path=str(source))

    needs_convert = (
        incoming.suffix in TELEGRAM_VOICE_EXTENSIONS
        or source.suffix.lower() not in SUPPORTED_EXTENSIONS
    )
    if needs_convert:
        converted = convert_to_supported_format(source, temp_dir)
        return converted, cleanup

    return source, cleanup
