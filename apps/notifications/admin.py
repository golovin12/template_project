from django.contrib import admin
from django.utils.html import format_html

from accounts.base import ManagerAdmin
from int.db_context import DatabaseContext
from .models import (
    NotificationMessage, NotificationSettings, NotificationChannel, CityNotificationPreference, NotificationConnectCode
)


@admin.register(NotificationMessage)
class NotificationMessageAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'provider', 'recipient_id', 'status', 'priority', 'retry_count', 'scheduled_for', 'sent_dt', 'created_dt',
        'short_text'
    )
    list_filter = ('provider', 'status', 'priority', 'created_dt', 'scheduled_for')
    search_fields = ('recipient_id', 'text', 'error_message')
    readonly_fields = ('created_dt', 'updated_dt', 'sent_dt')
    ordering = ('-priority', 'scheduled_for')

    fieldsets = (
        ('Основное', {
            'fields': (
                'provider', 'provider_token', 'recipient_id', 'text', 'mode'
            ),
        }),
        ('Статус отправки', {
            'fields': (
                'status', 'priority', 'scheduled_for', 'sent_dt', 'retry_count', 'error_message'
            ),
        }),
        ('Метаданные', {
            'fields': (
                'created_dt', 'updated_dt'
            ),
        }),
    )

    @admin.display(description='Текст')
    def short_text(self, obj):
        if not obj.text:
            return '—'

        return format_html(
            '<div style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{}</div>',
            obj.text,
        )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(ManagerAdmin):
    list_display = ('id', 'user', 'enabled', 'notif_type', 'created_dt')
    list_filter = ('enabled', 'notif_type', 'created_dt')
    search_fields = ('user__username',)
    readonly_fields = ('created_dt', 'updated_dt')
    autocomplete_fields = ('user',)
    list_select_related = ('user',)
    ordering = ('-created_dt',)

    fieldsets = (
        ('Основное', {
            'fields': (
                'user', 'enabled', 'notif_type'
            ),
        }),
        ('Метаданные', {
            'fields': (
                'created_dt', 'updated_dt'
            ),
        }),
    )


@admin.register(NotificationChannel)
class NotificationChannelAdmin(ManagerAdmin):
    list_display = ('id', 'notification_settings', 'provider', 'recipient_id', 'username', 'enabled', 'created_dt')
    list_filter = ('provider', 'enabled', 'created_dt')
    search_fields = ('recipient_id', 'username', 'notification_settings__user__username')
    readonly_fields = ('created_dt',)
    autocomplete_fields = ('notification_settings',)
    list_select_related = ('notification_settings', 'notification_settings__user')
    ordering = ('-created_dt',)


@admin.register(CityNotificationPreference)
class CityNotificationPreferenceAdmin(ManagerAdmin):
    list_display = ('id', 'notification_settings', 'city', 'enabled', 'created_dt')
    list_filter = ('enabled', 'created_dt')
    search_fields = ('notification_settings__user__username', 'city__name')
    readonly_fields = ('created_dt',)
    autocomplete_fields = ('city', 'notification_settings')
    list_select_related = ('notification_settings', 'notification_settings__user', 'city')
    ordering = ('-created_dt',)


@admin.register(NotificationConnectCode)
class NotificationConnectCodeAdmin(ManagerAdmin):
    list_display = ('user_id', 'provider', 'database_alias', 'code', 'expires_at', 'is_used', 'created_dt')
    list_filter = ('provider', 'database_alias', 'is_used', 'created_dt', 'expires_at')
    search_fields = ('code', 'user_id', 'database_alias')
    readonly_fields = ('user_id', 'code', 'provider', 'database_alias', 'created_dt', 'expires_at', 'is_used',)
    ordering = ('-created_dt',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(database_alias=DatabaseContext.get())

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
