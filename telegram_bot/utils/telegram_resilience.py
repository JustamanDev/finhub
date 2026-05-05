from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

from telegram.error import NetworkError, TimedOut

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_telegram_call(
    call_factory: Callable[[], Awaitable[T]],
    *,
    operation_name: str,
    retries: int = 3,
    initial_delay_seconds: float = 0.8,
    backoff_multiplier: float = 2.0,
) -> T:
    """
    Retry Telegram API calls that fail with transient network errors.
    """
    attempt = 0
    delay = initial_delay_seconds
    last_error: Exception | None = None

    while attempt < retries:
        attempt += 1
        try:
            return await call_factory()
        except (TimedOut, NetworkError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            logger.warning(
                "Retrying Telegram operation '%s' after %s (attempt %s/%s)",
                operation_name,
                type(exc).__name__,
                attempt,
                retries,
            )
            await asyncio.sleep(delay)
            delay *= backoff_multiplier

    assert last_error is not None
    raise last_error
