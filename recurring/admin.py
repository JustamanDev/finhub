from django.contrib import admin

from recurring.models import RecurringTemplate


@admin.register(RecurringTemplate)
class RecurringTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'periodicity', 'amount_kind', 'next_due', 'is_active']
    list_filter = ['periodicity', 'amount_kind', 'is_active']
    search_fields = ['name', 'user__username']
