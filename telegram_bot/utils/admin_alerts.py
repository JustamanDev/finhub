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


def _safe_getattr(obj, attr: str):
    try:
        return getattr(obj, attr, None)
    except Exception:
        return None


def summarize_update(update) -> str:
    """
    Create a short, stable update summary for alerts.
    """
    if update is None:
        return ""

    update_id = _safe_getattr(update, "update_id")
    effective_chat = _safe_getattr(update, "effective_chat")
    effective_user = _safe_getattr(update, "effective_user")

    chat_id = _safe_getattr(effective_chat, "id")
    chat_type = _safe_getattr(effective_chat, "type")
    user_id = _safe_getattr(effective_user, "id")
    username = _safe_getattr(effective_user, "username")

    message = _safe_getattr(update, "message")
    callback_query = _safe_getattr(update, "callback_query")

    text = _safe_getattr(message, "text")
    callback_data = _safe_getattr(callback_query, "data")

    parts = [
        f"update_id={update_id}",
        f"chat_id={chat_id}",
        f"chat_type={chat_type}",
        f"user_id={user_id}",
    ]
    if username:
        parts.append(f"username=@{username}")
    if text:
        parts.append(f"text={text!r}")
    if callback_data:
        parts.append(f"callback={callback_data!r}")
    return ", ".join(parts)


async def notify_admins_about_exception(
    bot,
    *,
    error: BaseException,
    where: str,
    update=None,
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

    update_summary = summarize_update(update)

    tb_fingerprint = ""
    try:
        tb_fingerprint = "".join(traceback.format_tb(error.__traceback__)[-6:])
    except Exception:
        tb_fingerprint = ""

    key = _dedupe_key(
        [
            where,
            error_type,
            error_text,
            tb_fingerprint,
            update_summary,
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
    if update_summary:
        message += f"\nUpdate: {update_summary}\n"
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

