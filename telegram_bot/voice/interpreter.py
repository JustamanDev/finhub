"""Разбор транскрипта: regex fast path + LLM structured output."""

from __future__ import annotations

import json
import logging
import re
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth.models import User
from categories.models import Category
from telegram_bot.utils.text_parser import TextCommandParser
from telegram_bot.voice.config import openai_api_key, voice_llm_model
from telegram_bot.voice.openai_client import format_openai_error, get_openai_client
from telegram_bot.voice.intents import (
    ParsedVoiceCommand,
    VoiceIntentType,
)
from telegram_bot.voice.metrics import log_voice_event, timed_ms
from telegram_bot.voice.number_words import replace_spoken_numbers

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / 'prompts' / 'voice_command.txt'
MAX_LLM_RETRIES = 3

INTENT_MAP = {
    'create_transaction': VoiceIntentType.CREATE_TRANSACTION,
    'set_budget': VoiceIntentType.SET_BUDGET,
    'manage_goal': VoiceIntentType.MANAGE_GOAL,
    'ask_advisor': VoiceIntentType.ASK_ADVISOR,
    'unknown': VoiceIntentType.UNKNOWN,
}

RESPONSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'intent': {
            'type': 'string',
            'enum': list(INTENT_MAP.keys()),
        },
        'transaction_type': {
            'type': ['string', 'null'],
            'enum': ['expense', 'income', None],
        },
        'amount': {'type': ['number', 'null']},
        'category_name': {'type': ['string', 'null']},
        'goal_action': {
            'type': ['string', 'null'],
            'enum': ['deposit', 'withdraw', 'create', None],
        },
        'goal_title': {'type': ['string', 'null']},
        'description': {'type': 'string'},
        'confidence': {'type': 'number'},
    },
    'required': [
        'intent',
        'transaction_type',
        'amount',
        'category_name',
        'goal_action',
        'goal_title',
        'description',
        'confidence',
    ],
    'additionalProperties': False,
}

NATURAL_VOICE_RE = re.compile(
    r'(?i)^(?:добавь|запиши|создай|потрать|расход)\s+'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?\s*)?'
    r'(?:в\s+)?(?:категори(?:ю|и)\s+)?(.+?)[.\s]*$'
)

NATURAL_INCOME_VOICE_RE = re.compile(
    r'(?i)^(?:получил|заработал|доход|зачисли|пришло)\s+'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?\s*)?'
    r'(?:(?:на\s+)?(?:категори(?:ю|и)\s+)?(.+?))?[.\s]*$'
)

NATURAL_INCOME_NOUN_RE = re.compile(
    r'(?i)^(?:зарплата|заработок)\s+'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?\s*)?'
    r'(.+?)?[.\s]*$'
)

# «лимит 5000 продукты» OR «бюджет на кафе 5000» OR «лимит на транспорт»
BUDGET_VOICE_RE = re.compile(
    r'(?i)^(?:лимит|бюджет|установи\s+лимит|установи\s+бюджет|'
    r'задай\s+лимит|задай\s+бюджет|поставь\s+лимит|поставь\s+бюджет)\s+'
    r'(?:'
    # amount-first: «5000 на продукты», «5000 рублей кафе»
    r'(?:на\s+)?'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?\s*)?'
    r'(?:(?:на\s+)?(?:категори(?:ю|и)\s+)?(.+?))?'
    r'|'
    # category-first: «на категорию кафе 5000», «на транспорт 5000»
    r'(?:на\s+)?(?:категори(?:ю|и)\s+)?(.+?)\s+'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?)?'
    r'|'
    # category-only: «на транспорт», «на категорию кафе»
    r'(?:на\s+)?(?:категори(?:ю|и)\s+)?(.+?)'
    r')'
    r'[.\s]*$'
)

# «создай цель отпуск 100000», «новая цель iPad на 50000»
GOAL_CREATE_RE = re.compile(
    r'(?i)^(?:создай|новая|заведи)\s+цель\s+'
    r'(.+?)\s+'
    r'(?:на\s+)?'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?)?[.\s]*$'
)

# «пополни цель отпуск на 5000», «пополни отпуск 5000»
GOAL_DEPOSIT_RE = re.compile(
    r'(?i)^(?:пополни|внеси|положи|закинь)\s+'
    r'(?:цель\s+)?'
    r'(.+?)\s+'
    r'(?:на\s+)?'
    r'(\d+(?:[.,]\d+)?)\s*'
    r'(?:руб(?:лей|ля|ль)?\.?)?[.\s]*$'
)

