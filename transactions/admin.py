from django.contrib import admin
from django.utils.html import format_html
from .models import Transaction
from categories.models import Category


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'amount',
        'category',
        'description_short',
        'date',
        'user',
        'created_at',
    ]
    list_filter = [
        'category__type',
        'category',
        'date',
        'created_at',
    ]
    search_fields = [
        'description',
        'category__name',
        'amount',
    ]
    date_hierarchy = 'date'
    readonly_fields = [
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('amount', 'category', 'description', 'date')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def description_short(self, obj):
        """Сокращенное описание для списка"""
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_short.short_description = 'Описание'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.filter(user=request.user, is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)
