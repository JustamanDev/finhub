"""Меню долгов. Сумма и контрагент. Транзакций отсюда не рождается."""

from decimal import Decimal

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from debts.ledger import add_payment
from debts.models import Debt
from telegram_bot.handlers.base import BaseHandler
from telegram_bot.handlers.recurring_handler import parse_plain_amount
from telegram_bot.keyboards.debts import (
    debt_card_keyboard,
    debt_direction_keyboard,
    debts_menu_keyboard,
)
from telegram_bot.services.weekly_digest import vietnam_today
from telegram_bot.utils.telegram_resilience import safe_edit_message_text
from transactions.currencies import base_for_user, symbol_of

DRAFT_KEY = 'debt_draft'
PAY_KEY = 'debt_payment_id'


def _money(amount: Decimal, currency: str) -> str:
    whole = int(Decimal(amount).quantize(Decimal('1')))
    grouped = f'{abs(whole):,}'.replace(',', ' ')
    return f'{grouped} {symbol_of(currency)}'


class DebtsHandler(BaseHandler):
    async def show_menu(self, query, context, telegram_user) -> None:
        context.user_data.pop(DRAFT_KEY, None)
        context.user_data.pop(PAY_KEY, None)
        user = await sync_to_async(lambda: telegram_user.user)()
        debts = await sync_to_async(list)(
            Debt.objects.filter(user=user, is_open=True).order_by('counterparty'),
        )
        await safe_edit_message_text(
            query,
            text='🤝 Долги\n\nЗдесь только кому и сколько. В расходы это само не попадает.',
            reply_markup=debts_menu_keyboard(debts),
        )

    async def handle_callback(self, query, context, telegram_user) -> None:
        data = query.data
        if data == 'debts_menu':
            await self.show_menu(query, context, telegram_user)
            return
        if data == 'debt_add':
            context.user_data[DRAFT_KEY] = {'step': 'who'}
            await safe_edit_message_text(query, text='Кому? Напишите имя.')
            return
        if data in ('debt_dir_owe', 'debt_dir_owed'):
            draft = context.user_data.get(DRAFT_KEY) or {}
            draft['direction'] = Debt.OWE if data.endswith('owe') else Debt.OWED
            draft['step'] = 'amount'
            context.user_data[DRAFT_KEY] = draft
            await safe_edit_message_text(query, text='Какая сумма? Напишите число.')
            return
        if data.startswith('debt_open_'):
            await self._open_card(query, telegram_user, int(data.removeprefix('debt_open_')))
            return
        if data.startswith('debt_pay_'):
            context.user_data[PAY_KEY] = int(data.removeprefix('debt_pay_'))
            await safe_edit_message_text(query, text='Сколько пришло или ушло по этому долгу?')
            return
        await query.answer('Не понял кнопку')

    async def maybe_text(self, update: Update, context, telegram_user, message_text: str) -> bool:
        pay_id = context.user_data.get(PAY_KEY)
        amount = parse_plain_amount(message_text)
        if pay_id and amount is not None:
            await self._pay(update, context, telegram_user, int(pay_id), amount)
            return True
        if pay_id and amount is None:
            await update.message.reply_text('Напишите сумму платежа одним числом.')
            return True

        draft = context.user_data.get(DRAFT_KEY)
        if not draft:
            return False
        if draft.get('step') == 'who':
            name = message_text.strip()
            if not name:
                await update.message.reply_text('Нужно имя.')
                return True
            draft['counterparty'] = name[:100]
            draft['step'] = 'direction'
            await update.message.reply_text(
                'Вы должны или вам?',
                reply_markup=debt_direction_keyboard(),
            )
            return True
        if draft.get('step') == 'amount':
            if amount is None:
                await update.message.reply_text('Напишите сумму одним числом.')
                return True
            await self._create(update, context, telegram_user, amount)
            return True
        return False

    async def _create(self, update, context, telegram_user, amount: Decimal) -> None:
        draft = context.user_data.get(DRAFT_KEY) or {}
        user = await sync_to_async(lambda: telegram_user.user)()

        def _save():
            debt = Debt(
                user=user,
                counterparty=draft['counterparty'],
                direction=draft['direction'],
                principal=amount,
            )
            debt.full_clean()
            debt.save()
            return debt

        debt = await sync_to_async(_save)()
        context.user_data.pop(DRAFT_KEY, None)
        currency = await sync_to_async(base_for_user)(user)
        side = 'я должен' if debt.direction == Debt.OWE else 'мне должны'
        await update.message.reply_text(
            f'{debt.counterparty}: {side} {_money(debt.principal, currency)}.',
            reply_markup=debt_card_keyboard(debt.id),
        )

    async def _open_card(self, query, telegram_user, debt_id: int) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()

        def _load():
            debt = Debt.objects.filter(id=debt_id, user=user, is_open=True).first()
            if debt is None:
                return None
            return {
                'id': debt.id,
                'counterparty': debt.counterparty,
                'direction': debt.direction,
                'principal': debt.principal,
                'remaining': debt.remaining,
            }

        card = await sync_to_async(_load)()
        if card is None:
            await query.answer('Долг не найден')
            return
        currency = await sync_to_async(base_for_user)(user)
        side = 'Я должен' if card['direction'] == Debt.OWE else 'Мне должны'
        await safe_edit_message_text(
            query,
            text=(
                f'{card["counterparty"]}\n'
                f'{side}. Было {_money(card["principal"], currency)}, '
                f'осталось {_money(card["remaining"], currency)}.'
            ),
            reply_markup=debt_card_keyboard(card['id']),
        )

    async def _pay(self, update, context, telegram_user, debt_id: int, amount: Decimal) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        today = vietnam_today()

        def _apply():
            debt = Debt.objects.filter(id=debt_id, user=user, is_open=True).first()
            if debt is None:
                return None, 'Долг уже закрыт.'
            try:
                add_payment(debt, amount, today)
            except ValueError as exc:
                return None, str(exc)
            debt.refresh_from_db()
            return {
                'is_open': debt.is_open,
                'remaining': debt.remaining,
                'counterparty': debt.counterparty,
            }, None

        card, error = await sync_to_async(_apply)()
        if error:
            await update.message.reply_text(error)
            return
        context.user_data.pop(PAY_KEY, None)
        currency = await sync_to_async(base_for_user)(user)
        if card['is_open']:
            await update.message.reply_text(
                f'Принял. Осталось {_money(card["remaining"], currency)}.',
            )
        else:
            await update.message.reply_text(f'{card["counterparty"]}: долг закрыт.')