# «сними 1000 с цели отпуск», «снять с отпуск 1000»
GOAL_WITHDRAW_RE = re.compile(
    r'(?i)^(?:сними|снять|выведи|вывести)\s+'
    r'(?:(\d+(?:[.,]\d+)?)\s*)?'
    r'(?:руб(?:лей|ля|ль)?\.?\s*)?'
    r'(?:с\s+)?(?:цели?\s+)?'
    r'(.+?)'
    r'(?:\s+(?:на\s+)?(\d+(?:[.,]\d+)?))?\s*'
    r'(?:руб(?:лей|ля|ль)?\.?)?[.\s]*$'
)


def _normalize_transcript(text: str) -> str:
    cleaned = text.strip().replace('\u00a0', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


def _clean_budget_category_name(name: str) -> str:
    """Strip quotes, trailing amount crumbs, filler words from category span."""
    cleaned = (name or '').strip().strip('«»"\'.,;:')
    cleaned = re.sub(
        r'(?i)\s+\d+(?:[.,]\d+)?\s*(?:руб(?:лей|ля|ль)?\.?)?\s*$',
        '',
        cleaned,
    ).strip()
    cleaned = cleaned.strip('«»"\'.,;:')
    if cleaned.lower() in {'на', 'для', 'категорию', 'категории', 'категория'}:
        return ''
    return cleaned


def _compact_natural_phrase(text: str) -> str | None:
    """«Добавь 500 рублей в категорию мобильный» → «500 мобильный»."""
    match = NATURAL_VOICE_RE.match(text)
    if not match:
        return None
    amount, category = match.groups()
    return f'{amount} {category.strip().strip(".")}'


def _compact_natural_income_phrase(text: str) -> str | None:
    """«Получил 5000 зарплата» → «+5000 зарплата», «зарплата 5000» → «+5000»."""
    for pattern in (NATURAL_INCOME_VOICE_RE, NATURAL_INCOME_NOUN_RE):
        match = pattern.match(text)
        if not match:
            continue
        amount, category = match.groups()
        category = (category or '').strip().strip('.')
        if category:
            return f'+{amount} {category}'
        return f'+{amount}'
    return None


def voice_text_parse_candidates(text: str) -> list[str]:
    """Candidate strings for parsing voice-derived text in text flows."""
    from telegram_bot.voice.number_words import replace_spoken_numbers

    candidates = [text]
    expanded = replace_spoken_numbers(text)
    if expanded and expanded not in candidates:
        candidates.append(expanded)
    for compact in (
        _compact_natural_phrase(text),
        _compact_natural_income_phrase(text),
        _compact_natural_phrase(expanded) if expanded != text else None,
        _compact_natural_income_phrase(expanded) if expanded != text else None,
    ):
        if compact and compact not in candidates:
            candidates.append(compact)
    return candidates


class VoiceInterpreter:
    def __init__(self, user: User):
        self.user = user
        self._parser = TextCommandParser(user)

    def interpret(self, transcript: str) -> ParsedVoiceCommand:
        text = _normalize_transcript(transcript)
        if not text:
            return ParsedVoiceCommand(
                intent=VoiceIntentType.UNKNOWN,
                success=False,
                confidence=0.0,
                raw_transcript=transcript,
                error='Пустая транскрипция.',
            )

        expanded = replace_spoken_numbers(text)
        # Prefer digit-expanded form first so «лимит пять тысяч …» hits budget regex.
        candidates = []
        if expanded != text:
            candidates.append(expanded)
        candidates.append(text)

        for candidate in candidates:
            fast = self._try_regex_fast_path(candidate)
            if fast:
                fast.raw_transcript = text
                log_voice_event(
                    'interpret',
                    path='regex',
                    intent=fast.intent.value,
                    spoken_numbers=int(expanded != text),
                )
                return fast

        logger.info('Voice LLM fallback for transcript: %r', text)
        with timed_ms() as timing:
            command = self._interpret_with_llm(expanded if expanded != text else text)
        if command.raw_transcript != text:
            command.raw_transcript = text
        log_voice_event(
            'interpret',
            path='llm',
            intent=command.intent.value,
            llm_ms=timing.get('ms'),
            spoken_numbers=int(expanded != text),
            confidence=round(command.confidence, 3),
        )
        return command

    def _try_regex_fast_path(self, text: str) -> ParsedVoiceCommand | None:
        budget = self._try_budget_fast_path(text)
        if budget:
            return budget

        goal = self._try_goal_fast_path(text)
        if goal:
            return goal

        candidates = (
            text,
            _compact_natural_phrase(text),
            _compact_natural_income_phrase(text),
        )
        for candidate in candidates:
            if not candidate:
                continue
            parsed = self._parser.parse(candidate)
            if not parsed.get('success'):
                continue
            if parsed['type'] == 'amount_category':
                return ParsedVoiceCommand(
                    intent=VoiceIntentType.CREATE_TRANSACTION,
                    success=True,
                    confidence=1.0,
                    raw_transcript=text,
                    transaction_type=parsed['transaction_type'],
                    amount=parsed['amount'],
                    category_name=parsed.get('category_name'),
                    category=parsed.get('category'),
                    description=parsed.get('description') or '',
                    command_type='amount_category',
                )
            if parsed['type'] == 'amount_only':
                return ParsedVoiceCommand(
                    intent=VoiceIntentType.CREATE_TRANSACTION,
                    success=True,
                    confidence=1.0,
                    raw_transcript=text,
                    transaction_type=parsed['transaction_type'],
                    amount=parsed['amount'],
                    command_type='amount_only',
                )
        return None

    def _try_budget_fast_path(self, text: str) -> ParsedVoiceCommand | None:
        match = BUDGET_VOICE_RE.match(text)
        if not match:
            return None
        amount_first, cat_after_amount, cat_before_amount, amount_after, cat_only = (
            match.groups()
        )
        amount_raw = amount_first or amount_after
        category_name = (
            cat_after_amount or cat_before_amount or cat_only or ''
        ).strip()
        category_name = _clean_budget_category_name(category_name)

        amount: Decimal | None = None
        if amount_raw:
            try:
                amount = Decimal(amount_raw.replace(',', '.')).copy_abs()
            except (InvalidOperation, ValueError):
                return None
            if amount <= 0:
                return None

        if amount is None and not category_name:
            return None

        category = None
        if category_name:
            from telegram_bot.voice.category_resolver import (
                CategoryResolver,
                ResolveStatus,
            )

            resolved = CategoryResolver(self.user).resolve(
                category_name,
                'expense',
            )
            if resolved.status == ResolveStatus.MATCHED:
                category = resolved.match

        return ParsedVoiceCommand(
            intent=VoiceIntentType.SET_BUDGET,
            success=True,
            confidence=1.0,
            raw_transcript=text,
            transaction_type='expense',
            amount=amount,
            category_name=category_name or None,
            category=category,
            command_type='amount_category' if category_name else (
                'amount_only' if amount is not None else None
            ),
        )

    def _try_goal_fast_path(self, text: str) -> ParsedVoiceCommand | None:
        from telegram_bot.voice.goal_resolver import GoalResolver, ResolveStatus
        from telegram_bot.voice.intents import (
            GOAL_ACTION_CREATE,
            GOAL_ACTION_DEPOSIT,
            GOAL_ACTION_WITHDRAW,
        )

        create_match = GOAL_CREATE_RE.match(text)
        if create_match:
            title_raw, amount_raw = create_match.groups()
            title = (title_raw or '').strip().strip('.')
            try:
                amount = Decimal(amount_raw.replace(',', '.')).copy_abs()
            except (InvalidOperation, ValueError):
                return None
            if not title or amount <= 0:
                return None
            return ParsedVoiceCommand(
                intent=VoiceIntentType.MANAGE_GOAL,
                success=True,
                confidence=1.0,
                raw_transcript=text,
                amount=amount,
                goal_action=GOAL_ACTION_CREATE,
                goal_title=title,
            )

        deposit_match = GOAL_DEPOSIT_RE.match(text)
        if deposit_match:
            title_raw, amount_raw = deposit_match.groups()
            title = (title_raw or '').strip().strip('.')
            # Avoid matching «пополни категорию …» style — require non-empty title
            if title.lower() in {'цель', 'категорию', 'категория'}:
                return None
            try:
                amount = Decimal(amount_raw.replace(',', '.')).copy_abs()
            except (InvalidOperation, ValueError):
                return None
            if not title or amount <= 0:
                return None
            goal = None
            resolved = GoalResolver(self.user).resolve(title)
            if resolved.status == ResolveStatus.MATCHED:
                goal = resolved.match
            return ParsedVoiceCommand(
                intent=VoiceIntentType.MANAGE_GOAL,
                success=True,
                confidence=1.0,
                raw_transcript=text,
                amount=amount,
                goal_action=GOAL_ACTION_DEPOSIT,
                goal_title=title,
                goal=goal,
            )

        withdraw_match = GOAL_WITHDRAW_RE.match(text)
        if withdraw_match:
            amount_a, title_raw, amount_b = withdraw_match.groups()
            amount_raw = amount_a or amount_b
            title = (title_raw or '').strip().strip('.')
            if not amount_raw or not title:
                return None
            try:
                amount = Decimal(amount_raw.replace(',', '.')).copy_abs()
            except (InvalidOperation, ValueError):
                return None
            if amount <= 0:
                return None
            goal = None
            resolved = GoalResolver(self.user).resolve(title)
            if resolved.status == ResolveStatus.MATCHED:
                goal = resolved.match
            return ParsedVoiceCommand(
                intent=VoiceIntentType.MANAGE_GOAL,
                success=True,
                confidence=1.0,
                raw_transcript=text,
                amount=amount,
                goal_action=GOAL_ACTION_WITHDRAW,
                goal_title=title,
                goal=goal,
            )
        return None

    def _interpret_with_llm(self, text: str) -> ParsedVoiceCommand:
        api_key = openai_api_key()
        if not api_key:
            return ParsedVoiceCommand(
                intent=VoiceIntentType.UNKNOWN,
                success=False,
                confidence=0.0,
                raw_transcript=text,
                error='OPENAI_API_KEY не задан.',
            )

        system_prompt = self._build_system_prompt()
        client = get_openai_client()
        model = voice_llm_model()
        last_error: Exception | None = None

        for attempt in range(1, MAX_LLM_RETRIES + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': text},
                    ],
                    response_format={
                        'type': 'json_schema',
                        'json_schema': {
                            'name': 'voice_command',
                            'strict': False,
                            'schema': RESPONSE_SCHEMA,
                        },
                    },
                )
                payload = json.loads(response.choices[0].message.content or '{}')
                return self._payload_to_command(text, payload)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    'LLM voice interpret attempt %s/%s failed: %s',
                    attempt,
                    MAX_LLM_RETRIES,
                    exc,
                )
                if attempt < MAX_LLM_RETRIES:
                    time.sleep(attempt)

        return ParsedVoiceCommand(
            intent=VoiceIntentType.UNKNOWN,
            success=False,
            confidence=0.0,
            raw_transcript=text,
            error=f'Не удалось разобрать команду: {format_openai_error(last_error)}',
        )

    def _build_system_prompt(self) -> str:
        from goals.models import Goal

        template = PROMPT_PATH.read_text(encoding='utf-8')
        categories = Category.objects.filter(user=self.user).order_by('type', 'name')
        lines = [
            f'- [{cat.type}] {cat.name}'
            for cat in categories
        ]
        categories_block = '\n'.join(lines) if lines else '(категорий пока нет)'
        goals = Goal.objects.filter(
            user=self.user,
            status=Goal.ACTIVE,
        ).order_by('-created_at')
        goal_lines = [f'- {goal.title}' for goal in goals]
        goals_block = '\n'.join(goal_lines) if goal_lines else '(целей пока нет)'
        return (
            template
            .replace('{{categories}}', categories_block)
            .replace('{{goals}}', goals_block)
        )

    def _payload_to_command(
        self,
        text: str,
        payload: dict,
    ) -> ParsedVoiceCommand:
        intent_raw = payload.get('intent', 'unknown')
        intent = INTENT_MAP.get(intent_raw, VoiceIntentType.UNKNOWN)
        confidence = float(payload.get('confidence', 0.0))
        confidence = max(0.0, min(1.0, confidence))

        if intent == VoiceIntentType.MANAGE_GOAL:
            from telegram_bot.voice.goal_resolver import GoalResolver, ResolveStatus
            from telegram_bot.voice.intents import (
                GOAL_ACTION_CREATE,
                GOAL_ACTION_DEPOSIT,
                GOAL_ACTION_WITHDRAW,
            )

            action_raw = (payload.get('goal_action') or '').strip().lower()
            goal_title = (payload.get('goal_title') or '').strip()
            amount_raw = payload.get('amount')
            amount: Decimal | None = None
            if amount_raw is not None:
                try:
                    amount = Decimal(str(amount_raw)).copy_abs()
                except (InvalidOperation, ValueError):
                    return ParsedVoiceCommand(
                        intent=VoiceIntentType.MANAGE_GOAL,
                        success=False,
                        confidence=0.0,
                        raw_transcript=text,
                        error='Не удалось распознать сумму для цели.',
                    )

            action = None
            if action_raw in {
                GOAL_ACTION_CREATE,
                GOAL_ACTION_DEPOSIT,
                GOAL_ACTION_WITHDRAW,
            }:
                action = action_raw

            goal = None
            if goal_title and action != GOAL_ACTION_CREATE:
                resolved = GoalResolver(self.user).resolve(goal_title)
                if resolved.status == ResolveStatus.MATCHED:
                    goal = resolved.match

            return ParsedVoiceCommand(
                intent=VoiceIntentType.MANAGE_GOAL,
                success=True,
                confidence=max(confidence, 0.6) if (
                    action or goal_title or amount is not None
                ) else confidence,
                raw_transcript=text,
                amount=amount,
                goal_action=action,
                goal_title=goal_title or None,
                goal=goal,
                description=(payload.get('description') or '').strip(),
            )

        if intent == VoiceIntentType.SET_BUDGET:
            amount_raw = payload.get('amount')
            category_name = (payload.get('category_name') or '').strip()
            amount: Decimal | None = None
            if amount_raw is not None:
                try:
                    amount = Decimal(str(amount_raw)).copy_abs()
                except (InvalidOperation, ValueError):
                    return ParsedVoiceCommand(
                        intent=VoiceIntentType.SET_BUDGET,
                        success=False,
                        confidence=0.0,
                        raw_transcript=text,
                        error='Не удалось распознать сумму лимита.',
                    )

            category = None
            if category_name:
                from telegram_bot.voice.category_resolver import (
                    CategoryResolver,
                    ResolveStatus,
                )

                resolved = CategoryResolver(self.user).resolve(
                    category_name,
                    'expense',
                )
                if resolved.status == ResolveStatus.MATCHED:
                    category = resolved.match

            return ParsedVoiceCommand(
                intent=VoiceIntentType.SET_BUDGET,
                success=True,
                confidence=max(confidence, 0.6) if (
                    amount is not None or category_name
                ) else confidence,
                raw_transcript=text,
                transaction_type='expense',
                amount=amount,
                category_name=category_name or None,
                category=category,
                description=(payload.get('description') or '').strip(),
                command_type='amount_category' if category_name else (
                    'amount_only' if amount is not None else None
                ),
            )

        if intent != VoiceIntentType.CREATE_TRANSACTION:
            return ParsedVoiceCommand(
                intent=intent,
                success=intent != VoiceIntentType.UNKNOWN,
                confidence=confidence,
                raw_transcript=text,
                description=(payload.get('description') or '').strip(),
            )

        amount_raw = payload.get('amount')
        transaction_type = payload.get('transaction_type') or 'expense'
        category_name = (payload.get('category_name') or '').strip()

        amount: Decimal | None = None
        if amount_raw is not None:
            try:
                amount = Decimal(str(amount_raw)).copy_abs()
            except (InvalidOperation, ValueError):
                return ParsedVoiceCommand(
                    intent=VoiceIntentType.CREATE_TRANSACTION,
                    success=False,
                    confidence=0.0,
                    raw_transcript=text,
                    error='Не удалось распознать сумму.',
                )

        if amount is None:
            # Partial command (e.g. «зарплата») — dialog asks for amount.
            category = None
            if category_name:
                from telegram_bot.voice.category_resolver import (
                    CategoryResolver,
                    ResolveStatus,
                )

                resolved = CategoryResolver(self.user).resolve(
                    category_name,
                    transaction_type,
                )
                if resolved.status == ResolveStatus.MATCHED:
                    category = resolved.match
            return ParsedVoiceCommand(
                intent=VoiceIntentType.CREATE_TRANSACTION,
                success=True,
                confidence=max(confidence, 0.6),
                raw_transcript=text,
                transaction_type=transaction_type,
                amount=None,
                category_name=category_name or None,
                category=category,
                description=(payload.get('description') or '').strip(),
                command_type='amount_category' if category_name else None,
            )

        category = None
        if category_name:
            from telegram_bot.voice.category_resolver import (
                CategoryResolver,
                ResolveStatus,
            )

            resolved = CategoryResolver(self.user).resolve(
                category_name,
                transaction_type,
            )
            if resolved.status == ResolveStatus.MATCHED:
                category = resolved.match

        command_type = 'amount_category' if category_name else 'amount_only'
        return ParsedVoiceCommand(
            intent=VoiceIntentType.CREATE_TRANSACTION,
            success=True,
            confidence=confidence,
            raw_transcript=text,
            transaction_type=transaction_type,
            amount=amount,
            category_name=category_name or None,
            category=category,
            description=(payload.get('description') or '').strip(),
            command_type=command_type,
        )
