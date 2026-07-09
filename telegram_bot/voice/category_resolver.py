"""Category resolution for voice (and shared text) matching.

State × Input → Action (Phase 1):

CREATE_TRANSACTION with category_name:
  MATCHED (exact/synonym/fuzzy auto) → set category, continue normal flow
  AMBIGUOUS (2+ close scores) → ask top-3 + «Все категории» + «Создать» + «Отмена»
  UNKNOWN (0 candidates) → «не найдена» + «Создать "X"» + «Выбрать» + «Отмена»

Callbacks:
  voice_cat_pick_{id} → bind category to pending command → create transaction
  voice_cat_all → full category keyboard (awaiting_category)
  voice_cat_create → awaiting_category_creation with pending amount
  voice_cancel → clear voice_category_pending
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Iterable

from django.contrib.auth.models import User

from categories.models import Category

# Auto-pick when best score is high enough and clearly ahead of #2.
AUTO_SCORE = 0.85
AUTO_GAP = 0.15
# Include in suggestion list.
CANDIDATE_MIN_SCORE = 0.55
MAX_CANDIDATES = 3

# Synonym key = normalized category name (or alias) → list of spoken forms.
# Keys should match common user category names (default templates + legacy).
CATEGORY_SYNONYMS: dict[str, list[str]] = {
    'продукты': ['продукты', 'еда', 'питание', 'пища', 'кухня', 'магазин'],
    'еда': ['еда', 'продукты', 'питание', 'пища'],
    'еда вне дома': ['еда вне дома', 'ресторан', 'кафе', 'обед', 'ужин', 'ланч'],
    'жильё': ['жилье', 'жильё', 'дом', 'квартира', 'аренда', 'коммунальные'],
    'жилье': ['жилье', 'жильё', 'дом', 'квартира', 'аренда', 'коммунальные'],
    'здоровье': ['здоровье', 'медицина', 'врач', 'лекарства', 'аптека'],
    'кофе': ['кофе', 'кафе', 'кофейня', 'напитки'],
    'одежда': ['одежда', 'вещи', 'шопинг'],
    'одежда и обувь': ['одежда', 'обувь', 'вещи', 'шопинг'],
    'развлечения': ['развлечения', 'кино', 'театр', 'бар'],
    'техника': ['техника', 'электроника', 'гаджеты', 'компьютер'],
    'транспорт': ['транспорт', 'такси', 'метро', 'автобус', 'машина', 'бензин'],
    'связь и интернет': [
        'связь',
        'интернет',
        'мобильный',
        'телефон',
        'связь и интернет',
    ],
    'зарплата': ['зарплата', 'зп', 'оклад', 'salary'],
    'дополнительный доход': [
        'дополнительный доход',
        'подработка',
        'фриланс',
        'халтура',
    ],
    'прочие поступления': ['подарки', 'возврат', 'прочие поступления'],
}


class ResolveStatus(str, Enum):
    MATCHED = 'matched'
    AMBIGUOUS = 'ambiguous'
    UNKNOWN = 'unknown'


@dataclass
class CategoryCandidate:
    category: Category
    score: float


@dataclass
class ResolveResult:
    status: ResolveStatus
    match: Category | None = None
    candidates: list[CategoryCandidate] = field(default_factory=list)
    query: str = ''

    @property
    def category(self) -> Category | None:
        return self.match


def _normalize(text: str) -> str:
    return ' '.join(text.lower().replace('ё', 'е').split())


def _score(query: str, candidate: str) -> float:
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c or c in q:
        # Prefer longer overlap relative to shorter string.
        ratio = min(len(q), len(c)) / max(len(q), len(c))
        return max(0.75, 0.75 + 0.2 * ratio)
    return SequenceMatcher(None, q, c).ratio()


def _synonym_hit(query: str, category_name: str) -> bool:
    q = _normalize(query)
    name = _normalize(category_name)
    synonyms = CATEGORY_SYNONYMS.get(name) or CATEGORY_SYNONYMS.get(category_name.lower())
    if not synonyms:
        # Also check if query is a key that maps to this category name.
        for key, values in CATEGORY_SYNONYMS.items():
            if _normalize(key) == name and q in {_normalize(v) for v in values}:
                return True
            if q == _normalize(key) and name in {_normalize(v) for v in values}:
                return True
        return False
    return q in {_normalize(v) for v in synonyms}


class CategoryResolver:
    def __init__(self, user: User):
        self.user = user

    def resolve(
        self,
        name: str,
        transaction_type: str,
        *,
        categories: Iterable[Category] | None = None,
    ) -> ResolveResult:
        query = (name or '').strip()
        if not query:
            return ResolveResult(status=ResolveStatus.UNKNOWN, query=query)

        if categories is None:
            qs = Category.objects.filter(user=self.user, type=transaction_type)
            category_list = list(qs)
        else:
            category_list = [
                c for c in categories if getattr(c, 'type', None) == transaction_type
            ]

        scored: list[CategoryCandidate] = []
        for category in category_list:
            if _normalize(category.name) == _normalize(query):
                return ResolveResult(
                    status=ResolveStatus.MATCHED,
                    match=category,
                    candidates=[CategoryCandidate(category, 1.0)],
                    query=query,
                )
            if _synonym_hit(query, category.name):
                scored.append(CategoryCandidate(category, 0.95))
                continue
            score = _score(query, category.name)
            if score >= CANDIDATE_MIN_SCORE:
                scored.append(CategoryCandidate(category, score))

        scored.sort(key=lambda item: item.score, reverse=True)
        # Deduplicate by category id keeping best score.
        seen: set[int] = set()
        unique: list[CategoryCandidate] = []
        for item in scored:
            if item.category.id in seen:
                continue
            seen.add(item.category.id)
            unique.append(item)

        if not unique:
            return ResolveResult(status=ResolveStatus.UNKNOWN, query=query)

        best = unique[0]
        second = unique[1].score if len(unique) > 1 else 0.0
        if best.score >= AUTO_SCORE and (best.score - second) >= AUTO_GAP:
            return ResolveResult(
                status=ResolveStatus.MATCHED,
                match=best.category,
                candidates=unique[:MAX_CANDIDATES],
                query=query,
            )

        if len(unique) == 1 and best.score >= AUTO_SCORE:
            return ResolveResult(
                status=ResolveStatus.MATCHED,
                match=best.category,
                candidates=unique[:MAX_CANDIDATES],
                query=query,
            )

        return ResolveResult(
            status=ResolveStatus.AMBIGUOUS,
            match=None,
            candidates=unique[:MAX_CANDIDATES],
            query=query,
        )
