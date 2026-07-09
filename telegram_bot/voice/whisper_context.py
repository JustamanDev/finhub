"""Build Whisper prompt hints from user categories / goals."""

from __future__ import annotations

from django.contrib.auth.models import User

from categories.models import Category
from goals.models import Goal
from telegram_bot.voice.config import whisper_prompt


def build_user_whisper_prompt(user: User, *, max_names: int = 40) -> str:
    """Combine env WHISPER_PROMPT with user category/goal names for bias."""
    base = whisper_prompt()
    names: list[str] = []
    categories = Category.objects.filter(user=user).order_by('name')[:max_names]
    names.extend(cat.name for cat in categories)
    goals = Goal.objects.filter(user=user, status=Goal.ACTIVE).order_by(
        '-created_at',
    )[:20]
    names.extend(goal.title for goal in goals)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)

    parts: list[str] = []
    if base:
        parts.append(base)
    if unique:
        parts.append(
            'Финансовые категории и цели: ' + ', '.join(unique[:max_names]) + '.',
        )
    # Whisper prompt max useful length is modest; keep under ~800 chars.
    combined = ' '.join(parts).strip()
    return combined[:800]
