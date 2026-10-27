"""Ответ на напоминание пишет обычную транзакцию и сдвигает ритм."""

from datetime import date
from decimal import Decimal

from recurring.models import RecurringTemplate
from recurring.rhythm import roll_forward
from telegram_bot.services.budget_alerts import breaches_after_spend, snapshot_spent
from transactions.currencies import base_for_user
from transactions.exchange import apply_entered_amount
from transactions.models import Transaction


def record_occurrence(
    template: RecurringTemplate,
    amount: Decimal,
    today: date,
) -> Transaction:
    """Сумма из ответа становится транзакцией на сегодня. Долг не трогается."""
    if amount <= 0:
        raise ValueError('Сумма должна быть больше нуля.')
    signed = -abs(amount) if template.category.type == 'expense' else abs(amount)
    before = snapshot_spent(template.user, template.category, today)
    transaction = Transaction(
        user=template.user,
        category=template.category,
        amount=signed,
        date=today,
        description=template.name,
    )
    apply_entered_amount(
        transaction,
        signed,
        base_for_user(template.user),
        base=base_for_user(template.user),
    )
    transaction.save()
    transaction._budget_breaches = breaches_after_spend(
        template.user,
        template.category,
        today,
        before,
    )
    template.next_due = roll_forward(template.next_due, template.periodicity, today)
    template.reminded_for = None
    template.save(update_fields=['next_due', 'reminded_for', 'updated_at'])
    return transaction
