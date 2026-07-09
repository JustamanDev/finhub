from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

from telegram import CallbackQuery, Update
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import ContextTypes

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


def is_message_not_modified_error(error: Exception) -> bool:
    return isinstance(error, BadRequest) and "Message is not modified" in str(error)


def get_callback_query(update: Update | CallbackQuery) -> CallbackQuery | None:
    if hasattr(update, "callback_query") and update.callback_query is not None:
        return update.callback_query
    if hasattr(update, "edit_message_text"):
        return update  # type: ignore[return-value]
    return None


async def _safe_answer_callback(query: CallbackQuery) -> None:
    try:
        await query.answer()
    except BadRequest:
        pass


async def safe_edit_message_text(
    query: CallbackQuery,
    *,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
    **kwargs,
) -> bool:
    """
    Edit callback message; ignore Telegram 'Message is not modified'.

    Returns True if the message was edited, False if content was unchanged.
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs,
        )
        return True
    except BadRequest as exc:
        if is_message_not_modified_error(exc):
            logger.debug(
                "Message is not modified for callback '%s' - ignoring",
                query.data,
            )
            await _safe_answer_callback(query)
            return False
        raise


async def send_or_edit_message(
    update: Update | CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
) -> bool:
    """
    Edit callback message or send a new one for non-callback updates.

    Returns True if message was sent/edited, False if edit skipped as unchanged.
    """
    query = get_callback_query(update)
    if query is not None:
        return await safe_edit_message_text(
            query,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    return True
