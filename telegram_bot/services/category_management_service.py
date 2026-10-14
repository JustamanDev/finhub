import logging
from typing import List, Optional, Dict
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from budgets.models import Budget
from categories.models import Category
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class CategoryManagementService:
    """Сервис для управления категориями"""
    
    def __init__(self, user: User):
        self.user = user
    
    async def get_user_categories(self) -> List[Category]:
        """Активные категории: их видно в меню и быстром вводе."""
        return await sync_to_async(list)(
            Category.objects.filter(
                user=self.user,
                is_active=True,
            ).order_by('type', 'name')
        )

    async def get_archived_categories(self) -> List[Category]:
        """Категории, скрытые из меню. Операции по ним остаются."""
        return await sync_to_async(list)(
            Category.objects.filter(
                user=self.user,
                is_active=False,
            ).order_by('type', 'name')
        )
    
    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        """Получает категорию по ID"""
        try:
            return await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
        except Category.DoesNotExist:
            return None
    
    async def save_category(self, category: Category) -> None:
        """Сохраняет категорию"""
        await sync_to_async(category.save)()
    
    async def create_category(
        self,
        name: str,
        category_type: str,
        icon: str = "💰",
    ) -> Category:
        """Создает новую категорию.

        Если такое имя уже лежит в архиве, категория возвращается в меню:
        уникальность имени не даёт завести вторую, а история должна остаться одной.
        """
        archived = await sync_to_async(
            lambda: Category.objects.filter(
                user=self.user,
                name=name,
                type=category_type,
                is_active=False,
            ).first(),
        )()
        if archived is not None:
            return await self.restore_category(archived.id, icon=icon)

        category = await sync_to_async(Category.objects.create)(
            user=self.user,
            name=name,
            type=category_type,
            icon=icon,
        )
        
        logger.info(
            f"Создана категория: {name} ({category_type}) "
            f"для пользователя {self.user.id}"
        )
        
        return category
    
    async def update_category(
        self,
        category_id: int,
        name: Optional[str] = None,
        icon: Optional[str] = None,
        category_type: Optional[str] = None,
    ) -> Optional[Category]:
        """Обновляет категорию"""
        try:
            category = await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
            
            update_fields = []
            
            if name is not None:
                category.name = name
                update_fields.append('name')
            
            if icon is not None:
                category.icon = icon
                update_fields.append('icon')
            
            if category_type is not None:
                category.type = category_type
                update_fields.append('type')
            
            if update_fields:
                await sync_to_async(category.save)(update_fields=update_fields)
                
                logger.info(
                    f"Обновлена категория {category_id}: "
                    f"{', '.join(update_fields)}"
                )
            
            return category
            
        except Category.DoesNotExist:
            logger.warning(f"Категория {category_id} не найдена")
            return None
    
    async def archive_category(self, category_id: int) -> Optional[Category]:
        """Прячет категорию из меню. Транзакции и прошлые суммы не трогает."""
        try:
            category = await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
        except Category.DoesNotExist:
            logger.warning(f"Категория {category_id} не найдена")
            return None

        category.is_active = False
        await sync_to_async(category.save)(update_fields=['is_active', 'updated_at'])
        await self._set_open_budgets_active(category, active=False)
        logger.info(f"Категория в архиве: {category.name}")
        return category

    async def restore_category(
        self,
        category_id: int,
        icon: Optional[str] = None,
    ) -> Optional[Category]:
        """Возвращает категорию в меню и снова включает её текущий лимит."""
        try:
            category = await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
        except Category.DoesNotExist:
            logger.warning(f"Категория {category_id} не найдена")
            return None

        category.is_active = True
        update_fields = ['is_active', 'updated_at']
        if icon:
            category.icon = icon
            update_fields.append('icon')
        await sync_to_async(category.save)(update_fields=update_fields)
        await self._set_open_budgets_active(category, active=True)
        logger.info(f"Категория возвращена из архива: {category.name}")
        return category

    async def delete_category(self, category_id: int) -> bool:
        """Совместимое имя: категория уходит в архив, а не удаляется из базы."""
        return await self.archive_category(category_id) is not None

    async def _set_open_budgets_active(self, category: Category, *, active: bool) -> None:
        """Текущие и будущие лимиты категории. Прошлые периоды не переписываем."""
        from django.utils import timezone

        today = timezone.localdate()

        def _update() -> None:
            Budget.objects.filter(
                user=self.user,
                category=category,
                end_date__gte=today,
            ).update(is_active=active)

        await sync_to_async(_update)()
    
    async def get_category_stats(self, category_id: int) -> Optional[Dict]:
        """Получает статистику по категории"""
        try:
            category = await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
            
            # Получаем транзакции за последние 3 месяца
            from datetime import date, timedelta
            three_months_ago = date.today() - timedelta(days=90)
            
            transactions = await sync_to_async(list)(
                Transaction.objects.filter(
                    category=category,
                    date__gte=three_months_ago,
                ).order_by('-date')
            )
            
            total_amount = sum(t.amount for t in transactions)
            transaction_count = len(transactions)
            
            return {
                'category': category,
                'total_amount': total_amount,
                'transaction_count': transaction_count,
                'last_transaction': transactions[0] if transactions else None,
            }
            
        except Category.DoesNotExist:
            return None
    
    async def get_available_icons(self) -> List[str]:
        """Возвращает список доступных иконок"""
        return [
            "💰", "💸", "🏠", "🚗", "🍔", "🎉", "📱", "💻", "🎓", "💊",
            "🏃", "🎁", "👕", "🚌", "⛽", "☕", "🎨", "🧠", "🍽️", "🏍️",
            "👩‍🦰", "✍️", "🍰", "🏥", "💪", "💵", "🔒", "🍀", "🥕", "🚽",
            "⚓", "✈️", "🐿️", "🐙", "🥰", "🥋", "🛵", "🍽️", "🍰", "💪",
        ] 