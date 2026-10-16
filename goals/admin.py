from django.contrib import admin

from goals.models import (
    Goal,
    GoalLedgerEntry,
)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'title',
        'kind',
        'target_amount',
        'deadline',
        'status',
        'created_at',
    )
    list_filter = (
        'kind',
        'status',
        'deadline',
        'created_at',
    )
    search_fields = (
        'title',
        'user__username',
    )


@admin.register(GoalLedgerEntry)
class GoalLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'goal',
        'entry_type',
        'amount',
        'occurred_at',
        'linked_transaction',
    )
    list_filter = (
        'entry_type',
        'occurred_at',
    )
    search_fields = (
        'goal__title',
        'comment',
    )

