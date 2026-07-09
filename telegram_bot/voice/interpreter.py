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
        'description': {'type': 'string'},
        'confidence': {'type': 'number'},
    },
    'required': [
        'intent',
        'transaction_type',
        'amount',
        'category_name',
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


def _normalize_transcript(text: str) -> str:
    cleaned = text.strip().replace('\u00a0', ' ')
    cleaned = re.sub(r'\s+', ' ', cleaned)
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
    candidates = [text]
    for compact in (
        _compact_natural_phrase(text),
        _compact_natural_income_phrase(text),
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

        fast = self._try_regex_fast_path(text)
        if fast:
            return fast

        logger.info('Voice LLM fallback for transcript: %r', text)
        return self._interpret_with_llm(text)

    def _try_regex_fast_path(self, text: str) -> ParsedVoiceCommand | None:
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
        template = PROMPT_PATH.read_text(encoding='utf-8')
        categories = Category.objects.filter(user=self.user).order_by('type', 'name')
        lines = [
            f'- [{cat.type}] {cat.name}'
            for cat in categories
        ]
        categories_block = '\n'.join(lines) if lines else '(категорий пока нет)'
        return template.replace('{{categories}}', categories_block)

    def _payload_to_command(
        self,
        text: str,
        payload: dict,
    ) -> ParsedVoiceCommand:
        intent_raw = payload.get('intent', 'unknown')
        intent = INTENT_MAP.get(intent_raw, VoiceIntentType.UNKNOWN)
        confidence = float(payload.get('confidence', 0.0))
        confidence = max(0.0, min(1.0, confidence))

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
            return ParsedVoiceCommand(
                intent=VoiceIntentType.CREATE_TRANSACTION,
                success=False,
                confidence=min(confidence, 0.4),
                raw_transcript=text,
                error='Сумма не распознана. Повторите, например: «расход 300 продукты».',
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
