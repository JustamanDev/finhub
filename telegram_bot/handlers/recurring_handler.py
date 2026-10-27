"""Меню повторов. Напоминание и ответ суммой живут отдельно от долгов."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from asgiref.sync import sync_to_async
from telegram import Update
from telegram.ext import ContextTypes

from categories.models import Category
from recurring.models import RecurringTemplate
from recurring.rhythm import expectation_phrase, format_due
from telegram_bot.handlers.base import BaseHandler
from telegram_bot.keyboards.recurring import (
    recurring_card_keyboard,
    recurring_category_keyboard,
    recurring_due_keyboard,
    recurring_kind_keyboard,
    recurring_menu_keyboard,
    recurring_period_keyboard,
    recurring_type_keyboard,
)
from telegram_bot.services.recurring_posting import record_occurrence
from telegram_bot.services.recurring_reminders import (
    clear_pending,
    pending_template_id,
)
from telegram_bot.services.weekly_digest import vietnam_today
from telegram_bot.utils.telegram_resilience import safe_edit_message_text
from transactions.currencies import base_for_user, symbol_of

DRAFT_KEY = 'recur_draft'


def parse_plain_amount(text: str) -> Decimal | None:
    """Одно положительное число. «500 кофе» сюда не попадает."""
    cleaned = text.strip().replace(' ', '').replace(',', '.')
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    return value.quantize(Decimal('0.01'))


def _money_factory(currency: str):
    def money(amount: Decimal) -> str:
        whole = int(Decimal(amount).quantize(Decimal('1')))
        grouped = f'{abs(whole):,}'.replace(',', ' ')
        return f'{grouped} {symbol_of(currency)}'

    return money


class RecurringHandler(BaseHandler):
    async def show_menu(self, query, context, telegram_user) -> None:
        context.user_data.pop(DRAFT_KEY, None)
        user = await sync_to_async(lambda: telegram_user.user)()
        templates = await sync_to_async(list)(
            RecurringTemplate.objects.filter(user=user).order_by('next_due', 'name'),
        )
        await safe_edit_message_text(
            query,
            text='🔁 Повторы\n\nБот напомнит в нужный день. Ответите суммой — запишется обычная операция.',
            reply_markup=recurring_menu_keyboard(templates),
        )

    async def handle_callback(self, query, context, telegram_user) -> None:
        data = query.data
        if data == 'recur_menu':
            await self.show_menu(query, context, telegram_user)
            return
        if data == 'recur_add':
            context.user_data[DRAFT_KEY] = {'step': 'name'}
            await safe_edit_message_text(
                query,
                text='Как назвать повтор? Например, аренда или зарплата.',
            )
            return
        if data in ('recur_type_expense', 'recur_type_income'):
            await self._pick_type(query, context, telegram_user, data.rsplit('_', 1)[-1])
            return
        if data.startswith('recur_cat_'):
            await self._pick_category(query, context, telegram_user, int(data.removeprefix('recur_cat_')))
            return
        if data.startswith('recur_every_'):
            await self._pick_period(query, context, data.removeprefix('recur_every_'))
            return
        if data.startswith('recur_kind_'):
            await self._pick_kind(query, context, data.removeprefix('recur_kind_'))
            return
        if data == 'recur_due_today':
            await self._finish(query, context, telegram_user, vietnam_today())
            return
        if data.startswith('recur_open_'):
            await self._open_card(query, telegram_user, int(data.removeprefix('recur_open_')))
            return
        if data.startswith('recur_pause_'):
            await self._toggle(query, context, telegram_user, int(data.removeprefix('recur_pause_')))
            return
        if data.startswith('recur_ask_'):
            await self._ask_amount(query, telegram_user, int(data.removeprefix('recur_ask_')))
            return
        await query.answer('Не понял кнопку')

    async def maybe_text(self, update: Update, context, telegram_user, message_text: str) -> bool:
        """True, если сообщение ушло в повтор, а не в обычный ввод."""
        state = await self.get_user_state(telegram_user)
        template_id = pending_template_id(state)
        amount = parse_plain_amount(message_text)
        if template_id and amount is not None:
            await self._record(update, telegram_user, state, template_id, amount)
            return True

        draft = context.user_data.get(DRAFT_KEY)
        if not draft:
            return False
        step = draft.get('step')
        if step == 'name':
            name = message_text.strip()
            if not name:
                await update.message.reply_text('Нужно имя.')
                return True
            draft['name'] = name[:100]
            draft['step'] = 'type'
            await update.message.reply_text(
                'Это расход или доход?',
                reply_markup=recurring_type_keyboard(),
            )
            return True
        if step == 'exact':
            if amount is None:
                await update.message.reply_text('Напишите сумму одним числом.')
                return True
            draft['amount'] = str(amount)
            draft['step'] = 'due'
            await update.message.reply_text(
                'Когда следующий раз? Напишите дату как 15.11.2026 или нажмите кнопку.',
                reply_markup=recurring_due_keyboard(),
            )
            return True
        if step == 'range':
            parts = message_text.replace(',', '.').split()
            if len(parts) != 2:
                await update.message.reply_text('Две суммы через пробел: от и до.')
                return True
            low = parse_plain_amount(parts[0])
            high = parse_plain_amount(parts[1])
            if low is None or high is None or high < low:
                await update.message.reply_text('Диапазон не сошёлся. Например: 10000 15000')
                return True
            draft['amount_min'] = str(low)
            draft['amount_max'] = str(high)
            draft['step'] = 'due'
            await update.message.reply_text(
                'Когда следующий раз? Напишите дату как 15.11.2026 или нажмите кнопку.',
                reply_markup=recurring_due_keyboard(),
            )
            return True
        if step == 'due':
            parsed = _parse_date(message_text)
            if parsed is None:
                await update.message.reply_text('Дата в виде 15.11.2026.')
                return True
            await self._finish_message(update, context, telegram_user, parsed)
            return True
        return False

    async def _pick_type(self, query, context, telegram_user, category_type: str) -> None:
        draft = context.user_data.get(DRAFT_KEY) or {}
        draft['category_type'] = category_type
        draft['step'] = 'category'
        context.user_data[DRAFT_KEY] = draft
        user = await sync_to_async(lambda: telegram_user.user)()
        categories = await sync_to_async(list)(
            Category.objects.filter(user=user, type=category_type, is_active=True).order_by('name'),
        )
        if not categories:
            await safe_edit_message_text(query, text='Сначала заведите категорию в настройках.')
            return
        await safe_edit_message_text(
            query,
            text='В какую категорию писать операцию?',
            reply_markup=recurring_category_keyboard(categories),
        )

    async def _pick_category(self, query, context, telegram_user, category_id: int) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        category = await Category.objects.filter(id=category_id, user=user, is_active=True).afirst()
        if category is None:
            await query.answer('Категория не найдена')
            return
        draft = context.user_data.get(DRAFT_KEY) or {}
        draft['category_id'] = category.id
        draft['step'] = 'period'
        context.user_data[DRAFT_KEY] = draft
        await safe_edit_message_text(
            query,
            text='Как часто?',
            reply_markup=recurring_period_keyboard(),
        )

    async def _pick_period(self, query, context, periodicity: str) -> None:
        if periodicity not in {
            RecurringTemplate.WEEKLY,
            RecurringTemplate.MONTHLY,
            RecurringTemplate.YEARLY,
        }:
            await query.answer('Неизвестный ритм')
            return
        draft = context.user_data.get(DRAFT_KEY) or {}
        draft['periodicity'] = periodicity
        draft['step'] = 'kind'
        context.user_data[DRAFT_KEY] = draft
        await safe_edit_message_text(
            query,
            text='Сумма обычно одна и та же, в диапазоне или каждый раз своя?',
            reply_markup=recurring_kind_keyboard(),
        )

    async def _pick_kind(self, query, context, kind: str) -> None:
        draft = context.user_data.get(DRAFT_KEY) or {}
        draft['amount_kind'] = kind
        context.user_data[DRAFT_KEY] = draft
        if kind == RecurringTemplate.EXACT:
            draft['step'] = 'exact'
            await safe_edit_message_text(query, text='Какая точная сумма? Напишите число.')
            return
        if kind == RecurringTemplate.RANGE:
            draft['step'] = 'range'
            await safe_edit_message_text(query, text='Напишите две суммы через пробел: от и до.')
            return
        if kind == RecurringTemplate.OPEN:
            draft['step'] = 'due'
            await safe_edit_message_text(
                query,
                text='Когда следующий раз? Напишите дату как 15.11.2026 или нажмите кнопку.',
                reply_markup=recurring_due_keyboard(),
            )
            return
        await query.answer('Не понял')

    async def _finish(self, query, context, telegram_user, due) -> None:
        template = await self._save_draft(context, telegram_user, due)
        if template is None:
            await safe_edit_message_text(query, text='Черновик повтора потерялся. Начните заново.')
            return
        context.user_data.pop(DRAFT_KEY, None)
        await safe_edit_message_text(
            query,
            text=f'Готово. {template.name} — следующий раз {format_due(template.next_due)}.',
            reply_markup=recurring_card_keyboard(template.id, template.is_active),
        )

    async def _finish_message(self, update, context, telegram_user, due) -> None:
        template = await self._save_draft(context, telegram_user, due)
        context.user_data.pop(DRAFT_KEY, None)
        if template is None:
            await update.message.reply_text('Черновик повтора потерялся. Начните заново.')
            return
        await update.message.reply_text(
            f'Готово. {template.name} — следующий раз {format_due(template.next_due)}.',
            reply_markup=recurring_card_keyboard(template.id, template.is_active),
        )

    async def _save_draft(self, context, telegram_user, due):
        draft = context.user_data.get(DRAFT_KEY) or {}
        if 'name' not in draft or 'category_id' not in draft or 'periodicity' not in draft:
            return None
        user = await sync_to_async(lambda: telegram_user.user)()
        kind = draft.get('amount_kind', RecurringTemplate.OPEN)

        def _create():
            template = RecurringTemplate(
                user=user,
                name=draft['name'],
                category_id=draft['category_id'],
                periodicity=draft['periodicity'],
                amount_kind=kind,
                next_due=due,
                amount=Decimal(draft['amount']) if kind == RecurringTemplate.EXACT else None,
                amount_min=Decimal(draft['amount_min']) if kind == RecurringTemplate.RANGE else None,
                amount_max=Decimal(draft['amount_max']) if kind == RecurringTemplate.RANGE else None,
            )
            template.full_clean()
            template.save()
            return template

        return await sync_to_async(_create)()

    async def _open_card(self, query, telegram_user, template_id: int) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        template = await RecurringTemplate.objects.filter(
            id=template_id,
            user=user,
        ).select_related('category').afirst()
        if template is None:
            await query.answer('Повтор не найден')
            return
        currency = await sync_to_async(base_for_user)(user)
        hint = expectation_phrase(template, _money_factory(currency))
        state = 'идёт' if template.is_active else 'на паузе'
        await safe_edit_message_text(
            query,
            text=(
                f'{template.name}\n'
                f'{template.category.icon} {template.category.name}\n'
                f'Следующий раз {format_due(template.next_due)}, {hint}.\n'
                f'Сейчас {state}.'
            ),
            reply_markup=recurring_card_keyboard(template.id, template.is_active),
        )

    async def _toggle(self, query, context, telegram_user, template_id: int) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()

        def _flip():
            template = RecurringTemplate.objects.filter(id=template_id, user=user).first()
            if template is None:
                return None
            template.is_active = not template.is_active
            template.save(update_fields=['is_active', 'updated_at'])
            return template

        template = await sync_to_async(_flip)()
        if template is None:
            await query.answer('Повтор не найден')
            return
        await self._open_card(query, telegram_user, template.id)

    async def _ask_amount(self, query, telegram_user, template_id: int) -> None:
        state = await self.get_user_state(telegram_user)

        def _set():
            data = dict(state.context_data or {})
            data['pending_recurring_id'] = template_id
            state.context_data = data
            state.save(update_fields=['context_data', 'updated_at'])

        await sync_to_async(_set)()
        await safe_edit_message_text(query, text='Напишите сумму одним числом.')

    async def _record(self, update, telegram_user, state, template_id: int, amount: Decimal) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()
        template = await RecurringTemplate.objects.filter(
            id=template_id,
            user=user,
            is_active=True,
        ).select_related('category', 'user').afirst()
        if template is None:
            await sync_to_async(clear_pending)(state)
            await update.message.reply_text('Этот повтор уже недоступен.')
            return
        today = vietnam_today()
        transaction = await sync_to_async(record_occurrence)(template, amount, today)
        await sync_to_async(clear_pending)(state)
        await sync_to_async(template.refresh_from_db)()
        await update.message.reply_text(
            f'Записал {template.name}. Следующий раз {format_due(template.next_due)}.',
        )
        from telegram_bot.services.budget_alerts import breaches_of, send_budget_breaches

        await send_budget_breaches(
            update.get_bot(),
            update.effective_chat.id,
            breaches_of(transaction),
            currency=transaction.report_currency,
        )


def _parse_date(text: str):
    raw = text.strip()
    for fmt in ('%d.%m.%Y', '%d.%m.%y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
