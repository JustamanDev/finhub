import re
from decimal import (
    Decimal,
    InvalidOperation,
)
from typing import (
    Optional,
    Dict,
    Any,
)

from categories.models import Category


class TextCommandParser:
    """Парсер команд вида '500 кофе', '+1000 зарплата', 'п500'"""
    
    # Регулярки для разных форматов
    AMOUNT_CATEGORY_PATTERN = r'^([+-]?\d+(?:[.,]\d+)?)\s+(.+)$'
    AMOUNT_ONLY_PATTERN = r'^([+-]?\d+(?:[.,]\d+)?)$'
    ALIAS_PATTERN = r'^([а-я]\d+)$'
    CATEGORY_ONLY_PATTERN = r'^([а-яё\s]+)$'
    
    def __init__(self, user):
        self.user = user
        
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Парсит текстовую команду пользователя
        
        Args:
            text: Текст команды от пользователя
            
        Returns:
            Словарь с результатами парсинга:
            {
                'type': str - тип команды,
                'amount': Decimal | None - сумма,
                'category_name': str | None - название категории,
                'transaction_type': str | None - тип транзакции,
                'category': Category | None - объект категории,
                'success': bool - успешность парсинга,
                'error': str | None - текст ошибки,
            }
        """
        text = text.strip()
        
        try:
            # 1. Проверяем алиасы (п500, к200)
            if match := re.match(self.ALIAS_PATTERN, text.lower()):
                return self._parse_alias(match.group(1))
                
            # 2. Сумма + категория (500 кофе, +1000 зарплата)
            if match := re.match(self.AMOUNT_CATEGORY_PATTERN, text):
                amount_str, category_name = match.groups()
                return self._parse_amount_category(
                    amount_str,
                    category_name,
                )
                
            # 3. Только сумма (500, +1000)
            if match := re.match(self.AMOUNT_ONLY_PATTERN, text):
                amount_str = match.group(1)
                return self._parse_amount_only(amount_str)
                
            # 4. Только категория (кофе, продукты)
            if re.match(self.CATEGORY_ONLY_PATTERN, text.lower()):
                return self._parse_category_only(text)
                
            return {
                'type': 'unknown',
                'raw_text': text,
                'success': False,
                'error': 'Не понял команду. Попробуйте: "500 кофе" или просто "500"',
            }
            
        except Exception as e:
            return {
                'type': 'error',
                'success': False,
                'error': f'Ошибка парсинга: {str(e)}',
            }
    
    def _parse_alias(self, alias: str) -> Dict[str, Any]:
        """
        Парсинг алиаса: п500 → Продукты 500₽
        
        Args:
            alias: Алиас пользователя
            
        Returns:
            Результат парсинга алиаса
        """
        from telegram_bot.models import UserAlias
        
        try:
            telegram_user = self.user.telegramuser
            user_alias = UserAlias.objects.get(
                telegram_user=telegram_user,
                alias=alias,
            )
            
            return {
                'type': 'alias',
                'alias': alias,
                'amount': user_alias.amount,
                'category': user_alias.category,
                'transaction_type': user_alias.category.type,
                'success': True,
            }
        except UserAlias.DoesNotExist:
            return {
                'type': 'alias',
                'alias': alias,
                'success': False,
                'error': f'Алиас "{alias}" не найден',
            }
    
    def _parse_amount_category(
        self,
        amount_str: str,
        category_name: str,
    ) -> Dict[str, Any]:
        """
        Парсинг: 500 кофе, +1000 зарплата
        
        Args:
            amount_str: Строка с суммой
            category_name: Название категории
            
        Returns:
            Результат парсинга суммы и категории
        """
        try:
            # Обрабатываем запятые как точки
            amount_str = amount_str.replace(',', '.')
            amount = Decimal(amount_str)
            
            # Определяем тип транзакции
            if amount_str.startswith('+'):
                # Явно указан доход
                transaction_type = 'income'
            elif amount_str.startswith('-'):
                # Явно указан расход
                transaction_type = 'expense'
            else:
                # Определяем по категории
                transaction_type = self._determine_transaction_type(category_name)
            
            amount = abs(amount)  # Убираем знак, тип определяем отдельно
            
            # Ищем категорию по имени
            category = self._find_category(
                category_name,
                transaction_type,
            )
            
            return {
                'type': 'amount_category',
                'amount': amount,
                'category_name': category_name,
                'transaction_type': transaction_type,
                'category': category,
                'success': True,
            }
        except (ValueError, InvalidOperation):
            return {
                'type': 'amount_category',
                'success': False,
                'error': f'Неверная сумма: "{amount_str}"',
            }
    
    def _parse_amount_only(self, amount_str: str) -> Dict[str, Any]:
        """
        Парсинг: 500, +1000
        
        Args:
            amount_str: Строка с суммой
            
        Returns:
            Результат парсинга только суммы
        """
        try:
            amount_str = amount_str.replace(',', '.')
            amount = Decimal(amount_str)
            transaction_type = 'income' if amount_str.startswith('+') else 'expense'
            amount = abs(amount)
            
            return {
                'type': 'amount_only',
                'amount': amount,
                'transaction_type': transaction_type,
                'success': True,
            }
        except (ValueError, InvalidOperation):
            return {
                'type': 'amount_only',
                'success': False,
                'error': f'Неверная сумма: "{amount_str}"',
            }
    
    def _parse_category_only(self, category_name: str) -> Dict[str, Any]:
        """
        Парсинг: кофе, продукты (для умных предложений)
        
        Args:
            category_name: Название категории
            
        Returns:
            Результат парсинга только категории
        """
        expense_category = self._find_category(
            category_name,
            'expense',
        )
        income_category = self._find_category(
            category_name,
            'income',
        )
        
        return {
            'type': 'category_only',
            'category_name': category_name,
            'expense_category': expense_category,
            'income_category': income_category,
            'success': True,
        }
    
    def _determine_transaction_type(self, category_name: str) -> str:
        """
        Определяет тип транзакции по названию категории
        
        Args:
            category_name: Название категории
            
        Returns:
            'income' или 'expense'
        """
        # Категории доходов
        income_categories = {
            'зарплата', 'подработка', 'подарки', 'инвестиции', 'возврат',
            'salary', 'work', 'gifts', 'investments', 'refund',
        }
        
        # Категории расходов (по умолчанию)
        expense_categories = {
            'еда', 'продукты', 'кофе', 'одежда', 'транспорт', 'жилье',
            'здоровье', 'развлечения', 'техника', 'магазин', 'шопинг',
            'food', 'coffee', 'clothes', 'transport', 'health', 'entertainment',
        }
        
        category_lower = category_name.lower().strip()
        
        if category_lower in income_categories:
            return 'income'
        elif category_lower in expense_categories:
            return 'expense'
        else:
            # По умолчанию считаем расходом
            return 'expense'
    
    def _find_category(
        self,
        name: str,
        transaction_type: str,
    ) -> Optional[Category]:
        """
        Поиск категории по имени (без учета регистра)
        
        Args:
            name: Название категории для поиска
            transaction_type: Тип транзакции ('expense' или 'income')
            
        Returns:
            Найденная категория или None
        """
        # Приводим к нижнему регистру для поиска
        name_lower = name.lower().strip()
        
        categories = Category.objects.filter(
            user=self.user,
            type=transaction_type,
        )
        
        # Синонимы для категорий
        category_synonyms = {
            'еда': ['продукты', 'еда', 'питание', 'пища', 'кухня'],
            'жилье': ['жилье', 'дом', 'квартира', 'аренда', 'коммунальные'],
            'здоровье': ['здоровье', 'медицина', 'врач', 'лекарства', 'аптека'],
            'кофе': ['кофе', 'кафе', 'кофейня', 'напитки'],
            'одежда': ['одежда', 'вещи', 'магазин', 'шопинг'],
            'развлечения': ['развлечения', 'кино', 'театр', 'ресторан', 'бар'],
            'техника': ['техника', 'электроника', 'гаджеты', 'компьютер'],
            'транспорт': ['транспорт', 'такси', 'метро', 'автобус', 'машина'],
        }
        
        # Используем Python-логику для поиска
        for category in categories:
            category_name_lower = category.name.lower()
            
            # Точное совпадение
            if category_name_lower == name_lower:
                return category
            
            # Частичное совпадение
            if name_lower in category_name_lower or category_name_lower in name_lower:
                return category
            
            # Поиск по синонимам
            if category_name_lower in category_synonyms:
                synonyms = category_synonyms[category_name_lower]
                if name_lower in synonyms:
                    return category
        
        return None 