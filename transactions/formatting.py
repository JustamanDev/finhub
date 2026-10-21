"""Отображение сумм: ввод в исходной валюте, итог в базовой."""

from decimal import Decimal

from transactions.currencies import RUB, symbol_of


def format_entry_amount(amount, currency: str | None) -> str:
    """Сумма так, как её ввёл пользователь."""
    if amount is None:
        return '—'
    value = Decimal(amount)
    return f'{value:,.0f}{symbol_of(currency or RUB)}'


def format_transaction_amount(transaction) -> str:
    """
    Строка для подтверждения.

    Совпадает валюта ввода и отчёта — только итог.
    Иначе исходная сумма, итог в базовой валюте и курс ЦБ на день записи.
    """
    base = getattr(transaction, 'report_currency', None) or RUB
    total = f'{abs(Decimal(transaction.amount)):,.0f}{symbol_of(base)}'
    currency = getattr(transaction, 'currency', None) or RUB
    original = getattr(transaction, 'original_amount', None)
    if currency == base or original is None:
        return total

    entered = f'{abs(Decimal(original)):,.0f}{symbol_of(currency)}'
    nominal = int(getattr(transaction, 'rate_nominal', None) or 1)
    rate = Decimal(getattr(transaction, 'exchange_rate', None) or 0)
    per_nominal = (rate * Decimal(nominal)).quantize(Decimal('0.0001'))
    rate_date = getattr(transaction, 'rate_date', None)
    date_label = rate_date.strftime('%d.%m.%Y') if rate_date else '—'
    nominal_label = f'{nominal:,}'.replace(',', ' ')
    return (
        f'{entered} → {total}\n'
        f'Курс ЦБ {date_label}: {per_nominal}{symbol_of(base)} '
        f'за {nominal_label}{symbol_of(currency)}'
    )
