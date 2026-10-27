"""Остаток долга. Повторяющиеся операции и транзакции здесь не читаются."""

from datetime import date
from decimal import Decimal

from debts.models import Debt, DebtPayment


def add_payment(debt: Debt, amount: Decimal, paid_on: date) -> DebtPayment:
    """Уменьшает остаток. Если он стал нулём, долг закрывается."""
    if amount <= 0:
        raise ValueError('Платёж должен быть больше нуля.')
    if amount > debt.remaining:
        raise ValueError('Платёж больше остатка.')
    payment = DebtPayment.objects.create(debt=debt, amount=amount, paid_on=paid_on)
    debt.refresh_from_db()
    if debt.remaining <= 0:
        debt.is_open = False
        debt.save(update_fields=['is_open', 'updated_at'])
    return payment


def obligation_lines(user) -> list[str]:
    """Строки блока «Долги». Повторов здесь нет."""
    from transactions.currencies import base_for_user, symbol_of

    currency = base_for_user(user)

    def money(amount: Decimal) -> str:
        whole = int(Decimal(amount).quantize(Decimal('1')))
        grouped = f'{abs(whole):,}'.replace(',', ' ')
        return f'{grouped} {symbol_of(currency)}'

    lines = []
    debts = Debt.objects.filter(user=user, is_open=True).order_by('counterparty', 'id')
    for debt in debts:
        side = 'я должен' if debt.direction == Debt.OWE else 'мне должны'
        lines.append(f'{debt.counterparty} — {side}, осталось {money(debt.remaining)}')
    return lines
