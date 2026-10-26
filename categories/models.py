from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel


class Category(TimestampedModel):
    """
    Модель категории доходов и расходов.
    
    Представляет собой способ классификации финансовых транзакций.
    Каждая категория принадлежит конкретному пользователю и имеет тип
    (доход или расход).
    
    Attributes:
        name: Название категории
        type: Тип категории (доход или расход)
        color: Цвет для отображения в UI (HEX формат)
        icon: Эмодзи иконка категории
        user: Владелец категории
        is_active: Активна ли категория
        is_quick: Стоит ли в коротком меню ввода, если человек выбрал категории сам
    """
    INCOME = 'income'
    EXPENSE = 'expense'
    TYPE_CHOICES = [
        (INCOME, 'Доход'),
        (EXPENSE, 'Расход'),
    ]
    
    name = models.CharField('Название', max_length=100)
    type = models.CharField('Тип', max_length=10, choices=TYPE_CHOICES)
    color = models.CharField('Цвет', max_length=7, default='#007BFF')  # HEX
    icon = models.CharField('Иконка', max_length=50, default='💰')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories', verbose_name='Пользователь')
    is_active = models.BooleanField('Активна', default=True)
    is_quick = models.BooleanField(
        'В меню ввода',
        default=False,
        help_text='Если отмечена хотя бы одна категория этого типа, короткое меню показывает только отмеченные. Иначе бот берёт шесть самых частых за 30 дней.',
    )
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = [
            'type',
            'name',
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'user',
                    'name',
                    'type',
                ],
                name='unique_category_per_user',
            ),
        ]
        
    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"
        
    def get_current_budget(self, date=None):
        """
        Получает текущий активный бюджет для этой категории.
        
        Args:
            date: Дата для проверки (по умолчанию сегодня)
            
        Returns:
            Budget или None: Активный бюджет или None
        """
        from budgets.models import Budget
        return Budget.get_current_budget(self.user, self, date)
        
    def get_budget_info(self, date=None):
        """
        Получает полную информацию о бюджете категории.
        
        Args:
            date: Дата для проверки (по умолчанию сегодня)
            
        Returns:
            dict или None: Словарь с информацией о бюджете или None
        """
        budget = self.get_current_budget(date)
        if not budget:
            return None
            
        return {
            'budget_amount': budget.amount,
            'spent_amount': budget.spent_amount,
            'remaining_amount': budget.remaining_amount,
            'spent_percentage': round(budget.spent_percentage, 1),
            'remaining_percentage': round(budget.remaining_percentage, 1),
            'is_overspent': budget.is_overspent,
            'days_remaining': budget.days_remaining,
            'daily_budget_remaining': budget.daily_budget_remaining,
            'period_type': budget.get_period_type_display(),
            'start_date': budget.start_date,
            'end_date': budget.end_date,
        }
        
    @property
    def has_active_budget(self):
        """
        Проверяет есть ли активный бюджет на эту категорию.
        
        Returns:
            bool: True если есть активный бюджет
        """
        return self.get_current_budget() is not None


class DefaultCategoryTemplate(TimestampedModel):
    """
    Шаблон дефолтных категорий (управляется через админку).

    Используется для создания стартового набора категорий для новых пользователей.
    """

    name = models.CharField("Название", max_length=100)
    type = models.CharField("Тип", max_length=10, choices=Category.TYPE_CHOICES)
    color = models.CharField("Цвет", max_length=7, default="#007BFF")
    icon = models.CharField("Иконка", max_length=50, default="💰")
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Шаблон категории по умолчанию"
        verbose_name_plural = "Шаблоны категорий по умолчанию"
        ordering = [
            "type",
            "sort_order",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "type",
                    "name",
                ],
                name="unique_default_category_template",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.icon} {self.name} ({self.get_type_display()})"
