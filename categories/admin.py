from django.contrib import admin
from .models import (
    Category,
    DefaultCategoryTemplate,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'type',
        'color',
        'icon',
        'user',
        'is_active',
        'created_at',
    ]
    list_filter = [
        'type',
        'is_active',
        'created_at',
    ]
    search_fields = [
        'name',
        'user__username',
    ]
    list_editable = [
        'is_active',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'type', 'color', 'icon', 'is_active')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs
        
    def save_model(self, request, obj, form, change):
        if not change:  # Создание новой категории
            obj.user = request.user
        super().save_model(request, obj, form, change)


@admin.register(DefaultCategoryTemplate)
class DefaultCategoryTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "type",
        "icon",
        "color",
        "sort_order",
        "is_active",
        "updated_at",
    ]
    list_filter = [
        "type",
        "is_active",
    ]
    search_fields = [
        "name",
    ]
    list_editable = [
        "is_active",
        "sort_order",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
