from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Category
from .serializers import CategorySerializer


# Rate limiting decorators for different operations
category_read_limit = ratelimit(key='user', rate='100/m', method='GET', block=True)
category_write_limit = ratelimit(key='user', rate='20/m', method=['POST', 'PUT', 'PATCH'], block=True)
category_delete_limit = ratelimit(key='user', rate='10/m', method='DELETE', block=True)


@extend_schema_view(
    list=extend_schema(
        summary="List user categories",
        description="Get all categories belonging to the authenticated user with filtering and search capabilities.",
        tags=['Categories'],
        parameters=[
            OpenApiParameter(
                name='type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by category type',
                enum=['income', 'expense']
            ),
            OpenApiParameter(
                name='is_active',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by active status'
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in category names'
            ),
        ]
    ),
    create=extend_schema(
        summary="Create new category",
        description="Create a new income or expense category for the authenticated user.",
        tags=['Categories']
    ),
    retrieve=extend_schema(
        summary="Get category details",
        description="Retrieve detailed information about a specific category including budget information.",
        tags=['Categories']
    ),
    update=extend_schema(
        summary="Update category",
        description="Update category information (full update).",
        tags=['Categories']
    ),
    partial_update=extend_schema(
        summary="Partially update category",
        description="Partially update category information.",
        tags=['Categories']
    ),
    destroy=extend_schema(
        summary="Delete category",
        description="Delete a category. Note: This will also affect related transactions.",
        tags=['Categories']
    ),
)
@method_decorator([category_read_limit, category_write_limit, category_delete_limit], name='dispatch')
class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления категориями с rate limiting.
    
    Rate limits:
    - GET: 100 запросов в минуту
    - POST/PUT/PATCH: 20 запросов в минуту  
    - DELETE: 10 запросов в минуту
    """
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_fields = [
        'type',
        'is_active',
    ]
    search_fields = [
        'name',
    ]
    ordering_fields = [
        'name',
        'created_at',
    ]
    ordering = [
        'type',
        'name',
    ]
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)
        
    @extend_schema(
        summary="Get income categories",
        description="Retrieve all active income categories for the authenticated user.",
        tags=['Categories'],
        responses={
            200: CategorySerializer(many=True),
        }
    )
    @method_decorator(ratelimit(key='user', rate='50/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def income(self, request):
        """Получить категории доходов"""
        categories = self.get_queryset().filter(type=Category.INCOME, is_active=True)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
        
    @extend_schema(
        summary="Get expense categories",
        description="Retrieve all active expense categories for the authenticated user.",
        tags=['Categories'],
        responses={
            200: CategorySerializer(many=True),
        }
    )
    @method_decorator(ratelimit(key='user', rate='50/m', method='GET', block=True))
    @action(detail=False, methods=['get']) 
    def expense(self, request):
        """Получить категории расходов"""
        categories = self.get_queryset().filter(type=Category.EXPENSE, is_active=True)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)
        
    @extend_schema(
        summary="Category statistics",
        description="Get statistical information about user's categories.",
        tags=['Statistics'],
        responses={
            200: OpenApiResponse(
                response={
                    'type': 'object',
                    'properties': {
                        'total_categories': {'type': 'integer'},
                        'active_categories': {'type': 'integer'},
                        'income_categories': {'type': 'integer'},
                        'expense_categories': {'type': 'integer'},
                    }
                },
                description='Category statistics'
            )
        }
    )
    @method_decorator(ratelimit(key='user', rate='30/m', method='GET', block=True))
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Статистика по категориям"""
        queryset = self.get_queryset()
        
        total_categories = queryset.count()
        active_categories = queryset.filter(is_active=True).count()
        income_categories = queryset.filter(type=Category.INCOME, is_active=True).count()
        expense_categories = queryset.filter(type=Category.EXPENSE, is_active=True).count()
        
        return Response({
            'total_categories': total_categories,
            'active_categories': active_categories,
            'income_categories': income_categories,
            'expense_categories': expense_categories,
        })
