"""Утреннее напоминание о повторе. Долги этим циклом не занимается."""

import logging
from decimal import Decimal

from asgiref.sync import sync_to_async

from recurring.models import RecurringTemplate
from recurring.rhythm import due_templates, expectation_phrase, format_due, mark_reminded
from telegram_bot.models import TelegramUser, UserState
from telegram_bot.services.weekly_digest import vietnam_today
from transactions.currencies import base_for_user, symbol_of

logger = logging.getLogger(__name__)

PENDING_RECURRING_KEY = 'pending_recurring_id'


def _money(amount: Decimal, currency: str) -> str:
    whole = int(Decimal(amount).quantize(Decimal('1')))
    grouped = f'{abs(whole):,}'.replace(',', ' ')
    return f'{grouped} {symbol_of(currency)}'


def _reminder_text(template: RecurringTemplate) -> str:
    currency = base_for_user(template.user)
    hint = expectation_phrase(template, lambda amount: _money(amount, currency))
    return (
        f'🔁 {template.name}\n'
        f'{format_due(template.next_due)}, {hint}.\n'
        'Ответьте суммой — запишу обычную операцию.'
    )


def _arm(telegram_user: TelegramUser, template: RecurringTemplate) -> str:
    state, _created = UserState.objects.get_or_create(telegram_user=telegram_user)
    data = dict(state.context_data or {})
    data[PENDING_RECURRING_KEY] = template.id
    state.context_data = data
    state.save(update_fields=['context_data', 'updated_at'])
    mark_reminded(template)
    return _reminder_text(template)


async def deliver_due_reminders(bot) -> int:
    """Одно напоминание на шаблон, пока дата следующего раза не сдвинется."""
    today = vietnam_today()
    users = await sync_to_async(list)(
        TelegramUser.objects.select_related('user').all(),
    )
    sent = 0
    for telegram_user in users:
        templates = await sync_to_async(list)(due_templates(telegram_user.user, today))
        if not templates:
            continue
        template = templates[0]
        text = await sync_to_async(_arm)(telegram_user, template)
        try:
            await bot.send_message(chat_id=telegram_user.telegram_id, text=text)
        except Exception:
            logger.exception(
                'Не удалось напомнить про повтор user=%s template=%s',
                telegram_user.pk,
                template.pk,
            )
            await sync_to_async(_clear_reminded)(template.id, telegram_user.id)
            continue
        sent += 1
    return sent


def _clear_reminded(template_id: int, telegram_user_id: int) -> None:
    RecurringTemplate.objects.filter(pk=template_id).update(reminded_for=None)
    state = UserState.objects.filter(telegram_user_id=telegram_user_id).first()
    if state is not None:
        clear_pending(state)


async def recurring_reminder_loop(bot) -> None:
    """Тот же час, что у недельной сводки: 09:00 по Вьетнаму."""
    import asyncio

    from telegram_bot.services.weekly_digest import seconds_until_next_send

    await asyncio.sleep(25)
    while True:
        try:
            sent = await deliver_due_reminders(bot)
            if sent:
                logger.info('Напоминаний о повторах: %s', sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Проверка повторов упала')
        await asyncio.sleep(seconds_until_next_send())


def pending_template_id(state: UserState) -> int | None:
    raw = (state.context_data or {}).get(PENDING_RECURRING_KEY)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def clear_pending(state: UserState) -> None:
    data = dict(state.context_data or {})
    data.pop(PENDING_RECURRING_KEY, None)
    state.context_data = data
    state.save(update_fields=['context_data', 'updated_at'])
