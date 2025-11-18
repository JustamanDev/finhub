from rest_framework import serializers
from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    transactions_count = serializers.SerializerMethodField()
    budget_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id',
            'name', 
            'type',
            'color',
            'icon',
            'is_active',
            'created_at',
            'transactions_count',
            'budget_info',
        ]
        read_only_fields = [
            'created_at',
        ]
        
    def get_transactions_count(self, obj):
        """Количество транзакций в категории"""
        return obj.transactions.count()
        
    def get_budget_info(self, obj):
        """Информация о текущем бюджете категории"""
        if obj.type != Category.EXPENSE:
            return None  # Бюджеты только для расходных категорий
        return obj.get_budget_info()
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data) 