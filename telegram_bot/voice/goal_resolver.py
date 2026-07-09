"""Fuzzy match of voice goal titles against the user's goals."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum

from django.contrib.auth.models import User

from goals.models import Goal

AUTO_SCORE = 0.85
AUTO_GAP = 0.15
CANDIDATE_MIN_SCORE = 0.55
MAX_CANDIDATES = 3


class ResolveStatus(str, Enum):
    MATCHED = 'matched'
    AMBIGUOUS = 'ambiguous'
    UNKNOWN = 'unknown'


@dataclass
class GoalCandidate:
    goal: Goal
    score: float


@dataclass
class ResolveResult:
    status: ResolveStatus
    match: Goal | None = None
    candidates: list[GoalCandidate] = field(default_factory=list)
    query: str = ''


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
        ratio = min(len(q), len(c)) / max(len(q), len(c))
        return max(0.75, 0.75 + 0.2 * ratio)
    return SequenceMatcher(None, q, c).ratio()


class GoalResolver:
    def __init__(self, user: User) -> None:
        self.user = user

    def resolve(self, query: str) -> ResolveResult:
        query = (query or '').strip()
        if not query:
            return ResolveResult(status=ResolveStatus.UNKNOWN, query=query)

        goals = list(
            Goal.objects.filter(user=self.user, status=Goal.ACTIVE).order_by(
                '-created_at',
            ),
        )
        if not goals:
            return ResolveResult(status=ResolveStatus.UNKNOWN, query=query)

        scored: list[GoalCandidate] = []
        for goal in goals:
            score = _score(query, goal.title)
            if score >= CANDIDATE_MIN_SCORE:
                scored.append(GoalCandidate(goal=goal, score=score))

        scored.sort(key=lambda item: item.score, reverse=True)
        candidates = scored[:MAX_CANDIDATES]
        if not candidates:
            return ResolveResult(status=ResolveStatus.UNKNOWN, query=query)

        best = candidates[0]
        second = candidates[1].score if len(candidates) > 1 else 0.0
        if best.score >= AUTO_SCORE and (best.score - second) >= AUTO_GAP:
            return ResolveResult(
                status=ResolveStatus.MATCHED,
                match=best.goal,
                candidates=candidates,
                query=query,
            )
        if len(candidates) == 1 and best.score >= AUTO_SCORE:
            return ResolveResult(
                status=ResolveStatus.MATCHED,
                match=best.goal,
                candidates=candidates,
                query=query,
            )
        if len(candidates) == 1 and best.score >= 0.75:
            return ResolveResult(
                status=ResolveStatus.MATCHED,
                match=best.goal,
                candidates=candidates,
                query=query,
            )
        return ResolveResult(
            status=ResolveStatus.AMBIGUOUS,
            candidates=candidates,
            query=query,
        )
