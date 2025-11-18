from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from datetime import datetime
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from .models import Budget
from .serializers import BudgetSerializer, BudgetCreateSerializer, CategoryBudgetInfoSerializer
from categories.models import Category


# Rate limiting for budget operations
budget_read_limit = ratelimit(key='user', rate='150/m', method='GET', block=True)
budget_write_limit = ratelimit(key='user', rate='25/m', method=['POST', 'PUT', 'PATCH'], block=True)
budget_delete_limit = ratelimit(key='user', rate='10/m', method='DELETE', block=True)


@method_decorator([budget_read_limit, budget_write_limit, budget_delete_limit], name='dispatch')
class BudgetViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления бюджетами с rate limiting.
    
    Rate limits для бюджетных операций:
    - GET: 150 запросов в минуту
    - POST/PUT/PATCH: 25 запросов в минуту
    - DELETE: 10 запросов в минуту
    """
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_fields = [
        'period_type',
        'is_active',
        'category',
    ]
    search_fields = [
        'category__name',
    ]
    ordering_fields = [
        'start_date',
        'amount',
        'created_at',
    ]
    ordering = [
        '-start_date',
    ]
    
    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user).select_related('category')
        
    def get_serializer_class(self):
        if self.action == 'quick_create':
            return BudgetCreateSerializer
        return BudgetSerializer
        
    @method_decorator(ratelimit(key='user', rate='80/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Получить текущие активные бюджеты"""
        today = timezone.now().date()
        budgets = self.get_queryset().filter(
            start_date__lte=today,
            end_date__gte=today,
            is_active=True
        )
        serializer = self.get_serializer(budgets, many=True)
        return Response(serializer.data)
        
    @method_decorator(ratelimit(key='user', rate='40/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def overspent(self, request):
        """Получить превышенные бюджеты"""
        budgets = []
        for budget in self.get_queryset().filter(is_active=True):
            if budget.is_overspent:
                budgets.append(budget)
                
        serializer = self.get_serializer(budgets, many=True)
        return Response(serializer.data)
        
    @method_decorator(ratelimit(key='user', rate='20/m', method='POST', block=True))
    @action(detail=False, methods=['post'])
    def quick_create(self, request):
        """Быстрое создание месячного бюджета"""
        serializer = BudgetCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            budget = serializer.save()
            response_serializer = BudgetSerializer(
                budget,
                context={'request': request}
            )
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    @method_decorator(ratelimit(key='user', rate='60/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def categories_overview(self, request):
        """Обзор всех расходных категорий с информацией о бюджетах"""
        categories = Category.objects.filter(
            user=request.user,
            type=Category.EXPENSE,
            is_active=True
        ).order_by('name')
        
        result = []
        for category in categories:
            budget_info = category.get_budget_info()
            
            category_data = {
                'category_id': category.id,
                'category_name': category.name,
                'category_icon': category.icon,
                'category_color': category.color,
                'has_budget': budget_info is not None,
            }
            
            if budget_info:
                category_data.update({
                    'budget_amount': budget_info['budget_amount'],
                    'spent_amount': budget_info['spent_amount'],
                    'remaining_amount': budget_info['remaining_amount'],
                    'spent_percentage': budget_info['spent_percentage'],
                    'remaining_percentage': budget_info['remaining_percentage'],
                    'is_overspent': budget_info['is_overspent'],
                    'days_remaining': budget_info['days_remaining'],
                    'daily_budget_remaining': budget_info['daily_budget_remaining'],
                    'period_type': budget_info['period_type'],
                })
            else:
                category_data.update({
                    'budget_amount': None,
                    'spent_amount': None,
                    'remaining_amount': None,
                    'spent_percentage': None,
                    'remaining_percentage': None,
                    'is_overspent': None,
                    'days_remaining': None,
                    'daily_budget_remaining': None,
                    'period_type': None,
                })
                
            result.append(category_data)
            
        serializer = CategoryBudgetInfoSerializer(result, many=True)
        return Response(serializer.data)
        
    @method_decorator(ratelimit(key='user', rate='30/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        """Сводка по месячным бюджетам"""
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        # Начало и конец месяца
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()
        end_date = end_date.replace(day=1) - timezone.timedelta(days=1)
        
        budgets = self.get_queryset().filter(
            start_date__lte=end_date,
            end_date__gte=start_date,
            period_type=Budget.MONTHLY,
            is_active=True
        )
        
        total_budget = sum(b.amount for b in budgets)
        total_spent = sum(b.spent_amount for b in budgets)
        total_remaining = total_budget - total_spent
        overspent_count = sum(1 for b in budgets if b.is_overspent)
        
        return Response({
            'year': year,
            'month': month,
            'total_budget': total_budget,
            'total_spent': total_spent,
            'total_remaining': total_remaining,
            'total_spent_percentage': (total_spent / total_budget * 100) if total_budget > 0 else 0,
            'budgets_count': budgets.count(),
            'overspent_count': overspent_count,
            'budgets': BudgetSerializer(budgets, many=True, context={'request': request}).data
        })
