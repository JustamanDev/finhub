"""Сумма в валюте записи и в валюте отчёта. Курс тот же, что у операций."""

from dataclasses import dataclass
from decimal import Decimal

from transactions.currencies import RUB, format_money, is_known
from transactions.exchange import MONEY, convert_factor, convert_magnitude
from transactions.exchange import ExchangeRateUnavailable


@dataclass(frozen=True)
class Booked:
    native: Decimal
    report: Decimal


def book_positive(
    amount: Decimal,
    source: str,
    native_currency: str,
    report_currency: str,
) -> Booked:
    """Положительная сумма: из валюты ввода в валюту записи и в валюту отчёта."""
    amount = abs(Decimal(amount))
    source = source if is_known(source) else RUB
    native_currency = native_currency if is_known(native_currency) else RUB
    report_currency = report_currency if is_known(report_currency) else RUB
    native = convert_magnitude(amount, source, native_currency)
    if native_currency == report_currency:
        report = native
    elif source == report_currency:
        report = amount.quantize(MONEY)
    else:
        report = convert_magnitude(amount, source, report_currency)
    return Booked(native=native, report=report)


def convert_signed(amount: Decimal, source: str, target: str) -> Decimal:
    """Сумма со знаком. Одинаковые валюты не ходят в ЦБ."""
    amount = Decimal(amount)
    source = source if is_known(source) else RUB
    target = target if is_known(target) else RUB
    if source == target:
        return amount.quantize(MONEY)
    factor = convert_factor(source, target)
    return (amount * factor).quantize(MONEY)


def native_with_base(amount: Decimal, native: str, base: str) -> str:
    """Своя валюта, а если отчёт в другой — эквивалент в скобках."""
    text = format_money(amount, native)
    if not native or native == base or Decimal(amount) == 0:
        return text
    try:
        converted = convert_magnitude(abs(Decimal(amount)), native, base)
    except ExchangeRateUnavailable:
        return text
    return f'{text} (≈ {format_money(converted, base)})'
