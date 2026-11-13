"""Остаток долга. Повторяющиеся операции и транзакции здесь не читаются."""

from datetime import date
from decimal import Decimal

from debts.models import Debt, DebtPayment


def add_payment(
    debt: Debt,
    amount: Decimal,
    paid_on: date,
    source_currency: str | None = None,
) -> DebtPayment:
    """Уменьшает остаток. Если он стал нулём, долг закрывается.

    amount — как ввели. Если валюта ввода не совпадает с валютой долга,
    в долг пишется эквивалент по курсу ЦБ, а исходная сумма остаётся на платеже.
    """
    from transactions.currencies import RUB, is_known
    from transactions.exchange import convert_magnitude

    if amount <= 0:
        raise ValueError('Платёж должен быть больше нуля.')
    debt_currency = debt.currency if is_known(debt.currency) else RUB
    source = source_currency if is_known(source_currency) else debt_currency
    input_amount = None
    input_currency = ''
    if source == debt_currency:
        native = Decimal(amount)
    else:
        native = convert_magnitude(amount, source, debt_currency)
        input_amount = Decimal(amount)
        input_currency = source
    if native > debt.remaining:
        raise ValueError('Платёж больше остатка.')
    payment = DebtPayment.objects.create(
        debt=debt,
        amount=native,
        paid_on=paid_on,
        input_amount=input_amount,
        input_currency=input_currency,
    )
    debt.refresh_from_db()
    if debt.remaining <= 0:
        debt.is_open = False
        debt.save(update_fields=['is_open', 'updated_at'])
    return payment


def obligation_lines(user) -> list[str]:
    """Строки блока «Долги». Остаток — в валюте долга, рядом эквивалент отчёта."""
    from transactions.booking import native_with_base
    from transactions.currencies import base_for_user

    base = base_for_user(user)
    lines = []
    debts = Debt.objects.filter(user=user, is_open=True).order_by('counterparty', 'id')
    for debt in debts:
        side = 'я должен' if debt.direction == Debt.OWE else 'мне должны'
        left = native_with_base(debt.remaining, debt.currency, base)
        lines.append(f'{debt.counterparty} — {side}, осталось {left}')
    return lines
