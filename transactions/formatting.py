"""Отображение сумм: ввод в исходной валюте, итог в рублях."""

from decimal import Decimal

from transactions.currencies import RUB, VND


def format_entry_amount(amount, currency: str | None) -> str:
    """Сумма так, как её ввёл пользователь."""
    if amount is None:
        return '—'
    value = Decimal(amount)
    if currency == VND:
        return f'{value:,.0f}₫'
    if currency == RUB:
        return f'{value:,.0f}₽'
    return f'{value:,.0f}'


def format_transaction_amount(transaction) -> str:
    """
    Строка для подтверждения.

    Рубли — только итог. Донги — исходная сумма, рублёвый итог и курс ЦБ.
    """
    rub = f'{abs(Decimal(transaction.amount)):,.0f}₽'
    currency = getattr(transaction, 'currency', None) or RUB
    original = getattr(transaction, 'original_amount', None)
    if currency != VND or original is None:
        return rub

    dong = f'{abs(Decimal(original)):,.0f}₫'
    nominal = int(getattr(transaction, 'rate_nominal', None) or 1)
    rate = Decimal(getattr(transaction, 'exchange_rate', None) or 0)
    per_nominal = (rate * Decimal(nominal)).quantize(Decimal('0.0001'))
    rate_date = getattr(transaction, 'rate_date', None)
    date_label = rate_date.strftime('%d.%m.%Y') if rate_date else '—'
    nominal_label = f'{nominal:,}'.replace(',', ' ')
    return (
        f'{dong} → {rub}\n'
        f'Курс ЦБ {date_label}: {per_nominal}₽ за {nominal_label}₫'
    )
