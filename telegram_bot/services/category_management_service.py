import logging
from typing import List, Optional, Dict
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async

from categories.models import Category
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class CategoryManagementService:
    """Сервис для управления категориями"""
    
    def __init__(self, user: User):
        self.user = user
    
    async def get_user_categories(self) -> List[Category]:
        """Получает все категории пользователя"""
        return await sync_to_async(list)(
            Category.objects.filter(user=self.user).order_by('type', 'name')
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
        """Создает новую категорию"""
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
    
    async def delete_category(self, category_id: int) -> bool:
        """Удаляет категорию"""
        try:
            category = await Category.objects.aget(
                id=category_id,
                user=self.user,
            )
            
            # Проверяем, есть ли транзакции в этой категории
            transaction_count = await sync_to_async(
                Transaction.objects.filter(category=category).count
            )()
            
            if transaction_count > 0:
                logger.warning(
                    f"Нельзя удалить категорию {category_id}: "
                    f"есть {transaction_count} транзакций"
                )
                return False
            
            # Удаляем категорию
            await sync_to_async(category.delete)()
            
            logger.info(f"Удалена категория: {category.name}")
            return True
            
        except Category.DoesNotExist:
            logger.warning(f"Категория {category_id} не найдена")
            return False
    
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