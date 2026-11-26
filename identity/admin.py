from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from accounts.base import OrganizationRequest
from .models import AuthUser, Organization

admin.site.unregister(Group)


@admin.register(AuthUser)
class AuthUserAdmin(UserAdmin):
    list_display = (
        'username', 'authorize', 'last_name', 'first_name', 'second_name', 'is_superuser', 'is_active'
    )
    list_filter = ('is_superuser', 'is_active', 'organizations')
    search_fields = ('username', 'first_name', 'last_name', 'second_name')
    readonly_fields = ('organizations_list',)

    fieldsets = (
        (None, {
            'fields': (
                'username', 'password'
            ),
        }),
        ('Персональная информация', {
            'fields': (
                'last_name', 'first_name', 'second_name', 'email'
            ),
        }),
        ('Права доступа', {
            'fields': (
                'organizations_list', 'is_active', 'is_superuser'
            ),
        }),
        ('Важные даты', {
            'fields': (
                'last_login', 'date_joined'
            ),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'password1', 'password2', 'last_name', 'first_name', 'second_name', 'email', 'is_superuser'
            ),
        }),
    )

    @admin.display(description='Вход')
    def authorize(self, obj):
        url = reverse('identity:authorize')
        return format_html('<a href="{}?username={}">[войти как {}]</a>', url, obj.username, obj.username)

    @admin.display(description='Организации')
    def organizations_list(self, obj):
        if not obj.pk:
            return '—'

        organizations = obj.organizations.all()

        if not organizations.exists():
            return 'Не назначены'

        return format_html_join('', '<div>• {}</div>', ((organization.name,) for organization in organizations))

    def has_module_permission(self, request: OrganizationRequest):
        return request.user.is_superuser

    def has_view_permission(self, request: OrganizationRequest, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request: OrganizationRequest):
        return request.user.is_superuser

    def has_change_permission(self, request: OrganizationRequest, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request: OrganizationRequest, obj=None):
        return request.user.is_superuser


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'database_alias', 'users_count')
    search_fields = ('name', 'database_alias', 'users__username')
    autocomplete_fields = ('users',)
    readonly_fields = ('database_alias',)

    @admin.display(description='Пользователей')
    def users_count(self, obj):
        return obj.users.count()

    def has_module_permission(self, request: OrganizationRequest):
        return request.user.is_superuser

    def has_view_permission(self, request: OrganizationRequest, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request: OrganizationRequest):
        return False

    def has_change_permission(self, request: OrganizationRequest, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request: OrganizationRequest, obj=None):
        return False
