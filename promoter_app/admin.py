import re
from datetime import datetime

from asgiref.sync import async_to_sync

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse

from accounts.base import ManagerAdmin, ZoneWSGIRequest
from . import models


@admin.register(models.PromoterProfile)
class PromoterProfileAdmin(ManagerAdmin):
    """Админка для промоутеров"""
    list_display = ('nickname', 'city', 'assignments_count', 'last_assignment_date')
    list_filter = ('city',)
    search_fields = ('nickname', 'city__name')

    def assignments_count(self, obj):
        """Количество назначений промоутера"""
        count = obj.assignments.count()
        url = reverse('admin:promoter_app_promoterassignment_changelist') + f'?promoter__id={obj.id}'
        return format_html('<a href="{}">{} назначений</a>', url, count)

    assignments_count.short_description = 'Назначения'

    def last_assignment_date(self, obj):
        """Дата последнего назначения"""
        last_assignment = obj.assignments.first()
        if last_assignment:
            return last_assignment.assigned_date.strftime('%d.%m.%Y %H:%M')
        return '-'

    last_assignment_date.short_description = 'Последнее назначение'


@admin.register(models.RouteZone)
class RouteZoneAdmin(ManagerAdmin):
    """Админка для маршрутов"""
    list_display = ('name', 'city', 'last_assigned_date', 'is_active', 'color_status', 'assignments_count')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'city__name')
    list_editable = ('is_active',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('city', 'name', 'is_active')
        }),
        ('Даты', {
            'fields': ('last_assigned_date',)
        }),
        ('Геометрия', {
            'fields': ('polygon',),
            'classes': ('wide',),
            'description': 'GeoJSON формат: {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}'
        }),
    )

    actions = ['update_last_assigned_by_name']

    def color_status(self, obj):
        """Цветовой индикатор статуса"""
        color = obj.get_color_by_last_assigned()
        color_map = {
            'red': '#dc3545',
            'yellow': '#ffc107',
            'green': '#28a745'
        }
        status_map = {
            'red': 'Активный',
            'yellow': 'Недавний',
            'green': 'Давно'
        }
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px; color: {};">{}</span>',
            color_map.get(color, '#6c757d'),
            'white' if color == 'red' else 'black',
            status_map.get(color, 'Неизвестно')
        )

    color_status.short_description = 'Статус'

    def assignments_count(self, obj):
        """Количество назначений на маршрут"""
        count = obj.assignments.count()
        url = reverse('admin:promoter_app_promoterassignment_changelist') + f'?route_zone__id={obj.id}'
        return format_html('<a href="{}">{} назначений</a>', url, count)

    assignments_count.short_description = 'Назначения'

    @admin.action(description='Обновить дату последнего назначения по названию')
    def update_last_assigned_by_name(self, request: ZoneWSGIRequest, queryset):
        """
        Обновляет дату последнего назначения для выбранных маршрутов.
        Ищет в названии маршрута паттерн "день.месяц" (поддерживает форматы:
        01.02, 1.02, 01.2, 1.2) и устанавливает last_assigned_date
        на соответствующий день текущего года.
        После обновления переименовывает маршрут в "Маршрут {номер}"
        """
        current_year = timezone.now().year
        updated_count = 0
        errors = []

        max_numbers = {}
        all_routes = models.RouteZone.objects.all()
        for route in all_routes:
            match = re.search(r'Маршрут\s+(\d+)', route.name)
            if match:
                number = int(match.group(1))
                city_id = route.city_id
                if city_id not in max_numbers or number > max_numbers[city_id]:
                    max_numbers[city_id] = number

        for route in queryset:
            match = re.search(r'(\d{1,2})[,./](\d{1,2})', route.name)

            if match:
                day = int(match.group(1))
                month = int(match.group(2))

                try:
                    new_date = datetime(current_year, month, day)
                    if not route.last_assigned_date:
                        route.last_assigned_date = new_date

                    city_id = route.city_id
                    next_number = max_numbers.get(city_id, 0) + 1
                    route.name = f'Маршрут {next_number}'
                    max_numbers[city_id] = next_number

                    route.save(update_fields=['last_assigned_date', 'name'])
                    updated_count += 1
                except ValueError:
                    errors.append(f'"{route.name}" ({day:02d}.{month:02d})')

        message_parts = []
        if updated_count > 0:
            message_parts.append(f'✅ Обновлено и переименовано: {updated_count}')
        if errors:
            message_parts.append(f'❌ Ошибок: {len(errors)}')
            self.message_user(request, f'Неверные даты: {", ".join(errors[:5])}', level='ERROR')

        if message_parts:
            self.message_user(request, ' | '.join(message_parts))
        else:
            self.message_user(request, 'Нет маршрутов для обновления')

    def save_model(self, request: ZoneWSGIRequest, obj, form, change):
        """При сохранении валидируем GeoJSON"""
        if obj.polygon:
            if isinstance(obj.polygon, str):
                import json
                try:
                    obj.polygon = json.loads(obj.polygon)
                except json.JSONDecodeError:
                    self.message_user(request, 'Ошибка: Неверный формат GeoJSON', level='ERROR')
                    return
        super().save_model(request, obj, form, change)


