from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html

from accounts.base import ManagerAdmin, OrganizationRequest
from .controllers import RequestController
from .models import ServiceRequest, DeviceType


@admin.register(DeviceType)
class DeviceTypeAdmin(ManagerAdmin):
    """Админка для типов техники"""
    list_display = ('name', 'branches_list')
    list_filter = ('is_available_for_all', 'branches')
    search_fields = ('name',)
    ordering = ('name',)
    autocomplete_fields = ('branches',)
    list_per_page = 25

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'is_available_for_all')
        }),
        ('Филиалы', {
            'fields': ('branches',),
        }),
    )

    def branches_list(self, obj):
        """Отображение списка филиалов в колонке"""
        if obj.is_available_for_all:
            return 'Все филиалы'

        branches = obj.branches.all().order_by('city', 'name')

        branch_names = (str(branch) for branch in branches)
        return ', '.join(branch_names) if branch_names else 'Нет филиалов'

    branches_list.short_description = 'Филиалы'


@admin.register(ServiceRequest)
class ServiceRequestAdmin(ManagerAdmin):
    list_display = (
        'request_number',
        'time_to_service',
        'branch',
        'client_phone',
        'client_name',
        'closing_amount',
        'status',
    )
    list_filter = ('status', 'time_to_service', 'branch', 'request_type')
    autocomplete_fields = ('branch',)
    search_fields = ('request_number', 'client_phone')
    readonly_fields = (
        'request_time',
        'closing_time',
        'created_by',
        'parent',
        'closing_undo_widget',
        'consent_time',
    )
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'parent',
                'created_by',
                'request_number',
                ('status', 'closing_undo_widget'),
                'branch',
            )
        }),
        ('Информация о клиенте', {
            'fields': (
                'client_name',
                'client_address',
                'client_phone',
                'request_type',
            )
        }),
        ('Детали заявки', {
            'fields': (
                'device_type',
                'problem_description',
                'time_to_service',
                'service_report',
                'sd_closing_date',
                'closing_amount',
                'other_expenses',
            )
        }),
        ('Временные метки', {
            'fields': (
                'request_time',
                'closing_time'
            )
        }),
    )

    def closing_undo_widget(self, obj):
        if obj.status == ServiceRequest.STATUS.COMPLETED:
            return format_html(
                '''
                <button type="submit" name="closing_undo_action" value="Отменить" class="btn-danger"
                  onclick="return confirm('Вы уверены, что хотите отменить закрытие заявки?');"
                  style="padding:2px 6px; margin-left: 10px;">Отменить закрытие</button>
                '''
            )
        return ''

    closing_undo_widget.short_description = ''
    closing_undo_widget.allow_tags = True

    def changeform_view(self, request: OrganizationRequest, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST' and 'closing_undo_action' in request.POST:
            obj = self.get_object(request, object_id)
            try:
                RequestController.undo_closing(obj)
                self.message_user(request, 'Заявка переведена в статус "В работе"')
                return redirect(request.path)
            except Exception as e:
                self.message_user(request, f'Ошибка: {e}', level='error')
        return super().changeform_view(request, object_id, form_url, extra_context)
