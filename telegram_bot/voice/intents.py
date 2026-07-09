"""Intent types and parsed voice command models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from categories.models import Category


class VoiceIntentType(str, Enum):
    CREATE_TRANSACTION = 'create_transaction'
    SET_BUDGET = 'set_budget'
    MANAGE_GOAL = 'manage_goal'
    ASK_ADVISOR = 'ask_advisor'
    UNKNOWN = 'unknown'


CONFIDENCE_AUTO_SAVE = 0.85
CONFIDENCE_CONFIRM = 0.5


@dataclass
class ParsedVoiceCommand:
    intent: VoiceIntentType
    success: bool
    confidence: float
    raw_transcript: str
    transaction_type: str | None = None
    amount: Decimal | None = None
    category_name: str | None = None
    category: Category | None = None
    description: str = ''
    error: str | None = None
    command_type: str | None = None

    def needs_confirmation(self) -> bool:
        if not self.success:
            return False
        if self.intent != VoiceIntentType.CREATE_TRANSACTION:
            return False
        if self.command_type == 'amount_only':
            return False
        if self.confidence < CONFIDENCE_CONFIRM:
            return False
        if self.confidence >= CONFIDENCE_AUTO_SAVE and self.category:
            return False
        return True

    def should_reject(self) -> bool:
        if not self.success:
            return True
        if self.intent == VoiceIntentType.SET_BUDGET:
            if self.confidence < CONFIDENCE_CONFIRM and (
                self.amount is None and not self.category_name and not self.category
            ):
                return True
            # Partial budget command → dialog, not hard reject.
            if self.amount is not None or self.category_name or self.category:
                return False
            return self.confidence < CONFIDENCE_CONFIRM
        if self.intent != VoiceIntentType.CREATE_TRANSACTION:
            return self.confidence < CONFIDENCE_CONFIRM
        # Partial create (missing amount) → dialog, not hard reject.
        if self.amount is None and (
            self.category_name or self.category or self.confidence >= CONFIDENCE_CONFIRM
        ):
            return False
        return self.confidence < CONFIDENCE_CONFIRM

    def to_executor_dict(self) -> dict[str, Any]:
        """Формат, совместимый с TextCommandParser / CommandExecutor."""
        if self.command_type == 'amount_only':
            return {
                'type': 'amount_only',
                'amount': self.amount,
                'transaction_type': self.transaction_type,
                'description': self.description,
                'success': True,
            }
        return {
            'type': 'amount_category',
            'amount': self.amount,
            'category_name': self.category_name,
            'transaction_type': self.transaction_type,
            'category': self.category,
            'description': self.description,
            'success': True,
        }
