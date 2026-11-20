from django.contrib import admin
from django.utils.html import format_html

from accounts.base import ManagerAdmin
from .models import NotificationMessage, NotificationSettings, NotificationChannel, CityNotificationPreference


@admin.register(NotificationMessage)
class NotificationMessageAdmin(ManagerAdmin):
    list_display = (
        'id',
        'provider',
        'recipient_id',
        'status',
        'priority',
        'retry_count',
        'scheduled_for',
        'sent_dt',
        'created_dt',
        'short_text',
    )

    list_filter = (
        'provider',
        'status',
        'priority',
        'created_dt',
        'scheduled_for',
    )

    search_fields = (
        'recipient_id',
        'text',
        'error_message',
    )

    readonly_fields = (
        'created_dt',
        'updated_dt',
        'sent_dt',
    )

    ordering = ('-priority', '-scheduled_for')

    fieldsets = (
        ('Основное', {
            'fields': (
                'provider',
                'provider_token',
                'recipient_id',
                'text',
            )
        }),
        ('Статус отправки', {
            'fields': (
                'status',
                'priority',
                'scheduled_for',
                'sent_dt',
                'retry_count',
                'error_message',
            )
        }),
        ('Метаданные', {
            'fields': (
                'created_dt',
                'updated_dt',
            )
        }),
    )

    def short_text(self, obj):
        if not obj.text:
            return "-"
        return format_html(
            '<div style="max-width:300px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
            '{}'
            '</div>',
            obj.text
        )

    short_text.short_description = 'Текст'


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(ManagerAdmin):
    list_display = (
        'id',
        'user',
        'enabled',
        'notif_type',
        'created_dt',
    )

    list_filter = (
        'enabled',
        'notif_type',
        'created_dt',
    )

    search_fields = (
        'user__username',
    )

    readonly_fields = (
        'created_dt',
        'updated_dt',
    )

    fieldsets = (
        ('Основное', {
            'fields': (
                'user',
                'enabled',
                'notif_type',
            )
        }),
        ('Метаданные', {
            'fields': (
                'created_dt',
                'updated_dt',
            )
        }),
    )

    autocomplete_fields = ('user',)


@admin.register(NotificationChannel)
class NotificationChannelAdmin(ManagerAdmin):
    list_display = (
        'id',
        'notification_settings',
        'provider',
        'recipient_id',
        'username',
        'enabled',
        'created_dt',
    )

    list_filter = ('provider', 'enabled', 'created_dt',)

    search_fields = (
        'recipient_id',
        'username',
        'notification_settings__user__username',
    )

    readonly_fields = ('created_dt',)
    autocomplete_fields = ('notification_settings',)


@admin.register(CityNotificationPreference)
class CityNotificationPreferenceAdmin(ManagerAdmin):
    list_display = (
        'id',
        'notification_settings',
        'city',
        'enabled',
        'created_dt',
    )

    list_filter = (
        'enabled',
        'created_dt',
    )

    search_fields = (
        'notification_settings__user__username',
        'city__name',
    )

    readonly_fields = ('created_dt',)
    autocomplete_fields = ('city', 'notification_settings')
