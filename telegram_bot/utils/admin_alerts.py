from __future__ import annotations

import hashlib
import os
import traceback
from typing import Iterable, Optional

from django.core.cache import cache


def _parse_admin_chat_ids(value: str) -> list[int]:
    raw = (value or "").strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    chat_ids: list[int] = []
    for part in parts:
        if not part:
            continue
        try:
            chat_ids.append(int(part))
        except ValueError:
            continue
    return chat_ids


def get_admin_chat_ids() -> list[int]:
    # Prefer plural, fallback to singular.
    return _parse_admin_chat_ids(
        os.getenv("TELEGRAM_ADMIN_CHAT_IDS")
        or os.getenv("TELEGRAM_ADMIN_CHAT_ID")
        or ""
    )


def _truncate(text: str, limit: int = 3500) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n…(truncated)…"


def _dedupe_key(parts: Iterable[str]) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", errors="ignore"))
        h.update(b"\n")
    return h.hexdigest()


async def notify_admins_about_exception(
    bot,
    *,
    error: BaseException,
    where: str,
    update_repr: Optional[str] = None,
    extra: Optional[str] = None,
    ttl_seconds: int = 300,
) -> None:
    """
    Send a short error alert to admin chat(s) in Telegram.

    Requires env var:
      - TELEGRAM_ADMIN_CHAT_IDS="123,456"
        or TELEGRAM_ADMIN_CHAT_ID="123"
    """
    admin_chat_ids = get_admin_chat_ids()
    if not admin_chat_ids:
        return

    error_type = type(error).__name__
    error_text = str(error)
    update_text = update_repr or ""

    key = _dedupe_key(
        [
            where,
            error_type,
            error_text,
            update_text,
        ]
    )
    cache_key = f"admin_alert:{key}"
    if cache.get(cache_key):
        return
    cache.set(cache_key, True, timeout=ttl_seconds)

    tb = "".join(
        traceback.format_exception(
            type(error),
            error,
            error.__traceback__,
        )
    )

    message = (
        "🚨 FinHub bot error\n\n"
        f"Where: {where}\n"
        f"Type: {error_type}\n"
        f"Error: {error_text}\n"
    )
    if update_repr:
        message += f"\nUpdate: {update_repr}\n"
    if extra:
        message += f"\nExtra: {extra}\n"

    message += "\nTraceback:\n" + tb
    message = _truncate(message)

    for chat_id in admin_chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=message,
            )
        except Exception:
            # Never fail the main flow due to alerting.
            continue

