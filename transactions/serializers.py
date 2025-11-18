from rest_framework import serializers
from .models import Transaction
from categories.models import Category
from categories.serializers import CategorySerializer


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_type = serializers.CharField(source='category.type', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    is_income = serializers.BooleanField(read_only=True)
    is_expense = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id',
            'amount',
            'description',
            'category',
            'category_name',
            'category_type',
            'category_icon',
            'date',
            'is_income',
            'is_expense',
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
        """Проверка что категория принадлежит текущему пользователю"""
        if value.user != self.context['request'].user:
            raise serializers.ValidationError("Вы можете использовать только свои категории.")
        if not value.is_active:
            raise serializers.ValidationError("Категория неактивна.")
        return value


class TransactionCreateSerializer(serializers.ModelSerializer):
    """Упрощенный serializer для создания транзакций (например, из Telegram бота)"""
    
    class Meta:
        model = Transaction
        fields = [
            'amount',
            'description',
            'category',
            'date',
        ]
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data) 