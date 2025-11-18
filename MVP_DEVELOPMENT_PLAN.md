# 🚀 MVP Development Plan - FinHub

## 🎯 MVP ЦЕЛЬ

Создать функциональную систему учета личных доходов и расходов с категоризацией и базовой аналитикой.

## 📋 MVP SCOPE (Что включаем)

### ✅ ВКЛЮЧЕНО В MVP:
- Регистрация и авторизация пользователей
- Управление категориями доходов/расходов  
- Добавление/редактирование/удаление транзакций
- Просмотр списка транзакций с фильтрацией
- Базовая статистика (баланс, траты за период)
- Простая Django админка
- REST API для будущего фронтенда

### ❌ НЕ ВКЛЮЧЕНО В MVP:
- Telegram бот (этап 2)
- Сложная аналитика и графики (этап 3)
- Бюджеты и лимиты (этап 4)
- Финансовые цели (этап 5)
- Красивый фронтенд (этап 8)

## 🏗️ ПОШАГОВЫЙ ПЛАН MVP РАЗРАБОТКИ

### ШАГ 1: Настройка проекта и зависимостей (30 мин)

```bash
# Добавить зависимости
poetry add djangorestframework django-environ django-cors-headers django-filter

# Обновить settings.py
```

**Файлы для изменения:**
- `pyproject.toml` - добавить зависимости
- `finhub/settings.py` - настроить DRF и новые apps
- `finhub/urls.py` - добавить API routes

### ШАГ 2: Создание Django приложений (15 мин)

```bash
poetry run python manage.py startapp accounts
poetry run python manage.py startapp core  
poetry run python manage.py startapp categories
poetry run python manage.py startapp transactions
```

### ШАГ 3: Модели данных (1 час)

#### 3.1 Core models (`core/models.py`)
```python
from django.db import models

class TimestampedModel(models.Model):
    """Базовая модель с временными метками"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

#### 3.2 Categories models (`categories/models.py`)
```python
from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel

class Category(TimestampedModel):
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    is_active = models.BooleanField('Активна', default=True)
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        unique_together = ['user', 'name', 'type']
        
    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"
```

#### 3.3 Transactions models (`transactions/models.py`)
```python
from django.db import models
from django.contrib.auth.models import User
from core.models import TimestampedModel
from categories.models import Category

class Transaction(TimestampedModel):
    amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    description = models.TextField('Описание', blank=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.CASCADE, 
        related_name='transactions',
        verbose_name='Категория'
    )
    date = models.DateField('Дата')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    
    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-date', '-created_at']
        
    def __str__(self):
        return f"{self.amount} руб. - {self.category.name} ({self.date})"
        
    @property
    def is_income(self):
        return self.category.type == Category.INCOME
        
    @property
    def is_expense(self):
        return self.category.type == Category.EXPENSE
```

### ШАГ 4: Django Admin настройка (30 мин)

#### 4.1 Categories admin (`categories/admin.py`)
```python
from django.contrib import admin
from .models import Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'color', 'user', 'is_active', 'created_at']
    list_filter = ['type', 'is_active', 'created_at']
    search_fields = ['name', 'user__username']
    list_editable = ['is_active']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs
        
    def save_model(self, request, obj, form, change):
        if not change:  # Создание новой категории
            obj.user = request.user
        super().save_model(request, obj, form, change)
```

#### 4.2 Transactions admin (`transactions/admin.py`)
```python
from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['amount', 'category', 'description', 'date', 'user', 'created_at']
    list_filter = ['category__type', 'category', 'date', 'created_at']
    search_fields = ['description', 'category__name']
    date_hierarchy = 'date'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.filter(user=request.user, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)
```

### ШАГ 5: REST API (1.5 часа)

#### 5.1 Serializers (`categories/serializers.py`)
```python
from rest_framework import serializers
from .models import Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'type', 'color', 'icon', 'is_active', 'created_at']
        read_only_fields = ['created_at']
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
```

#### 5.2 ViewSets (`categories/views.py`)
```python
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category
from .serializers import CategorySerializer

class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)
        
    @action(detail=False, methods=['get'])
    def income(self, request):
        """Получить категории доходов"""
        categories = self.get_queryset().filter(type=Category.INCOME, is_active=True)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get']) 
    def expense(self, request):
        """Получить категории расходов"""
        categories = self.get_queryset().filter(type=Category.EXPENSE, is_active=True)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
