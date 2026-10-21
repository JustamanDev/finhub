from decimal import Decimal

from rest_framework import serializers
from .models import Transaction
from categories.models import Category
from categories.serializers import CategorySerializer
from transactions.currencies import RUB, base_for_user
from transactions.exchange import ExchangeRateUnavailable, apply_entered_amount


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
            'currency',
            'original_amount',
            'exchange_rate',
            'rate_date',
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
            'currency',
            'original_amount',
            'exchange_rate',
            'rate_date',
            'created_at',
            'updated_at',
        ]
        
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        currency = validated_data.pop('currency', RUB)
        entered = validated_data.pop('amount')
        transaction = Transaction(amount=entered, **validated_data)
        try:
            apply_entered_amount(
                transaction,
                entered,
                currency,
                base=base_for_user(transaction.user),
            )
        except ExchangeRateUnavailable as exc:
            raise serializers.ValidationError({'amount': str(exc)}) from exc
        transaction.save()
        return transaction

    def update(self, instance, validated_data):
        report_currency = instance.report_currency or RUB
        if 'amount' in validated_data and instance.currency == report_currency:
            validated_data['original_amount'] = validated_data['amount']
            validated_data['exchange_rate'] = Decimal('1')
        return super().update(instance, validated_data)
        
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
            'currency',
            'original_amount',
            'exchange_rate',
            'rate_date',
            'description',
            'category',
            'date',
        ]
        read_only_fields = [
            'original_amount',
            'exchange_rate',
            'rate_date',
        ]
        extra_kwargs = {
            'currency': {
                'required': False,
                'default': RUB,
                'help_text': 'Валюта поля amount при создании. В ответе amount уже в базовой валюте.',
            },
        }

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        currency = validated_data.pop('currency', RUB)
        entered = validated_data.pop('amount')
        transaction = Transaction(amount=entered, **validated_data)
        try:
            apply_entered_amount(
                transaction,
                entered,
                currency,
                base=base_for_user(transaction.user),
            )
        except ExchangeRateUnavailable as exc:
            raise serializers.ValidationError({'amount': str(exc)}) from exc
        transaction.save()
        return transaction 