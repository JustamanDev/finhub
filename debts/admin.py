from django.contrib import admin

from debts.models import Debt, DebtPayment


class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ['counterparty', 'user', 'direction', 'principal', 'is_open']
    list_filter = ['direction', 'is_open']
    search_fields = ['counterparty', 'user__username']
    inlines = [DebtPaymentInline]
