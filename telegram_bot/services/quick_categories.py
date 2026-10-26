"""Короткое меню категорий после ввода суммы.

Если человек сам отметил категории этого типа, меню показывает только их
(не больше шести). Если не отметил ни одной, берутся шесть самых частых
за последние 30 дней, а пустые места добиваются остальными по алфавиту.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db.models import Count

from categories.models import Category
from transactions.models import Transaction

QUICK_MENU_SIZE = 6
QUICK_WINDOW_DAYS = 30


@dataclass(frozen=True)
class QuickMenu:
    """Категории короткого меню и сколько активных есть у этого типа всего."""

    categories: list[Category]
    total_active: int
    manual: bool


def select_quick_categories(
    user: User,
    transaction_type: str,
    today: date,
) -> QuickMenu:
    """Шесть категорий для первого экрана после суммы."""
    active = list(
        Category.objects.filter(
            user=user,
            type=transaction_type,
            is_active=True,
        ).order_by('name'),
    )
    pinned = [category for category in active if category.is_quick][:QUICK_MENU_SIZE]
    if pinned:
        return QuickMenu(pinned, len(active), True)

    since = today - timedelta(days=QUICK_WINDOW_DAYS - 1)
    counts = (
        Transaction.objects.filter(
            user=user,
            category__in=active,
            date__gte=since,
            date__lte=today,
        )
        .values('category_id')
        .annotate(n=Count('id'))
        .order_by('-n', 'category__name')
    )
    by_id = {category.id: category for category in active}
    chosen: list[Category] = []
    for row in counts:
        category = by_id.get(row['category_id'])
        if category is None:
            continue
        chosen.append(category)
        if len(chosen) == QUICK_MENU_SIZE:
            break

    if len(chosen) < QUICK_MENU_SIZE:
        chosen_ids = {category.id for category in chosen}
        for category in active:
            if category.id in chosen_ids:
                continue
            chosen.append(category)
            if len(chosen) == QUICK_MENU_SIZE:
                break

    return QuickMenu(chosen, len(active), False)


def toggle_quick(user: User, category_id: int) -> tuple[Category | None, str | None]:
    """Ставит или снимает категорию с меню ввода.

    Второе значение — текст, если отметить нельзя: уже шесть или категории нет.
    """
    try:
        category = Category.objects.get(id=category_id, user=user, is_active=True)
    except Category.DoesNotExist:
        return None, 'Категория не найдена'

    if category.is_quick:
        category.is_quick = False
        category.save(update_fields=['is_quick', 'updated_at'])
        return category, None

    taken = Category.objects.filter(
        user=user,
        type=category.type,
        is_active=True,
        is_quick=True,
    ).count()
    if taken >= QUICK_MENU_SIZE:
        return category, 'В избранных уже шесть. Снимите одну, чтобы поставить эту.'

    category.is_quick = True
    category.save(update_fields=['is_quick', 'updated_at'])
    return category, None


def clear_quick(user: User, transaction_type: str) -> int:
    """Снимает ручной выбор. Меню снова собирается по частоте."""
    return Category.objects.filter(
        user=user,
        type=transaction_type,
        is_quick=True,
    ).update(is_quick=False)


def drop_quick_if_type_is_full(user: User, category: Category, new_type: str) -> bool:
    """Снимает отметку, если в новом типе свои шесть уже заняты.

    Возвращает True, когда отметку пришлось снять. Саму категорию не сохраняет:
    вызывающий пишет тип и отметку одним сохранением.
    """
    if not category.is_quick or category.type == new_type:
        return False
    taken = Category.objects.filter(
        user=user,
        type=new_type,
        is_active=True,
        is_quick=True,
    ).exclude(pk=category.pk).count()
    if taken < QUICK_MENU_SIZE:
        return False
    category.is_quick = False
    return True
