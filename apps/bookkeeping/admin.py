from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from accounts.base import ManagerAdmin
from .models import AccountingEntry


@admin.register(AccountingEntry)
class AccountingEntryAdmin(ManagerAdmin):
    list_display = (
        'created_dt',
        'entry_type',
        'expense_subtype',
        'amount',
        'description',
        'branch_display',
        'service_request_link'
    )
    autocomplete_fields = ('branch', 'service_request', 'created_by', 'city')
    list_filter = ('entry_type', 'branch', 'created_dt', 'hidden')
    list_select_related = ('city', 'branch', 'service_request', 'created_by')
    search_fields = ('description',)
    readonly_fields = ('service_request_link', 'created_by', 'branch_display')
    fieldsets = (
        (None, {
            'fields': (
                'created_by',
                'entry_type',
                'expense_subtype',
                'amount',
                'hidden',
                'description',
                'city',
                'branch',
                'service_request',
                'service_request_link',
                'created_dt',
                'receipt_photo',
            )
        }),
    )

    def branch_display(self, obj):
        if obj.branch:
            return str(obj.branch)
        return obj.city.name if obj.city else "Без филиала"

    branch_display.short_description = 'Филиал'

    def service_request_link(self, obj):
        if obj.service_request:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:service_requests_servicerequest_change', args=[obj.service_request.id]),
                obj.service_request,
            )
        return 'Нет заявки'

    service_request_link.short_description = 'Ссылка на заявку'
    service_request_link.allow_tags = True
