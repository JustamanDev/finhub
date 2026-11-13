"""Сумма из короткого ответа: «170000», «170 000», «170000 донгов»."""

from decimal import Decimal, InvalidOperation

from telegram_bot.handlers.recurring_handler import parse_plain_amount
from telegram_bot.utils.currency_text import parse_leading_amount


def split_amount(text: str) -> tuple[Decimal, str | None] | None:
    """Положительная сумма и валюта, если она названа. Иначе None."""
    raw = (text or '').strip()
    parsed = parse_leading_amount(raw)
    if parsed and not (parsed.get('rest') or '').strip():
        try:
            amount = Decimal(str(parsed['amount']).replace(',', '.'))
        except InvalidOperation:
            amount = None
        if amount is not None and amount > 0:
            return amount.quantize(Decimal('0.01')), parsed.get('currency')
    plain = parse_plain_amount(raw)
    if plain is None:
        return None
    return plain, None
