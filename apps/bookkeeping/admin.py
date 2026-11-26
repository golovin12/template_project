from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from accounts.base import ManagerAdmin
from .models import AccountingEntry


@admin.register(AccountingEntry)
class AccountingEntryAdmin(ManagerAdmin):
    list_display = (
        'created_dt', 'entry_type', 'expense_subtype', 'amount', 'description', 'branch_display', 'service_request_link'
    )
    list_filter = ('entry_type', 'expense_subtype', 'branch', 'city', 'created_dt')
    search_fields = (
        'description', 'branch__name', 'city__name', 'service_request__request_number', 'created_by__username'
    )
    autocomplete_fields = ('branch', 'service_request', 'city')
    list_select_related = ('city', 'branch', 'service_request', 'created_by')
    readonly_fields = ('created_by', 'created_dt', 'branch_display', 'service_request_link')
    ordering = ('-created_dt',)

    fieldsets = (
        (None, {
            'fields': (
                'created_by', 'entry_type', 'expense_subtype', 'amount', 'description', 'city', 'branch',
                'service_request', 'service_request_link', 'created_dt', 'receipt_photo'
            ),
        }),
    )

    @admin.display(description='Филиал')
    def branch_display(self, obj):
        if obj.branch:
            return str(obj.branch)

        return obj.city.name if obj.city else 'Без филиала'

    @admin.display(description='Ссылка на заявку')
    def service_request_link(self, obj):
        if not obj.service_request_id:
            return 'Нет заявки'

        url = reverse('admin:service_requests_servicerequest_change', args=[obj.service_request_id])

        return format_html('<a href="{}">{}</a>', url, obj.service_request)
