import logging
from functools import wraps

import dramatiq

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.http import HttpRequest

from accounts.models import OrganizationUser
from identity.models import AuthUser, Organization
from int.db_context import DatabaseContext

logger = logging.getLogger(__name__)


class AuthUserWithOrganizationUser(AuthUser):
    organization_user: OrganizationUser

    class Meta:
        abstract = True


class OrganizationRequest(HttpRequest):
    user: AuthUserWithOrganizationUser
    available_organizations: dict[str, str]
    current_city_id: int
    current_branch_ids: list[int]


def actor(*args, **actor_kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*func_args, **func_kwargs):
            organization = func_kwargs.pop('_organization', None)

            if not organization:
                logger.warning('Task "%s" запущена без указания организации', func.__name__, )
                return func(*func_args, **func_kwargs)

            with DatabaseContext.using(organization):
                return func(*func_args, **func_kwargs)

        dramatiq_actor = dramatiq.actor(*args, **actor_kwargs)(wrapper)

        class OrganizationActor:
            def __init__(self, actor):
                self._actor = actor

            def send(self, *send_args, **send_kwargs):
                db_alias = DatabaseContext.get()

                if not db_alias:
                    logger.warning('Task "%s" отправлена без указания организации', func.__name__, )
                    return self._actor.send(*send_args, **send_kwargs)

                return self._actor.send(*send_args, **send_kwargs, _db_alias=db_alias)

            def send_with_db_alias(self, db_alias, *send_args, **send_kwargs):
                return self._actor.send(*send_args, **send_kwargs, _db_alias=db_alias)

            def __getattr__(self, item):
                return getattr(self._actor, item)

        return OrganizationActor(dramatiq_actor)

    return decorator


class MyAdminSite(AdminSite):
    site_header = 'Панель управления сервисным центром'
    site_title = 'Сервисный центр'
    index_title = 'Администрирование системы'

    def has_permission(self, request: OrganizationRequest):
        user = request.user

        return user.is_active and (user.is_superuser or user.organization_user.is_manager)


class ManagerAdmin(admin.ModelAdmin):
    """
    Базовая админка.

    Доступ имеют:
    - глобальный суперпользователь;
    - менеджер текущей зоны.
    """

    @staticmethod
    def has_access(request: OrganizationRequest):
        if request.user.is_superuser:
            return True

        return request.user.organization_user.is_manager

    def has_module_permission(self, request: OrganizationRequest):
        return self.has_access(request)

    def has_view_permission(self, request: OrganizationRequest, obj=None):
        return self.has_access(request)

    def has_add_permission(self, request):
        return self.has_access(request)

    def has_change_permission(self, request: OrganizationRequest, obj=None):
        return self.has_access(request)

    def has_delete_permission(self, request: OrganizationRequest, obj=None):
        return self.has_access(request)


def create_user_with_role(username, role, first_name='Ф', last_name='И', second_name='О', is_superuser=False,
                          cities=None) -> AuthUser:
    auth_user = AuthUser.objects.create(username=username, first_name=first_name, last_name=last_name,
                                        second_name=second_name, password='password', is_superuser=is_superuser)
    organization, _ = Organization.objects.get_or_create(database_alias=DatabaseContext.get())
    organization.users.add(auth_user)
    organization_user = auth_user.organization_user
    organization_user.role = role
    organization_user.sync_and_save()
    if cities:
        organization_user.cities.set(cities)

    return auth_user