@admin.register(models.PromoterAssignment)
class PromoterAssignmentAdmin(ManagerAdmin):
    """Админка для назначений промоутеров"""
    list_display = ('id', 'promoter', 'route_zone', 'assigned_date', 'status', 'is_confirmed', 'is_cleaned',
                    'photos_info', 'full_data_loaded', 'assigned_by')
    list_filter = ('status', 'is_confirmed', 'full_data_loaded', 'assigned_date', 'route_zone__city', 'is_cleaned')
    search_fields = ('promoter__nickname', 'route_zone__name')
    date_hierarchy = 'assigned_date'
    readonly_fields = ('assigned_date',)
    autocomplete_fields = ('promoter', 'route_zone', 'assigned_by')

    fieldsets = (
        ('Назначение', {
            'fields': ('promoter', 'route_zone', 'status', 'is_confirmed', 'is_cleaned')
        }),
        ('Информация о назначении', {
            'fields': ('assigned_date', 'assigned_by', 'confirmed_dt')
        }),
        ('Статистика фотографий', {
            'fields': ('total_photos', 'photos_no_gps', 'full_data_loaded')
        }),
    )

    def photos_info(self, obj):
        """Информация о фотографиях"""
        if obj.total_photos == 0:
            return format_html('<span style="color: #6c757d;">Нет фото</span>')

        photos_with_gps = obj.total_photos - obj.photos_no_gps
        percentage = round((photos_with_gps / obj.total_photos * 100)) if obj.total_photos > 0 else 0

        color = '#28a745' if percentage > 70 else '#ffc107' if percentage > 30 else '#dc3545'

        return format_html(
            '<span style="color: {};">{} / {} ({}%)</span>',
            color, photos_with_gps, obj.total_photos, percentage
        )

    photos_info.short_description = 'Фото с GPS / Всего'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('promoter', 'route_zone', 'assigned_by')

    actions = ['mark_as_processed', 'mark_as_ended', 'mark_as_confirmed', 'recalc_stats']

    @admin.action(description='Отметить как "В работе"')
    def mark_as_processed(self, request: ZoneWSGIRequest, queryset):
        updated = queryset.update(status=models.PromoterAssignment.Status.PROCESS)
        self.message_user(request, f'{updated} назначений отмечены как "В работе"')

    @admin.action(description='Отметить как "Завершён"')
    def mark_as_ended(self, request: ZoneWSGIRequest, queryset):
        updated = queryset.update(status=models.PromoterAssignment.Status.ENDED)
        self.message_user(request, f'{updated} назначений отмечены как "Завершён"')

    @admin.action(description='Отметить как "Подтверждён"')
    def mark_as_confirmed(self, request: ZoneWSGIRequest, queryset):
        updated = queryset.update(status=models.PromoterAssignment.Status.ENDED, is_confirmed=True,
                                  confirmed_dt=timezone.now())
        self.message_user(request, f'{updated} назначений отмечены как "Подтверждён"')

    @admin.action(description='Пересчитать статистику фото')
    def recalc_stats(self, request: ZoneWSGIRequest, queryset):
        for assignment in queryset:
            async_to_sync(assignment.recalc_stat_and_save)()
        self.message_user(request, f'Статистика пересчитана для {queryset.count()} назначений')


class PromoterPhotoInline(admin.TabularInline):
    """Inline для фотографий в назначении"""
    model = models.PromoterPhoto
    extra = 0
    fields = ('image', 'created_at', 'lat', 'lng', 'has_location', 'image_preview')
    readonly_fields = ('created_at', 'image_preview')

    def image_preview(self, obj):
        """Превью изображения в админке"""
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 100px;" />', obj.s3_rul)
        return '-'

    image_preview.short_description = 'Превью'


@admin.register(models.PromoterPhoto)
class PromoterPhotoAdmin(ManagerAdmin):
    """Админка для фотографий промоутеров"""
    list_display = ('id', 'assignment', 'image_preview', 'created_at', 'has_location', 'lat', 'lng')
    list_filter = ('has_location', 'created_at', 'assignment__route_zone__city')
    search_fields = ('assignment__promoter__nickname', 'assignment__route_zone__name')
    date_hierarchy = 'created_at'
    raw_id_fields = ('assignment',)

    fieldsets = (
        ('Назначение', {
            'fields': ('assignment',)
        }),
        ('Фотография', {
            'fields': ('image', 'image_preview', 'created_at')
        }),
        ('Геолокация', {
            'fields': ('has_location', 'lat', 'lng')
        }),
    )

    readonly_fields = ('created_at', 'image_preview')

    def image_preview(self, obj):
        """Превью изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 100px; max-width: 200px;" /></a>',
                obj.s3_url, obj.s3_url
            )
        return '-'

    image_preview.short_description = 'Превью'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('assignment__promoter', 'assignment__route_zone')


PromoterAssignmentAdmin.inlines = [PromoterPhotoInline]
