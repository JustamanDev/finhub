"""
Default categories for new users.

Single source of truth used by:
- Telegram bot user bootstrap
- management commands (create/backfill)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

from categories.models import (
    Category,
    DefaultCategoryTemplate,
)


@dataclass(frozen=True, slots=True)
class DefaultCategory:
    name: str
    icon: str
    color: str
    category_type: str


DEFAULT_CATEGORIES: tuple[DefaultCategory, ...] = (
    # Income (3)
    DefaultCategory(
        name="Зарплата",
        icon="💰",
        color="#00B894",
        category_type=Category.INCOME,
    ),
    DefaultCategory(
        name="Дополнительный доход",
        icon="💼",
        color="#0984E3",
        category_type=Category.INCOME,
    ),
    DefaultCategory(
        name="Прочие поступления",
        icon="🎁",
        color="#6C5CE7",
        category_type=Category.INCOME,
    ),
    # Expense (10)
    DefaultCategory(
        name="Продукты",
        icon="🥕",
        color="#FF6B6B",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Жильё",
        icon="🏠",
        color="#96CEB4",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Транспорт",
        icon="🚇",
        color="#4ECDC4",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Связь и интернет",
        icon="📱",
        color="#45B7D1",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Еда вне дома",
        icon="🍽",
        color="#FD79A8",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Одежда и обувь",
        icon="👕",
        color="#DDA0DD",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Здоровье",
        icon="💊",
        color="#FFEAA7",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Развлечения и досуг",
        icon="🎉",
        color="#6C5CE7",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Подарки",
        icon="🎁",
        color="#E17055",
        category_type=Category.EXPENSE,
    ),
    DefaultCategory(
        name="Разное",
        icon="🐙",
        color="#A0A0A0",
        category_type=Category.EXPENSE,
    ),
)


def iter_default_categories() -> Iterable[DefaultCategory]:
    templates = list(_get_default_template_queryset())

    if templates:
        return [
            DefaultCategory(
                name=t.name,
                icon=t.icon,
                color=t.color,
                category_type=t.type,
            )
            for t in templates
        ]

    return DEFAULT_CATEGORIES


def _get_default_template_queryset():
    return DefaultCategoryTemplate.objects.filter(is_active=True).order_by(
        "type",
        "sort_order",
        "name",
        "id",
    )


async def iter_default_categories_async() -> list[DefaultCategory]:
    """
    Async-safe version of iter_default_categories().
    """
    templates = await sync_to_async(
        lambda: list(_get_default_template_queryset()),
        thread_sensitive=True,
    )()

    if templates:
        return [
            DefaultCategory(
                name=t.name,
                icon=t.icon,
                color=t.color,
                category_type=t.type,
            )
            for t in templates
        ]

    return list(DEFAULT_CATEGORIES)


def ensure_default_categories(user: User) -> int:
    """
    Ensure default categories exist for a user (idempotent).

    Returns:
        int: number of newly created categories
    """
    created_count = 0
    for item in iter_default_categories():
        _, created = Category.objects.get_or_create(
            user=user,
            name=item.name,
            type=item.category_type,
            defaults={
                "icon": item.icon,
                "color": item.color,
                "is_active": True,
            },
        )
        if created:
            created_count += 1
    return created_count


async def ensure_default_categories_async(user: User) -> int:
    """
    Async version of ensure_default_categories() for bot runtime.
    """
    created_count = 0
    for item in await iter_default_categories_async():
        _, created = await Category.objects.aget_or_create(
            user=user,
            name=item.name,
            type=item.category_type,
            defaults={
                "icon": item.icon,
                "color": item.color,
                "is_active": True,
            },
        )
        if created:
            created_count += 1
    return created_count

