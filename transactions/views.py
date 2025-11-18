from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import (
    Sum,
    Count,
    Q,
)
from django.utils import timezone
from datetime import (
    datetime,
    timedelta,
)
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import Transaction
from .serializers import TransactionSerializer, TransactionCreateSerializer
from categories.models import Category


# Strict rate limiting for financial operations
transaction_read_limit = ratelimit(key='user', rate='200/m', method='GET', block=True)
transaction_write_limit = ratelimit(key='user', rate='30/m', method=['POST', 'PUT', 'PATCH'], block=True)
transaction_delete_limit = ratelimit(key='user', rate='5/m', method='DELETE', block=True)


@extend_schema_view(
    list=extend_schema(
        summary="List user transactions",
        description="Get all financial transactions for the authenticated user with comprehensive filtering options.",
        tags=['Transactions'],
        parameters=[
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter by category ID'
            ),
            OpenApiParameter(
                name='category__type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by category type',
                enum=['income', 'expense']
            ),
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter by specific date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in transaction descriptions and category names'
            ),
        ]
    ),
    create=extend_schema(
        summary="Create new transaction",
        description="Create a new financial transaction. This operation is logged for audit purposes.",
        tags=['Transactions'],
        request=TransactionCreateSerializer,
        responses={
            201: TransactionSerializer,
            400: OpenApiResponse(description='Validation errors')
        },
        examples=[
            OpenApiExample(
                'Income transaction',
                summary='Example income transaction',
                description='Example of creating an income transaction',
                value={
                    'amount': '50000.00',
                    'description': 'Monthly salary',
                    'category': 1,
                    'date': '2024-12-28'
                }
            ),
            OpenApiExample(
                'Expense transaction',
                summary='Example expense transaction',
                description='Example of creating an expense transaction',
                value={
                    'amount': '1500.00',
                    'description': 'Grocery shopping',
                    'category': 2,
                    'date': '2024-12-28'
                }
            ),
        ]
    ),
    retrieve=extend_schema(
        summary="Get transaction details",
        description="Retrieve detailed information about a specific transaction.",
        tags=['Transactions']
    ),
    update=extend_schema(
        summary="Update transaction",
        description="Update transaction information. Changes are logged for audit purposes.",
        tags=['Transactions']
    ),
    partial_update=extend_schema(
        summary="Partially update transaction",
        description="Partially update transaction information. Changes are logged for audit purposes.",
        tags=['Transactions']
    ),
    destroy=extend_schema(
        summary="Delete transaction",
        description="Delete a transaction. This operation is logged and cannot be undone.",
        tags=['Transactions']
    ),
)
@method_decorator([transaction_read_limit, transaction_write_limit, transaction_delete_limit], name='dispatch')
class TransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления транзакциями с строгим rate limiting.
    
    Rate limits для финансовых операций:
    - GET: 200 запросов в минуту
    - POST/PUT/PATCH: 30 запросов в минуту (финансовые операции)
    - DELETE: 5 запросов в минуту (критические операции)
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_fields = [
        'category',
        'category__type',
        'date',
    ]
    search_fields = [
        'description',
        'category__name',
    ]
    ordering_fields = [
        'date',
        'amount',
        'created_at',
    ]
    ordering = [
        '-date',
        '-created_at',
    ]
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).select_related('category')
        
    def get_serializer_class(self):
        if self.action == 'create':
            return TransactionCreateSerializer
        return TransactionSerializer
        
    @extend_schema(
        summary="Financial statistics",
        description="Get comprehensive financial statistics for different time periods.",
        tags=['Statistics'],
        parameters=[
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Time period for statistics',
                enum=['week', 'month', 'year', 'all'],
                default='month'
            ),
        ],
        responses={
            200: OpenApiResponse(
                response={
                    'type': 'object',
                    'properties': {
                        'period': {'type': 'string'},
                        'total_balance': {'type': 'number'},
                        'period_income': {'type': 'number'},
                        'period_expense': {'type': 'number'},
                        'period_balance': {'type': 'number'},
                        'today_income': {'type': 'number'},
                        'today_expense': {'type': 'number'},
                        'top_expense_categories': {'type': 'array'},
                    }
                },
                description='Financial statistics'
            )
        }
    )
    @method_decorator(ratelimit(key='user', rate='60/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Базовая статистика по транзакциям"""
        queryset = self.get_queryset()
        
        # Текущий месяц
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Фильтр по периоду из параметров запроса
        period = request.query_params.get('period', 'month')  # month, week, year, all
        
        if period == 'week':
            week_start = today - timedelta(days=today.weekday())
            period_transactions = queryset.filter(date__gte=week_start)
            period_name = 'за неделю'
        elif period == 'year':
            year_start = today.replace(month=1, day=1)
            period_transactions = queryset.filter(date__gte=year_start)
            period_name = 'за год'
        elif period == 'all':
            period_transactions = queryset
            period_name = 'за все время'
        else:  # month по умолчанию
            period_transactions = queryset.filter(date__gte=month_start)
            period_name = 'за месяц'
        
        # Доходы и расходы за период
        period_income = period_transactions.filter(
            category__type=Category.INCOME
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        period_expense = period_transactions.filter(
            category__type=Category.EXPENSE  
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Общий баланс (за все время)
        total_income = queryset.filter(
            category__type=Category.INCOME
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        total_expense = queryset.filter(
            category__type=Category.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Топ категории за период
        top_expense_categories = period_transactions.filter(
            category__type=Category.EXPENSE
        ).values(
            'category__name', 'category__icon', 'category__color'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')[:5]
        
        # Транзакции за сегодня
        today_transactions = queryset.filter(date=today)
        today_income = today_transactions.filter(
            category__type=Category.INCOME
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        today_expense = today_transactions.filter(
            category__type=Category.EXPENSE
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'period': period_name,
            'total_balance': total_income - total_expense,
            'period_income': period_income,
            'period_expense': period_expense,
            'period_balance': period_income - period_expense,
            'period_transactions_count': period_transactions.count(),
            'today_income': today_income,
            'today_expense': today_expense,
            'today_balance': today_income - today_expense,
            'today_transactions_count': today_transactions.count(),
            'top_expense_categories': list(top_expense_categories),
        })
        
    @extend_schema(
        summary="Recent transactions",
        description="Get the most recent transactions for the authenticated user.",
        tags=['Transactions'],
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of recent transactions to return',
                default=10
            ),
        ],
        responses={
            200: TransactionSerializer(many=True)
        }
    )
    @method_decorator(ratelimit(key='user', rate='100/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Последние транзакции"""
        limit = int(request.query_params.get('limit', 10))
        transactions = self.get_queryset()[:limit]
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)
        
    @extend_schema(
        summary="Quick add transaction",
        description="Quickly create a transaction with minimal data (optimized for Telegram bot integration).",
        tags=['Transactions'],
        request=TransactionCreateSerializer,
        responses={
            201: TransactionSerializer,
            400: OpenApiResponse(description='Validation errors')
        }
    )
    @method_decorator(ratelimit(key='user', rate='50/m', method='POST', block=True))
    @action(detail=False, methods=['post'])
    def quick_add(self, request):
        """Быстрое добавление транзакции (для Telegram бота)"""
        serializer = TransactionCreateSerializer(
            data=request.data, 
            context={'request': request}
        )
        if serializer.is_valid():
            transaction = serializer.save()
            response_serializer = TransactionSerializer(
                transaction, 
                context={'request': request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
