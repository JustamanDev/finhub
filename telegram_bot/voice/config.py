"""Настройки голосового ввода из переменных окружения."""

import os

from decouple import config


def voice_enabled() -> bool:
    return config('VOICE_ENABLED', default=False, cast=bool)


def openai_api_key() -> str:
    return config('OPENAI_API_KEY', default='').strip()


def openai_proxy_url() -> str | None:
    """Proxy for OpenAI API (Whisper + LLM). Falls back to TELEGRAM_PROXY_URL."""
    # os.environ first: надёжнее в Docker, чем только decouple/.env в образе
    raw = os.getenv('OPENAI_PROXY_URL', '').strip()
    if not raw:
        raw = config('OPENAI_PROXY_URL', default='').strip()
    if raw:
        return raw
    raw = os.getenv('TELEGRAM_PROXY_URL', '').strip()
    if not raw:
        raw = config('TELEGRAM_PROXY_URL', default='').strip()
    return raw or None


def transcription_model() -> str:
    return config('TRANSCRIPTION_MODEL', default='whisper-1').strip()


def voice_llm_model() -> str:
    return config('VOICE_LLM_MODEL', default='gpt-4o-mini').strip()


def whisper_prompt() -> str:
    return config('WHISPER_PROMPT', default='').strip()


def whisper_language() -> str | None:
    raw = config('WHISPER_LANGUAGE', default='').strip()
    return raw or None
