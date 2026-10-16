"""Суммы по журналу цели или конверта.

Покупка уменьшает остаток, но не «собранность» цели:
накоплено — это взносы минус снятия, без трат.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce

from goals.models import GoalLedgerEntry


@dataclass(frozen=True)
class LedgerTotals:
    deposited: Decimal
    withdrawn: Decimal
    spent: Decimal

    @property
    def committed(self) -> Decimal:
        """Сколько отложено к цели: взносы минус возвраты в свободные деньги."""
        return self.deposited - self.withdrawn

    @property
    def balance(self) -> Decimal:
        """Сколько сейчас лежит."""
        return self.committed - self.spent


def ledger_totals(goal_id: int) -> LedgerTotals:
    rows = (
        GoalLedgerEntry.objects.filter(goal_id=goal_id)
        .values('entry_type')
        .annotate(total=Coalesce(Sum('amount'), Decimal('0')))
    )
    deposited = Decimal('0')
    withdrawn = Decimal('0')
    spent = Decimal('0')
    for row in rows:
        amount = Decimal(row['total'] or 0)
        if row['entry_type'] == GoalLedgerEntry.DEPOSIT:
            deposited = amount
        elif row['entry_type'] == GoalLedgerEntry.WITHDRAW:
            withdrawn = abs(amount)
        elif row['entry_type'] == GoalLedgerEntry.SPEND:
            spent = abs(amount)
    return LedgerTotals(deposited=deposited, withdrawn=withdrawn, spent=spent)