```

### ШАГ 6: URL Configuration (15 мин)

#### 6.1 API URLs (`api/urls.py`)
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from categories.views import CategoryViewSet
from transactions.views import TransactionViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'transactions', TransactionViewSet, basename='transactions')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
]
```

### ШАГ 7: Первичные данные (30 мин)

#### 7.1 Management команда (`categories/management/commands/create_default_categories.py`)
```python
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from categories.models import Category

class Command(BaseCommand):
    help = 'Создать категории по умолчанию для пользователя'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Имя пользователя')
        
    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Пользователь {username} не найден'))
            return
            
        # Категории расходов
        expense_categories = [
            {'name': 'Продукты', 'icon': '🛒', 'color': '#FF6B6B'},
            {'name': 'Транспорт', 'icon': '🚗', 'color': '#4ECDC4'},
            {'name': 'Развлечения', 'icon': '🎬', 'color': '#45B7D1'},
            {'name': 'Коммунальные', 'icon': '🏠', 'color': '#96CEB4'},
            {'name': 'Здоровье', 'icon': '💊', 'color': '#FFEAA7'},
            {'name': 'Одежда', 'icon': '👕', 'color': '#DDA0DD'},
        ]
        
        # Категории доходов  
        income_categories = [
            {'name': 'Зарплата', 'icon': '💰', 'color': '#00B894'},
            {'name': 'Фриланс', 'icon': '💻', 'color': '#0984E3'},
            {'name': 'Инвестиции', 'icon': '📈', 'color': '#6C5CE7'},
        ]
        
        for cat_data in expense_categories:
            Category.objects.get_or_create(
                user=user,
                name=cat_data['name'],
                type=Category.EXPENSE,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color']
                }
            )
            
        for cat_data in income_categories:
            Category.objects.get_or_create(
                user=user,
                name=cat_data['name'], 
                type=Category.INCOME,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color']
                }
            )
            
        self.stdout.write(self.style.SUCCESS(f'Категории созданы для пользователя {username}'))
```

### ШАГ 8: Миграции и тестирование (30 мин)

```bash
# Создать и применить миграции
poetry run python manage.py makemigrations core
poetry run python manage.py makemigrations categories  
poetry run python manage.py makemigrations transactions
poetry run python manage.py migrate

# Создать суперпользователя
poetry run python manage.py createsuperuser

# Создать категории по умолчанию
poetry run python manage.py create_default_categories admin

# Запустить сервер
poetry run python manage.py runserver
```

### ШАГ 9: Базовая статистика (1 час)

#### 9.1 Analytics views (`transactions/views.py` - дополнение)
```python
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta

class TransactionViewSet(viewsets.ModelViewSet):
    # ... базовый код ...
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Базовая статистика по транзакциям"""
        queryset = self.get_queryset()
        
        # Текущий месяц
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        month_transactions = queryset.filter(date__gte=month_start)
        
        # Доходы и расходы за месяц
        month_income = month_transactions.filter(
            category__type=Category.INCOME
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        month_expense = month_transactions.filter(
            category__type=Category.EXPENSE  
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Общий баланс
        total_income = queryset.filter(
            category__type=Category.INCOME
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_expense = queryset.filter(
            category__type=Category.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'total_balance': total_income - total_expense,
            'month_income': month_income,
            'month_expense': month_expense,
            'month_balance': month_income - month_expense,
            'month_transactions_count': month_transactions.count(),
        })
```

## ✅ КРИТЕРИИ ГОТОВНОСТИ MVP

MVP считается готовым, когда:

- [ ] ✅ Пользователь может зарегистрироваться/войти
- [ ] ✅ Можно создавать категории доходов и расходов
- [ ] ✅ Можно добавлять/редактировать/удалять транзакции  
- [ ] ✅ Есть список транзакций с фильтрацией по дате/категории
- [ ] ✅ Работает базовая статистика (баланс, траты за месяц)
- [ ] ✅ API endpoints отвечают корректно
- [ ] ✅ Django админка функциональна
- [ ] ✅ Есть начальные категории для тестирования

## 🚀 ПОСЛЕ MVP

После завершения MVP можно переходить к этапу 2 - разработке Telegram бота для удобного внесения трат.

**Время разработки MVP: 4-6 часов активной работы** 