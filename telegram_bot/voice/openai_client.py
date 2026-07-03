"""OpenAI client with optional HTTP/SOCKS proxy for blocked regions."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from openai import OpenAI

from telegram_bot.voice.config import openai_api_key, openai_proxy_url

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=20.0)


def get_openai_client() -> OpenAI:
    api_key = openai_api_key()
    if not api_key:
        raise ValueError('OPENAI_API_KEY is not set')

    proxy = openai_proxy_url()
    if not proxy:
        logger.warning(
            'OPENAI_PROXY_URL is not set — OpenAI requests go direct from VPS',
        )
    http_client = httpx.Client(
        proxy=proxy,
        timeout=DEFAULT_TIMEOUT,
    )
    if proxy:
        logger.info('OpenAI proxy is enabled: %s', _mask_proxy_url(proxy))

    return OpenAI(api_key=api_key, http_client=http_client)


def format_openai_error(exc: Exception) -> str:
    """User-facing hint for common OpenAI API failures."""
    message = str(exc)
    if 'unsupported_country_region_territory' in message:
        return (
            'OpenAI недоступен из текущего региона VPS. '
            'Задайте OPENAI_PROXY_URL с выходом в поддерживаемой стране '
            '(EU/US). TELEGRAM_PROXY_URL для OpenAI не подходит, если proxy '
            'тоже в заблокированном регионе.'
        )
    return message


def _mask_proxy_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or '?'
    port = parsed.port or ''
    port_suffix = f':{port}' if port else ''
    user = parsed.username or ''
    auth = f'{user}:***@' if user else ''
    return f'{parsed.scheme}://{auth}{host}{port_suffix}'
