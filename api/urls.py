from django.urls import (
    path,
    include,
)
from rest_framework.routers import DefaultRouter
from categories.views import CategoryViewSet
from transactions.views import TransactionViewSet
from budgets.views import BudgetViewSet
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


# API v1 Router
v1_router = DefaultRouter()
v1_router.register(r'categories', CategoryViewSet, basename='categories')
v1_router.register(r'transactions', TransactionViewSet, basename='transactions')
v1_router.register(r'budgets', BudgetViewSet, basename='budgets')

# URL patterns with versioning
urlpatterns = [
    # API v1 endpoints
    path('v1/', include([
        path('', include(v1_router.urls)),
        # v1 Authentication endpoints
        path('auth/', include('djoser.urls')),
        path('auth/', include('djoser.urls.authtoken')),
        
        # API Documentation v1
        path('schema/', SpectacularAPIView.as_view(api_version='v1'), name='schema-v1'),
        path('docs/', SpectacularSwaggerView.as_view(url_name='schema-v1'), name='swagger-ui-v1'),
        path('redoc/', SpectacularRedocView.as_view(url_name='schema-v1'), name='redoc-v1'),
    ])),
    
    # Default version (currently v1)
    path('', include([
        path('', include(v1_router.urls)),
        path('auth/', include('djoser.urls')),
        path('auth/', include('djoser.urls.authtoken')),
        
        # Default API Documentation (latest version)
        path('schema/', SpectacularAPIView.as_view(), name='schema'),
        path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
        path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    ])),
] 