"""Lightweight structured metrics for voice pipeline."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger('telegram_bot.voice.metrics')


@contextmanager
def timed_ms() -> Iterator[dict[str, float]]:
    """Yield a dict that receives ``ms`` when the context exits."""
    bucket: dict[str, float] = {}
    started = time.perf_counter()
    try:
        yield bucket
    finally:
        bucket['ms'] = round((time.perf_counter() - started) * 1000, 1)


def log_voice_event(event: str, **fields: Any) -> None:
    """Emit one structured voice metric line (JSON-ish key=value)."""
    parts = [f'event={event}']
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, str):
            safe = value.replace('"', "'")[:120]
            parts.append(f'{key}="{safe}"')
        else:
            parts.append(f'{key}={value}')
    logger.info('voice_metric %s', ' '.join(parts))
