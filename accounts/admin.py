import re

from django_dramatiq.admin import TaskAdmin
from django_dramatiq.models import Task

from django.contrib import admin
from django.utils.html import format_html_join

from .base import ManagerAdmin, OrganizationRequest
from .models import Branch, City, OrganizationUser


@admin.register(OrganizationUser)
class CustomUserAdmin(ManagerAdmin):
    list_display = (
        'user_id', 'username', 'is_global_superuser', 'is_superuser', 'role', 'allowed_cities', 'last_name',
        'first_name', 'second_name'
    )
    list_filter = ('role', 'cities', 'all_cities_access', 'is_global_superuser', 'is_superuser')
    search_fields = ('username', 'user_id', 'last_name', 'first_name', 'second_name')
    autocomplete_fields = ('cities',)
    readonly_fields = ('user_id', 'username', 'first_name', 'last_name', 'second_name', 'is_global_superuser')

    fieldsets = (
        (None, {
            'fields': (
                'user_id', 'username'
            ),
        }),
        ('Персональная информация', {
            'fields': (
                'last_name', 'first_name', 'second_name'
            ),
        }),
        ('Права доступа', {
            'fields': (
                'is_global_superuser', 'is_superuser', 'role', 'cities', 'all_cities_access'
            ),
        }),
    )

    @admin.display(description='Города')
    def allowed_cities(self, obj: OrganizationUser):
        if obj.all_cities_access or obj.is_manager:
            return 'Все города'

        cities = obj.allowed_city_choices

        if not cities:
            return 'Не назначены'

        return format_html_join('', '<div>• {}</div>', ((name,) for _, name in cities))

    def has_add_permission(self, request: OrganizationRequest) -> bool:
        return False

    def has_delete_permission(self, request: OrganizationRequest, obj=None) -> bool:
        return False


@admin.register(City)
class CityAdmin(ManagerAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Branch)
class BranchAdmin(ManagerAdmin):
    list_display = ('branch_title', 'is_active')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'city__name')
    autocomplete_fields = ('city',)
    ordering = ('city__name', 'name')

    @admin.display(description='Филиал', ordering='city__name')
    def branch_title(self, obj):
        return f'{obj.city} ({obj.name})'


admin.site.unregister(Task)


@admin.register(Task)
class SimpleTaskAdmin(TaskAdmin):
    list_per_page = 50
    list_display = ('task_detail', 'status', 'eta', 'created_at', 'updated_at', 'queue_name', 'actor_name')

    @admin.display(description='Задача')
    def task_detail(self, obj: Task):
        text = re.sub(r'\\+', r'\\', str(obj))
        text = re.sub(r'\^+', '^', text)
        return text
