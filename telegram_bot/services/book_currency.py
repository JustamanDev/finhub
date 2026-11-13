"""Выбор валюты для долга, цели и конверта — те же кнопки, что после суммы операции."""

from decimal import Decimal

from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from transactions.currencies import button_label, format_money, prefs_tuple

PENDING_KEY = 'pending_book_currency'


async def take_or_ask(
    update,
    context,
    telegram_user,
    amount: Decimal,
    *,
    kind: str,
    payload: dict,
    named: str | None = None,
    prompt: str | None = None,
) -> str | None:
    """Код валюты, если его уже можно взять. None — бот показал кнопки и ждёт."""
    _base, inputs = await sync_to_async(prefs_tuple)(telegram_user)
    chosen = named if named in inputs else None
    if chosen is None and len(inputs) == 1:
        chosen = inputs[0]
    if chosen:
        return chosen
    context.user_data[PENDING_KEY] = {
        'kind': kind,
        'amount': str(amount),
        'payload': payload,
    }
    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for code in inputs:
        pair.append(InlineKeyboardButton(button_label(code), callback_data=f'book_currency_{code}'))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton('Отмена', callback_data='book_currency_cancel')])
    label = format_money(amount, '').strip()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=prompt or f'{label} — в какой валюте?',
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return None


async def apply_choice(update, context, telegram_user, currency: str | None) -> None:
    """Продолжает ввод после кнопки валюты или отмены."""
    query = update.callback_query
    pending = context.user_data.pop(PENDING_KEY, None)
    if not pending:
        if query is not None:
            await query.answer('Отправьте сумму ещё раз.')
        return
    if currency is None:
        _drop_draft(context, pending.get('kind'))
        if query is not None:
            await query.answer()
            await query.edit_message_text('Хорошо, эту сумму не записал.')
        return
    _base, inputs = await sync_to_async(prefs_tuple)(telegram_user)
    if currency not in inputs:
        context.user_data[PENDING_KEY] = pending
        if query is not None:
            await query.answer('Этой валюты нет в настройках ввода.')
        return
    if query is not None:
        await query.answer()
    amount = Decimal(pending['amount'])
    kind = pending['kind']
    payload = pending.get('payload') or {}
    if kind == 'debt_create':
        from telegram_bot.handlers.debts_handler import DebtsHandler

        await DebtsHandler().finish_create(
            update,
            context,
            telegram_user,
            amount,
            currency,
            counterparty=payload.get('counterparty', ''),
            direction=payload.get('direction', ''),
        )
        return
    if kind == 'debt_pay':
        from telegram_bot.handlers.debts_handler import DebtsHandler

        await DebtsHandler().finish_pay(
            update,
            context,
            telegram_user,
            int(payload['debt_id']),
            amount,
            currency,
        )
        return
    if kind == 'goal_target':
        await _continue_goal_deadline(update, context, amount, currency)
        return
    if kind == 'envelope_open':
        from telegram_bot.handlers.text_handler import TextHandler

        deposit = Decimal(payload['deposit']) if payload.get('deposit') is not None else amount
        await TextHandler()._finish_envelope(
            update,
            context,
            telegram_user,
            payload.get('title', ''),
            deposit,
            currency,
        )
        return
    if kind in {'goal_deposit', 'goal_withdraw'}:
        from telegram_bot.handlers.text_handler import TextHandler

        await TextHandler()._apply_goal_movement(
            update,
            context,
            telegram_user,
            int(payload['goal_id']),
            amount,
            currency,
            withdraw=kind == 'goal_withdraw',
        )
        return
    if query is not None:
        await query.edit_message_text('Не понял, куда записать сумму. Начните ещё раз.')


async def _continue_goal_deadline(update, context, amount: Decimal, currency: str) -> None:
    from telegram_bot.keyboards.goals import GoalsKeyboard

    data = dict(context.user_data.get('goal_creation_data') or {})
    data['target_amount'] = str(amount)
    data['currency'] = currency
    context.user_data['goal_creation_data'] = data
    context.user_data['goal_creation_step'] = 'deadline'
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='📅 Введите дедлайн (ДД.MM.YYYY) или напишите **«без срока»**:',
        reply_markup=GoalsKeyboard.get_goal_input_keyboard(cancel_callback='goals_menu'),
        parse_mode='Markdown',
    )


def _drop_draft(context, kind: str | None) -> None:
    if kind == 'goal_deposit':
        context.user_data.pop('goal_deposit_goal_id', None)
    elif kind == 'goal_withdraw':
        context.user_data.pop('goal_withdraw_goal_id', None)
    elif kind in {'debt_create', 'debt_pay'}:
        context.user_data.pop('debt_draft', None)
        context.user_data.pop('debt_payment_id', None)
    elif kind in {'goal_target', 'envelope_open'}:
        context.user_data.pop('goal_creation_step', None)
        context.user_data.pop('goal_creation_data', None)
