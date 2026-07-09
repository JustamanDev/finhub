"""Multi-turn voice dialog for incomplete CREATE_TRANSACTION commands.

State priority (voice_handler):
  interactive wizard
  > awaiting_category_creation
  > voice_dialog (this module)
  > awaiting_category (legacy amount_only picker)
  > voice_pending / voice_category_pending block
  > new interpret

CREATE_TRANSACTION dialog steps:
  awaiting_amount   — ask for sum
  awaiting_type     — ask expense vs income (rare)
  awaiting_category — ask / resolve category (may hand off to CategoryResolver UI)
  awaiting_confirm  — medium-confidence confirm (reuses voice_pending)

State × Input → Action:
  dialog + amount reply     → fill amount, advance
  dialog + type reply       → fill type, advance
  dialog + category reply   → resolve category, advance or disambiguate
  dialog + cancel / timeout → clear dialog
  dialog + full phrase      → merge slots from re-parse, advance
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from asgiref.sync import sync_to_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from telegram_bot.voice.category_resolver import CategoryResolver, ResolveStatus
from telegram_bot.voice.intents import (
    CONFIDENCE_AUTO_SAVE,
    GOAL_ACTION_CREATE,
    GOAL_ACTION_DEPOSIT,
    GOAL_ACTION_WITHDRAW,
    ParsedVoiceCommand,
    VoiceIntentType,
)
from telegram_bot.voice.interpreter import VoiceInterpreter, voice_text_parse_candidates

logger = logging.getLogger(__name__)

VOICE_DIALOG_KEY = 'voice_dialog'
DEFAULT_TIMEOUT_SEC = 300

STEP_AMOUNT = 'awaiting_amount'
STEP_TYPE = 'awaiting_type'
STEP_CATEGORY = 'awaiting_category'
STEP_GOAL = 'awaiting_goal'
STEP_CONFIRM = 'awaiting_confirm'

TYPE_KEYWORDS = {
    'expense': {
        'расход', 'расходы', 'трата', 'траты', 'expense', 'минус', '-',
    },
    'income': {
        'доход', 'доходы', 'приход', 'зарплата', 'income', 'плюс', '+',
    },
}


@dataclass
class VoiceDialogState:
    intent: str
    step: str
    slots: dict[str, Any] = field(default_factory=dict)
    transcript: str = ''
    created_at: float = field(default_factory=time.time)
    last_prompt: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'intent': self.intent,
            'step': self.step,
            'slots': dict(self.slots),
            'transcript': self.transcript,
            'created_at': self.created_at,
            'last_prompt': self.last_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoiceDialogState:
        return cls(
            intent=data.get('intent', VoiceIntentType.CREATE_TRANSACTION.value),
            step=data.get('step', STEP_AMOUNT),
            slots=dict(data.get('slots') or {}),
            transcript=data.get('transcript') or '',
            created_at=float(data.get('created_at') or time.time()),
            last_prompt=data.get('last_prompt') or '',
        )


def get_dialog(context: ContextTypes.DEFAULT_TYPE) -> VoiceDialogState | None:
    raw = context.user_data.get(VOICE_DIALOG_KEY)
    if not raw:
        return None
    return VoiceDialogState.from_dict(raw)


def save_dialog(
    context: ContextTypes.DEFAULT_TYPE,
    dialog: VoiceDialogState,
) -> None:
    context.user_data[VOICE_DIALOG_KEY] = dialog.to_dict()


def clear_dialog(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(VOICE_DIALOG_KEY, None)


def is_dialog_expired(
    dialog: VoiceDialogState,
    *,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> bool:
    return (time.time() - dialog.created_at) > timeout_sec


def missing_slots_for_create(command: ParsedVoiceCommand) -> list[str]:
    """Return ordered missing slots for CREATE_TRANSACTION dialog."""
    missing: list[str] = []
    if command.amount is None:
        missing.append('amount')
    if not command.transaction_type:
        missing.append('transaction_type')
    if command.category_name and not command.category:
        missing.append('category')
    return missing


def missing_slots_for_budget(command: ParsedVoiceCommand) -> list[str]:
    """Return ordered missing slots for SET_BUDGET dialog."""
    missing: list[str] = []
    if command.amount is None:
        missing.append('amount')
    if not command.category and not command.category_name:
        missing.append('category')
    elif command.category_name and not command.category:
        missing.append('category')
    return missing


def missing_slots_for_goal(command: ParsedVoiceCommand) -> list[str]:
    """Return ordered missing slots for MANAGE_GOAL dialog."""
    missing: list[str] = []
    action = command.goal_action
    if not action:
        missing.append('goal_action')
        return missing
    if action == GOAL_ACTION_CREATE:
        if not command.goal_title:
            missing.append('goal')
        if command.amount is None:
            missing.append('amount')
        return missing
    if action in {GOAL_ACTION_DEPOSIT, GOAL_ACTION_WITHDRAW}:
        if command.amount is None:
            missing.append('amount')
        if not command.goal and not command.goal_title:
            missing.append('goal')
        elif command.goal_title and not command.goal:
            missing.append('goal')
    return missing


def next_step(missing: list[str]) -> str | None:
    if 'amount' in missing:
        return STEP_AMOUNT
    if 'transaction_type' in missing:
        return STEP_TYPE
    if 'category' in missing:
        return STEP_CATEGORY
    if 'goal' in missing:
        return STEP_GOAL
    return None


def prompt_for_step(step: str, slots: dict[str, Any], *, intent: str = '') -> str:
    amount = slots.get('amount')
    cat = slots.get('category_name') or slots.get('category_label')
    goal_title = slots.get('goal_title') or slots.get('goal_label')
    goal_action = slots.get('goal_action')
    is_budget = intent == VoiceIntentType.SET_BUDGET.value
    is_goal = intent == VoiceIntentType.MANAGE_GOAL.value
    if step == STEP_AMOUNT:
        if is_goal:
            if goal_action == GOAL_ACTION_CREATE:
                if goal_title:
                    return (
                        f'Какая целевая сумма для «{goal_title}»? '
                        f'Например: 100000'
                    )
                return 'Какая целевая сумма? Например: 100000'
            if goal_action == GOAL_ACTION_WITHDRAW:
                if goal_title:
                    return f'Сколько снять с «{goal_title}»? Например: 1000'
                return 'Сколько снять с цели? Например: 1000'
            if goal_title:
                return f'Сколько пополнить «{goal_title}»? Например: 5000'
            return 'Сколько пополнить цель? Например: 5000'
        if is_budget:
            if cat:
                return f'Какой лимит установить на «{cat}»? Например: 5000'
            return 'Какой лимит установить? Например: 5000'
        if cat:
            return f'Какую сумму записать в «{cat}»?'
        return 'Какую сумму записать? Например: 500 или 1500.50'
    if step == STEP_TYPE:
        return 'Это расход или доход?'
    if step == STEP_CATEGORY:
        if is_budget:
            if amount is not None:
                return f'На какую категорию установить лимит {amount:,.0f}₽?'
            return 'На какую категорию установить лимит?'
        if amount is not None:
            return f'На какую категорию записать {amount:,.0f}₽?'
        return 'На какую категорию записать?'
    if step == STEP_GOAL:
        if goal_action == GOAL_ACTION_CREATE:
            return 'Как назвать новую цель?'
        if amount is not None:
            verb = 'снять' if goal_action == GOAL_ACTION_WITHDRAW else 'пополнить'
            return f'Какую цель {verb} на {amount:,.0f}₽?'
        return 'Какую цель имеете в виду?'
    return 'Уточните, пожалуйста.'


def command_to_slots(command: ParsedVoiceCommand) -> dict[str, Any]:
    slots: dict[str, Any] = {
        'intent': command.intent.value,
    }
    if command.amount is not None:
        slots['amount'] = command.amount
    if command.transaction_type:
        slots['transaction_type'] = command.transaction_type
    if command.category_name:
        slots['category_name'] = command.category_name
    if command.category is not None:
        slots['category_id'] = command.category.id
        slots['category_label'] = (
            f'{command.category.icon} {command.category.name}'
        )
        slots['transaction_type'] = command.category.type
    if command.goal_action:
        slots['goal_action'] = command.goal_action
    if command.goal_title:
        slots['goal_title'] = command.goal_title
    if command.goal is not None:
        slots['goal_id'] = command.goal.id
        slots['goal_title'] = command.goal.title
        slots['goal_label'] = command.goal.title
    if command.description:
        slots['description'] = command.description
    slots['confidence'] = command.confidence
    slots['raw_transcript'] = command.raw_transcript
    return slots


def slots_to_command(slots: dict[str, Any], transcript: str) -> ParsedVoiceCommand:
    amount = slots.get('amount')
    if amount is not None and not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    category = None
    category_id = slots.get('category_id')
    # category object may be re-loaded by caller; keep id in slots
    category_name = slots.get('category_name')
    tx_type = slots.get('transaction_type') or 'expense'
    intent_raw = slots.get('intent') or VoiceIntentType.CREATE_TRANSACTION.value
    if intent_raw == VoiceIntentType.SET_BUDGET.value:
        intent = VoiceIntentType.SET_BUDGET
    elif intent_raw == VoiceIntentType.MANAGE_GOAL.value:
        intent = VoiceIntentType.MANAGE_GOAL
    else:
        intent = VoiceIntentType.CREATE_TRANSACTION
    has_category = category_id is not None or category is not None
    if category_name and not has_category:
        command_type = 'amount_category'
    elif has_category:
        command_type = 'amount_category'
    else:
        command_type = 'amount_only'
    return ParsedVoiceCommand(
        intent=intent,
        success=True,
        confidence=float(slots.get('confidence') or 1.0),
        raw_transcript=transcript or slots.get('raw_transcript') or '',
        transaction_type=tx_type,
        amount=amount,
        category_name=category_name,
        category=category,
        description=slots.get('description') or '',
        command_type=command_type,
        goal_action=slots.get('goal_action'),
        goal_title=slots.get('goal_title'),
        goal=None,
    )


def _parse_amount(text: str) -> Decimal | None:
    from telegram_bot.voice.number_words import (
        parse_number_words,
        replace_spoken_numbers,
    )

    raw = (text or '').strip()
    if not raw:
        return None
    # «Да, пять тысяч» / «ок 5000»
    raw = re.sub(
        r'(?i)^(да|ок|хорошо|верно|ага|угу)[,!.\s]+',
        '',
        raw,
    ).strip()
    # Drop currency words for digit parse
    digitish = re.sub(
        r'(?i)\s*руб(?:лей|ля|ль)?\.?\s*$',
        '',
        raw,
    ).strip()

    cleaned = digitish.replace(' ', '').replace(',', '.')
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    try:
        value = Decimal(cleaned)
        if value > 0:
            return value.copy_abs()
    except (InvalidOperation, ValueError):
        pass

    expanded = replace_spoken_numbers(digitish)
    expanded_clean = re.sub(
        r'(?i)\s*руб(?:лей|ля|ль)?\.?\s*$',
        '',
        expanded,
    ).strip().replace(' ', '').replace(',', '.')
    try:
        value = Decimal(expanded_clean)
        if value > 0:
            return value.copy_abs()
    except (InvalidOperation, ValueError):
        pass

    spoken = parse_number_words(digitish)
    if spoken is not None and spoken > 0:
        return spoken.copy_abs()
    return None


def _parse_type(text: str) -> str | None:
    normalized = text.strip().lower().replace('ё', 'е')
    if normalized in TYPE_KEYWORDS['expense']:
        return 'expense'
    if normalized in TYPE_KEYWORDS['income']:
        return 'income'
    return None


class VoiceDialogManager:
    def __init__(self) -> None:
        from telegram_bot.services.command_executor import CommandExecutor

        self._executor = CommandExecutor()

    async def start_from_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        command: ParsedVoiceCommand,
        missing: list[str],
    ) -> None:
        step = next_step(missing)
        if not step:
            await self._finish(
                update,
                context,
                telegram_user,
                command_to_slots(command),
                command.raw_transcript,
            )
            return

        dialog = VoiceDialogState(
            intent=command.intent.value,
            step=step,
            slots=command_to_slots(command),
            transcript=command.raw_transcript,
        )
        question = prompt_for_step(step, dialog.slots, intent=dialog.intent)
        dialog.last_prompt = question
        save_dialog(context, dialog)

        lines = [f'🎤 Распознано: «{command.raw_transcript}»', '', question]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text='❌ Отмена',
                    callback_data='voice_cancel',
                ),
            ],
        ])
        if step == STEP_TYPE:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        text='💸 Расход',
                        callback_data='voice_dialog_type_expense',
                    ),
                    InlineKeyboardButton(
                        text='💰 Доход',
                        callback_data='voice_dialog_type_income',
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text='❌ Отмена',
                        callback_data='voice_cancel',
                    ),
                ],
            ])

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='\n'.join(lines),
            reply_markup=keyboard,
        )

    async def continue_dialog(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        reply_text: str,
    ) -> bool:
        """Continue active dialog. Returns True if handled."""
        dialog = get_dialog(context)
        if not dialog:
            return False
        if is_dialog_expired(dialog):
            clear_dialog(context)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='⏱ Диалог устарел. Отправьте команду заново.',
            )
            return True

        text = reply_text.strip()
        if not text:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=dialog.last_prompt or prompt_for_step(
                    dialog.step,
                    dialog.slots,
                    intent=dialog.intent,
                ),
            )
            return True

        if text.lower() in {'отмена', 'cancel', 'стоп'}:
            clear_dialog(context)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='❌ Голосовая команда отменена.',
            )
            return True

        # Try to fill current step, then re-check all slots.
        await self._apply_reply(dialog, telegram_user, text)
        save_dialog(context, dialog)

        missing = self._missing_from_slots(dialog.slots, intent=dialog.intent)

        # Named but unresolved category → picker/create UI (do not free-text loop).
        if (
            'category' in missing
            and dialog.slots.get('amount') is not None
            and (
                dialog.intent == VoiceIntentType.SET_BUDGET.value
                or dialog.slots.get('transaction_type')
            )
            and dialog.slots.get('category_name')
            and not dialog.slots.get('category_id')
        ):
            command = slots_to_command(dialog.slots, dialog.transcript)
            clear_dialog(context)
            await self._executor.prompt_category_resolution(
                update,
                context,
                telegram_user,
                command,
            )
            return True

        # Named but unresolved goal → picker UI.
        if (
            dialog.intent == VoiceIntentType.MANAGE_GOAL.value
            and 'goal' in missing
            and dialog.slots.get('goal_title')
            and not dialog.slots.get('goal_id')
            and dialog.slots.get('goal_action') != GOAL_ACTION_CREATE
            and dialog.slots.get('amount') is not None
        ):
            command = slots_to_command(dialog.slots, dialog.transcript)
            clear_dialog(context)
            await self._executor.prompt_goal_resolution(
                update,
                context,
                telegram_user,
                command,
            )
            return True

        step = next_step(missing)
        if step:
            dialog.step = step
            question = prompt_for_step(step, dialog.slots, intent=dialog.intent)
            dialog.last_prompt = question
            save_dialog(context, dialog)
            keyboard = None
            if step == STEP_TYPE:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text='💸 Расход',
                            callback_data='voice_dialog_type_expense',
                        ),
                        InlineKeyboardButton(
                            text='💰 Доход',
                            callback_data='voice_dialog_type_income',
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text='❌ Отмена',
                            callback_data='voice_cancel',
                        ),
                    ],
                ])
            else:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text='❌ Отмена',
                            callback_data='voice_cancel',
                        ),
                    ],
                ])
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=question,
                reply_markup=keyboard,
            )
            return True

        clear_dialog(context)
        await self._finish(
            update,
            context,
            telegram_user,
            dialog.slots,
            dialog.transcript,
        )
        return True

    async def set_type_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        transaction_type: str,
    ) -> None:
        dialog = get_dialog(context)
        if not dialog:
            await update.callback_query.answer('Диалог не найден')
            return
        dialog.slots['transaction_type'] = transaction_type
        dialog.step = next_step(
            self._missing_from_slots(dialog.slots, intent=dialog.intent),
        ) or STEP_CONFIRM
        save_dialog(context, dialog)
        await update.callback_query.answer()
        # Re-enter continue with empty? Better finish path:
        missing = self._missing_from_slots(dialog.slots, intent=dialog.intent)
        step = next_step(missing)
        if step:
            dialog.step = step
            question = prompt_for_step(step, dialog.slots, intent=dialog.intent)
            dialog.last_prompt = question
            save_dialog(context, dialog)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=question,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            text='❌ Отмена',
                            callback_data='voice_cancel',
                        ),
                    ],
                ]),
            )
            return
        if dialog.slots.get('category_name') and not dialog.slots.get('category_id'):
            command = slots_to_command(dialog.slots, dialog.transcript)
            clear_dialog(context)
            await self._executor.prompt_category_resolution(
                update,
                context,
                telegram_user,
                command,
            )
            return
        clear_dialog(context)
        await self._finish(
            update,
            context,
            telegram_user,
            dialog.slots,
            dialog.transcript,
        )

    async def _apply_reply(
        self,
        dialog: VoiceDialogState,
        telegram_user,
        text: str,
    ) -> None:
        user = await sync_to_async(lambda: telegram_user.user)()

        # Prefer filling the current step, but also accept richer phrases.
        if dialog.step == STEP_AMOUNT:
            amount = _parse_amount(text)
            if amount is not None:
                dialog.slots['amount'] = amount
                return
            # Try full parse candidates
            for candidate in voice_text_parse_candidates(text):
                parsed = await sync_to_async(VoiceInterpreter(user).interpret)(
                    candidate,
                )
                if parsed.amount is not None:
                    dialog.slots['amount'] = parsed.amount
                    if parsed.transaction_type:
                        dialog.slots['transaction_type'] = parsed.transaction_type
                    if parsed.category_name:
                        dialog.slots['category_name'] = parsed.category_name
                    if parsed.category is not None:
                        dialog.slots['category_id'] = parsed.category.id
                        dialog.slots['category_label'] = (
                            f'{parsed.category.icon} {parsed.category.name}'
                        )
                        dialog.slots['transaction_type'] = parsed.category.type
                    return
            return

        if dialog.step == STEP_TYPE:
            tx_type = _parse_type(text)
            if tx_type:
                dialog.slots['transaction_type'] = tx_type
            return

        if dialog.step == STEP_CATEGORY:
            tx_type = 'expense' if (
                dialog.intent == VoiceIntentType.SET_BUDGET.value
            ) else (dialog.slots.get('transaction_type') or 'expense')
            # Full phrase may include amount correction
            for candidate in voice_text_parse_candidates(text):
                parsed = await sync_to_async(VoiceInterpreter(user).interpret)(
                    candidate,
                )
                if parsed.category is not None:
                    dialog.slots['category_id'] = parsed.category.id
                    dialog.slots['category_name'] = parsed.category.name
                    dialog.slots['category_label'] = (
                        f'{parsed.category.icon} {parsed.category.name}'
                    )
                    dialog.slots['transaction_type'] = (
                        'expense'
                        if dialog.intent == VoiceIntentType.SET_BUDGET.value
                        else parsed.category.type
                    )
                    if parsed.amount is not None:
                        dialog.slots['amount'] = parsed.amount
                    return
                if parsed.category_name:
                    dialog.slots['category_name'] = parsed.category_name

            resolved = await sync_to_async(CategoryResolver(user).resolve)(
                text,
                tx_type,
            )
            if resolved.status == ResolveStatus.MATCHED and resolved.match:
                cat = resolved.match
                dialog.slots['category_id'] = cat.id
                dialog.slots['category_name'] = cat.name
                dialog.slots['category_label'] = f'{cat.icon} {cat.name}'
                dialog.slots['transaction_type'] = cat.type
            elif resolved.status == ResolveStatus.AMBIGUOUS:
                dialog.slots['category_name'] = text
                # leave category_id empty → handoff to resolution UI
            else:
                dialog.slots['category_name'] = text

        if dialog.step == STEP_GOAL:
            from telegram_bot.voice.goal_resolver import (
                GoalResolver,
                ResolveStatus as GoalResolveStatus,
            )

            action = dialog.slots.get('goal_action')
            if action == GOAL_ACTION_CREATE:
                title = text.strip()
                if title:
                    dialog.slots['goal_title'] = title
                return

            for candidate in voice_text_parse_candidates(text):
                parsed = await sync_to_async(VoiceInterpreter(user).interpret)(
                    candidate,
                )
                if parsed.goal is not None:
                    dialog.slots['goal_id'] = parsed.goal.id
                    dialog.slots['goal_title'] = parsed.goal.title
                    dialog.slots['goal_label'] = parsed.goal.title
                    if parsed.amount is not None:
                        dialog.slots['amount'] = parsed.amount
                    if parsed.goal_action:
                        dialog.slots['goal_action'] = parsed.goal_action
                    return
                if parsed.goal_title:
                    dialog.slots['goal_title'] = parsed.goal_title

            resolved = await sync_to_async(GoalResolver(user).resolve)(text)
            if resolved.status == GoalResolveStatus.MATCHED and resolved.match:
                goal = resolved.match
                dialog.slots['goal_id'] = goal.id
                dialog.slots['goal_title'] = goal.title
                dialog.slots['goal_label'] = goal.title
            else:
                dialog.slots['goal_title'] = text

    def _missing_from_slots(
        self,
        slots: dict[str, Any],
        *,
        intent: str = '',
    ) -> list[str]:
        is_budget = intent == VoiceIntentType.SET_BUDGET.value
        is_goal = intent == VoiceIntentType.MANAGE_GOAL.value
        missing: list[str] = []
        if is_goal:
            action = slots.get('goal_action')
            if not action:
                missing.append('goal_action')
                return missing
            if action == GOAL_ACTION_CREATE:
                if not slots.get('goal_title'):
                    missing.append('goal')
                if slots.get('amount') is None:
                    missing.append('amount')
                return missing
            if slots.get('amount') is None:
                missing.append('amount')
            if not slots.get('goal_id'):
                missing.append('goal')
            return missing

        if slots.get('amount') is None:
            missing.append('amount')
        if not is_budget and not slots.get('transaction_type'):
            missing.append('transaction_type')
        has_id = slots.get('category_id') is not None
        has_name = bool(slots.get('category_name'))
        if is_budget:
            if not has_id:
                missing.append('category')
        elif has_name and not has_id:
            missing.append('category')
        return missing

    async def _finish(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        telegram_user,
        slots: dict[str, Any],
        transcript: str,
    ) -> None:
        from categories.models import Category
        from goals.models import Goal

        command = slots_to_command(slots, transcript)
        category_id = slots.get('category_id')
        if category_id is not None:
            user = await sync_to_async(lambda: telegram_user.user)()
            try:
                command.category = await Category.objects.aget(
                    id=category_id,
                    user=user,
                )
                command.category_name = command.category.name
                command.transaction_type = command.category.type
                command.command_type = 'amount_category'
            except Category.DoesNotExist:
                command.category = None

        goal_id = slots.get('goal_id')
        if goal_id is not None:
            user = await sync_to_async(lambda: telegram_user.user)()
            try:
                command.goal = await Goal.objects.aget(id=goal_id, user=user)
                command.goal_title = command.goal.title
            except Goal.DoesNotExist:
                command.goal = None

        if command.intent == VoiceIntentType.MANAGE_GOAL:
            if (
                command.goal_action in {GOAL_ACTION_DEPOSIT, GOAL_ACTION_WITHDRAW}
                and command.goal_title
                and not command.goal
                and command.amount is not None
            ):
                await self._executor.prompt_goal_resolution(
                    update,
                    context,
                    telegram_user,
                    command,
                )
                return
            await self._executor.execute_manage_goal(
                update,
                context,
                telegram_user,
                command,
            )
            return

        if command.intent == VoiceIntentType.SET_BUDGET:
            command.transaction_type = 'expense'
            if command.amount is None or command.category is None:
                if command.category_name and not command.category:
                    await self._executor.prompt_category_resolution(
                        update,
                        context,
                        telegram_user,
                        command,
                    )
                    return
                await self._executor.send_error(
                    update,
                    context,
                    'Не хватает данных для лимита. Пример: «лимит 5000 продукты».',
                    voice_transcript=transcript,
                )
                return
            await self._executor.execute_set_budget(
                update,
                context,
                telegram_user,
                command,
            )
            return

        if command.amount is None:
            await self._executor.send_error(
                update,
                context,
                'Сумма не распознана. Повторите, например: «500 продукты».',
                voice_transcript=transcript,
            )
            return

        if command.category is None and not command.category_name:
            command.command_type = 'amount_only'

        if (
            command.command_type == 'amount_category'
            and command.category_name
            and not command.category
        ):
            await self._executor.prompt_category_resolution(
                update,
                context,
                telegram_user,
                command,
            )
            return

        if (
            command.confidence < CONFIDENCE_AUTO_SAVE
            and command.category is not None
            and command.needs_confirmation()
        ):
            await self._executor.prompt_voice_confirmation(
                update,
                context,
                telegram_user,
                command,
            )
            return

        await self._executor.execute_create_transaction(
            update,
            context,
            telegram_user,
            command.to_executor_dict(),
            voice_transcript=transcript,
        )
