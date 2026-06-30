"""Транскрибация аудио через OpenAI Whisper API."""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

from telegram_bot.voice.config import (
    openai_api_key,
    transcription_model,
    whisper_language,
    whisper_prompt,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_EXTENSIONS = {'.m4a', '.mp3', '.mp4', '.mpga', '.mpeg', '.wav', '.webm'}
TELEGRAM_VOICE_EXTENSIONS = {'.ogg', '.oga'}
VOICE_SAMPLE_RATE = 16_000
VOICE_BITRATE_KBPS = '64k'
VOICE_CHANNELS = 1
CHUNK_DURATION_MS = 10 * 60 * 1000
MAX_OPENAI_RETRIES = 3

ProgressCallback = Callable[[str], None]


class TranscriptionError(Exception):
    """Ошибка транскрибации или конфигурации."""


def get_client() -> OpenAI:
    api_key = openai_api_key()
    if not api_key:
        raise TranscriptionError(
            'Задайте OPENAI_API_KEY в .env для голосового ввода.',
        )
    return OpenAI(api_key=api_key)


def _notify(progress: ProgressCallback | None, message: str) -> None:
    if progress:
        progress(message)


def transcribe(
    path: Path,
    *,
    language: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> str:
    """Whisper API; файлы >25 MB сжимаются и при необходимости нарезаются."""
    suffix = path.suffix.lower()
    if (
        suffix not in SUPPORTED_EXTENSIONS
        and suffix not in TELEGRAM_VOICE_EXTENSIONS
    ):
        _notify(
            on_progress,
            f'Предупреждение: расширение {suffix} не в списке рекомендуемых.',
        )

    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        return _transcribe_large(path, language, model, prompt, on_progress)
    return _transcribe_one(path, language, model, prompt)


def _transcribe_one(
    path: Path,
    language: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
) -> str:
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise TranscriptionError(f'Файл {path} больше {MAX_FILE_SIZE_MB} MB.')

    model_name = model or transcription_model()
    lang = language if language is not None else whisper_language()
    hint = prompt if prompt is not None else whisper_prompt()
    client = get_client()
    use_text_format = model_name == 'whisper-1'

    last_error: Exception | None = None
    for attempt in range(1, MAX_OPENAI_RETRIES + 1):
        try:
            with path.open('rb') as file_handle:
                kwargs: dict = {
                    'model': model_name,
                    'file': file_handle,
                }
                if use_text_format:
                    kwargs['response_format'] = 'text'
                if lang:
                    kwargs['language'] = lang
                if hint:
                    kwargs['prompt'] = hint
                response = client.audio.transcriptions.create(**kwargs)
            return response if isinstance(response, str) else response.text
        except Exception as exc:
            last_error = exc
            logger.warning(
                'Whisper attempt %s/%s failed: %s',
                attempt,
                MAX_OPENAI_RETRIES,
                exc,
            )
            if attempt < MAX_OPENAI_RETRIES:
                time.sleep(attempt)

    raise TranscriptionError(
        f'Не удалось распознать аудио: {last_error}',
    ) from last_error


@contextmanager
def _prepare_audio_for_api(source: Path):
    size = source.stat().st_size
    if size <= MAX_FILE_SIZE_BYTES:
        yield [source]
        return

    tmpdir = tempfile.mkdtemp(prefix='whisper_')
    try:
        audio = AudioSegment.from_file(str(source))
        audio = audio.set_channels(VOICE_CHANNELS).set_frame_rate(
            VOICE_SAMPLE_RATE,
        )
        compressed = Path(tmpdir) / 'voice.mp3'
        audio.export(str(compressed), format='mp3', bitrate=VOICE_BITRATE_KBPS)

        if compressed.stat().st_size <= MAX_FILE_SIZE_BYTES:
            yield [compressed]
            return

        chunks: list[Path] = []
        for index, start in enumerate(range(0, len(audio), CHUNK_DURATION_MS)):
            chunk = audio[start : start + CHUNK_DURATION_MS]
            out = Path(tmpdir) / f'chunk_{index:03d}.mp3'
            chunk.export(str(out), format='mp3', bitrate=VOICE_BITRATE_KBPS)
            chunks.append(out)
        yield chunks
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _transcribe_large(
    path: Path,
    language: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> str:
    _notify(on_progress, 'Сжимаю аудио под лимит Whisper…')
    parts: list[str] = []
    with _prepare_audio_for_api(path) as paths:
        total = len(paths)
        if total > 1:
            _notify(on_progress, f'Нарезка на {total} частей…')
        for index, chunk_path in enumerate(paths):
            if total > 1:
                _notify(on_progress, f'Часть {index + 1}/{total}…')
            parts.append(_transcribe_one(chunk_path, language, model, prompt))
    return '\n\n'.join(part.strip() for part in parts if part.strip())


def convert_to_supported_format(
    source: Path,
    dest_dir: Path | None = None,
) -> Path:
    """Конвертирует Telegram OGG в mp3 при необходимости."""
    suffix = source.suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return source
    if suffix not in TELEGRAM_VOICE_EXTENSIONS:
        return source

    target_dir = dest_dir or source.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f'{source.stem}_converted.mp3'
    audio = AudioSegment.from_file(str(source))
    audio.export(str(target), format='mp3', bitrate=VOICE_BITRATE_KBPS)
    return target
