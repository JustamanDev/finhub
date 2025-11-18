import logging
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
from django.contrib.auth.models import User
from django.db.models import Sum, Q

from transactions.models import Transaction
from categories.models import Category

logger = logging.getLogger(__name__)


class ReportService:
    """Сервис для работы с отчетами"""
    
    def __init__(self, user: User):
        self.user = user
    
    async def get_monthly_report(
        self,
        year: int,
        month: int,
    ) -> Dict[str, any]:
        """
        Получает месячный отчет
        
        Args:
            year: Год
            month: Месяц (1-12)
            
        Returns:
            Словарь с данными отчета
        """
        # Получаем все категории пользователя
        categories = await self._get_user_categories()
        
        # Получаем транзакции за месяц
        transactions = await self._get_monthly_transactions(year, month)
        
        # Рассчитываем статистику по категориям
        category_stats = await self._calculate_category_stats(
            categories,
            transactions,
        )
        
        # Общая статистика
        total_income = sum(
            stat['income'] for stat in category_stats.values()
        )
        total_expenses = sum(
            stat['expense'] for stat in category_stats.values()
        )
        balance = total_income - total_expenses
        
        return {
            'year': year,
            'month': month,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'balance': balance,
            'categories': category_stats,
            'period_name': self._get_period_name(year, month),
        }
    
    async def _get_user_categories(self) -> List[Category]:
        """Получает все категории пользователя"""
        from asgiref.sync import sync_to_async
        
        return await sync_to_async(list)(
            Category.objects.filter(user=self.user)
        )
    
    async def _get_monthly_transactions(
        self,
        year: int,
        month: int,
    ) -> List[Transaction]:
        """Получает транзакции за месяц"""
        from asgiref.sync import sync_to_async
        
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        return await sync_to_async(list)(
            Transaction.objects.filter(
                user=self.user,
                date__gte=start_date,
                date__lt=end_date,
            )
        )
    
    async def _calculate_category_stats(
        self,
        categories: List[Category],
        transactions: List[Transaction],
    ) -> Dict[str, Dict]:
        """Рассчитывает статистику по категориям"""
        from asgiref.sync import sync_to_async
        
        stats = {}
        
        for category in categories:
            # Фильтруем транзакции для категории
            category_transactions = []
            for transaction in transactions:
                # Безопасно получаем category_id
                transaction_category_id = await sync_to_async(
                    lambda t: t.category_id
                )(transaction)
                
                if transaction_category_id == category.id:
                    category_transactions.append(transaction)
            
            # Рассчитываем статистику
            income = sum(
                t.amount for t in category_transactions if t.amount > 0
            )
            expense = abs(sum(
                t.amount for t in category_transactions if t.amount < 0
            ))
            
            # Рассчитываем баланс в зависимости от типа категории
            if category.type == 'income':
                # Для доходов: НЕТ остатка (доходы не имеют остатков)
                balance = 0
            else:
                # Для расходов: проверяем есть ли бюджет
                budget_info = await sync_to_async(category.get_budget_info)()
                print(f"DEBUG: Category {category.name}, budget_info: {budget_info}")  # Отладка
                if budget_info:
                    # Есть бюджет: баланс = остаток от бюджета
                    balance = budget_info['remaining_amount']
                else:
                    # Нет бюджета: баланс = 0 (нет лимита)
                    balance = 0
            
            stats[category.name] = {
                'category': category,
                'income': income,
                'expense': expense,
                'balance': balance,
                'transaction_count': len(category_transactions),
            }
        
        return stats
    
    def _get_period_name(self, year: int, month: int) -> str:
        """Получает название периода"""
        month_names = [
            'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
            'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'
        ]
        return f"{month_names[month-1]} {year}"
    
    async def get_available_periods(self) -> List[Dict[str, int]]:
        """Получает доступные периоды для отчетов"""
        from asgiref.sync import sync_to_async
        
        # Получаем все даты транзакций пользователя
        dates = await sync_to_async(list)(
            Transaction.objects.filter(user=self.user)
            .values_list('date', flat=True)
            .distinct()
            .order_by('date')
        )
        
        if not dates:
            # Если нет транзакций, возвращаем текущий месяц
            now = datetime.now()
            return [{'year': now.year, 'month': now.month}]
        
        # Группируем по годам и месяцам
        periods = set()
        for transaction_date in dates:
            periods.add((transaction_date.year, transaction_date.month))
        
        # Сортируем по дате
        sorted_periods = sorted(periods)
        
        return [
            {'year': year, 'month': month}
            for year, month in sorted_periods
        ] 