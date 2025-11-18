from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import Budget
from categories.models import Category


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        'category',
        'amount',
        'spent_amount_display',
        'remaining_amount_display',
        'spent_percentage_display',
        'period_type',
        'start_date',
        'end_date',
        'is_active',
        'is_overspent_display',
    ]
    list_filter = [
        'period_type',
        'is_active',
        'start_date',
        'category__type',
    ]
    search_fields = [
        'category__name',
    ]
    readonly_fields = [
        'spent_amount_display',
        'remaining_amount_display',
        'spent_percentage_display',
        'days_remaining_display',
        'daily_budget_remaining_display',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('category', 'amount', 'period_type', 'start_date', 'end_date', 'is_active')
        }),
        ('Статистика (только для чтения)', {
            'fields': (
                'spent_amount_display', 'remaining_amount_display', 'spent_percentage_display',
                'days_remaining_display', 'daily_budget_remaining_display'
            ),
            'classes': ('collapse',),
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def spent_amount_display(self, obj):
        """Отображение потраченной суммы"""
        try:
            spent = obj.spent_amount
            color = 'red' if obj.is_overspent else 'green'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} руб.</span>',
                color,
                spent
            )
        except (TypeError, AttributeError):
            return format_html('<span style="color: red;">Ошибка</span>')
    spent_amount_display.short_description = 'Потрачено'
    
    def remaining_amount_display(self, obj):
        """Отображение оставшейся суммы"""
        try:
            remaining = obj.remaining_amount
            color = 'red' if remaining < 0 else 'green'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} руб.</span>',
                color,
                remaining
            )
        except (TypeError, AttributeError):
            return format_html('<span style="color: red;">Ошибка</span>')
    remaining_amount_display.short_description = 'Остаток'
    
    def spent_percentage_display(self, obj):
        """Отображение процента потраченного"""
        try:
            percentage = obj.spent_percentage
            if percentage <= 50:
                color = 'green'
            elif percentage <= 80:
                color = 'orange'
            else:
                color = 'red'
                
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}%</span>',
                color,
                round(percentage, 1)
            )
        except (TypeError, AttributeError):
            return format_html('<span style="color: red;">Ошибка</span>')
    spent_percentage_display.short_description = 'Потрачено %'
    
    def is_overspent_display(self, obj):
        """Отображение превышения бюджета"""
        try:
            if obj.is_overspent:
                return format_html('<span style="color: red;">❌ Превышен</span>')
            return format_html('<span style="color: green;">✅ В рамках</span>')
        except (TypeError, AttributeError):
            return format_html('<span style="color: red;">Ошибка</span>')
    is_overspent_display.short_description = 'Статус'
    
    def days_remaining_display(self, obj):
        """Отображение оставшихся дней"""
        try:
            # Защита от случаев, когда даты не заданы (например, при создании в админке)
            if getattr(obj, 'start_date', None) is None or getattr(obj, 'end_date', None) is None:
                return "Не задано"

            days = obj.days_remaining
            if isinstance(days, int):
                return f"{days} дн." if days > 0 else "Завершен"
            return "Ошибка"
        except Exception:
            return "Ошибка"
    days_remaining_display.short_description = 'Дней осталось'
    
    def daily_budget_remaining_display(self, obj):
        """Отображение дневного бюджета"""
        try:
            daily = obj.daily_budget_remaining
            return f"{daily} руб./день"
        except (TypeError, AttributeError):
            return "Ошибка"
    daily_budget_remaining_display.short_description = 'Дневной лимит'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        return qs.select_related('category')
        
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.filter(
                user=request.user, 
                is_active=True,
                type=Category.EXPENSE  # Бюджеты только для расходных категорий
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
        
    def save_model(self, request, obj, form, change):
        if not change:
            obj.user = request.user
        super().save_model(request, obj, form, change)
        
    class Media:
        css = {
            'all': ('admin/css/budget_admin.css',)
        }
