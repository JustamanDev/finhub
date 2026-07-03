"""Настройки голосового ввода из переменных окружения."""

from decouple import config


def voice_enabled() -> bool:
    return config('VOICE_ENABLED', default=False, cast=bool)


def openai_api_key() -> str:
    return config('OPENAI_API_KEY', default='').strip()


def openai_proxy_url() -> str | None:
    """Proxy for OpenAI API (Whisper + LLM). Falls back to TELEGRAM_PROXY_URL."""
    raw = config('OPENAI_PROXY_URL', default='').strip()
    if raw:
        return raw
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
