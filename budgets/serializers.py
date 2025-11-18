from rest_framework import serializers
from .models import Budget
from categories.models import Category


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    
    # План-факт поля (только для чтения)
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    spent_percentage = serializers.FloatField(read_only=True)
    remaining_percentage = serializers.FloatField(read_only=True)
    is_overspent = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    days_total = serializers.IntegerField(read_only=True)
    daily_budget_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Budget
        fields = [
            'id',
            'category',
            'category_name',
            'category_icon',
            'category_color',
            'amount',
            'period_type',
            'start_date',
            'end_date',
            'is_active',
            'spent_amount',
            'remaining_amount',
            'spent_percentage',
            'remaining_percentage',
            'is_overspent',
            'days_remaining',
            'days_total',
            'daily_budget_remaining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'created_at',
            'updated_at',
        ]
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
        
    def validate_category(self, value):
        """Проверка что категория принадлежит пользователю и это расходная категория"""
        if value.user != self.context['request'].user:
            raise serializers.ValidationError("Вы можете использовать только свои категории.")
        if value.type != Category.EXPENSE:
            raise serializers.ValidationError("Бюджеты можно создавать только для расходных категорий.")
        if not value.is_active:
            raise serializers.ValidationError("Категория неактивна.")
        return value
        
    def validate(self, data):
        """Проверка на пересечение дат для одной категории"""
        user = self.context['request'].user
        category = data['category']
        start_date = data['start_date']
        end_date = data.get('end_date') or start_date
        
        # Проверяем пересечения только при создании или изменении дат
        queryset = Budget.objects.filter(
            user=user,
            category=category,
            is_active=True
        )
        
        # Исключаем текущий объект при обновлении
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        # Проверяем пересечения дат
        overlapping = queryset.filter(
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        if overlapping.exists():
            raise serializers.ValidationError(
                "У этой категории уже есть активный бюджет на указанный период."
            )
            
        return data


class BudgetCreateSerializer(serializers.ModelSerializer):
    """Упрощенный serializer для быстрого создания месячного бюджета"""
    
    class Meta:
        model = Budget
        fields = [
            'category',
            'amount',
            'start_date',
        ]
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['period_type'] = Budget.MONTHLY
        
        # Автоматически вычисляем end_date для месячного бюджета
        start_date = validated_data['start_date']
        budget = Budget(
            user=validated_data['user'],
            category=validated_data['category'],
            amount=validated_data['amount'],
            period_type=Budget.MONTHLY,
            start_date=start_date
        )
        # save() автоматически установит end_date
        budget.save()
        return budget


class CategoryBudgetInfoSerializer(serializers.Serializer):
    """Serializer для отображения информации о бюджете категории"""
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    category_icon = serializers.CharField()
    category_color = serializers.CharField()
    
    # Информация о бюджете (может быть None)
    has_budget = serializers.BooleanField()
    budget_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    spent_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    spent_percentage = serializers.FloatField(allow_null=True)
    remaining_percentage = serializers.FloatField(allow_null=True)
    is_overspent = serializers.BooleanField(allow_null=True)
    days_remaining = serializers.IntegerField(allow_null=True)
    daily_budget_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    period_type = serializers.CharField(allow_null=True) 