"""
URL configuration for finhub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import (
    path,
    include,
)
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status


@api_view(['GET'])
def api_info(request):
    """API information endpoint."""
    base_url = request.build_absolute_uri('/api/')
    
    return Response({
        'name': 'FinHub API',
        'version': '1.0.0',
        'description': 'Personal Finance Management API with comprehensive budgeting and transaction tracking',
        'supported_versions': ['v1'],
        'current_version': 'v1',
        'endpoints': {
            'v1': f'{base_url}v1/',
            'auth': f'{base_url}v1/auth/',
            'docs': f'{base_url}docs/',
            'redoc': f'{base_url}redoc/',
            'schema': f'{base_url}schema/',
        },
        'documentation': {
            'swagger_ui': f'{base_url}docs/',
            'redoc': f'{base_url}redoc/',
            'openapi_schema': f'{base_url}schema/',
            'interactive': True,
        },
        'authentication': {
            'types': ['Token Authentication', 'Session Authentication'],
            'token_endpoint': f'{base_url}v1/auth/token/login/',
            'token_logout': f'{base_url}v1/auth/token/logout/',
        },
        'features': [
            'Categories Management',
            'Transaction Tracking', 
            'Budget Planning',
            'Financial Analytics',
            'Rate Limiting',
            'Comprehensive Logging',
        ],
        'status': 'stable',
        'last_updated': '2024-12-28',
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api_info, name='api-info'),
    path('api/', include('api.urls')),
]
