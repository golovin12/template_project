from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.db import close_old_connections

from accounts.models import OrganizationUser
from int.db_context import DatabaseContext
from .models import Organization, AuthUser


class OrganizationMiddleware(MiddlewareMixin):
    """Middleware для выбора текущей организации пользователя."""

    def process_request(self, request):
        if settings.IS_WEB:
            close_old_connections()

        DatabaseContext.set('default')

        if not request.user.is_authenticated:
            return

        auth_user: AuthUser = request.user
        organizations = self.get_available_organizations(auth_user)
        available_organizations = dict(organizations.values_list('database_alias', 'name'))

        if not available_organizations:
            logout(request)
            messages.error(request, 'У вас нет доступа ни к одной организации. Обратитесь к администратору.')
            return redirect('identity:login')

        request.available_organizations = available_organizations

        current_db_alias = request.session.get('current_db_alias')

        if current_db_alias not in available_organizations:
            current_db_alias = next(iter(available_organizations))
            request.session['current_db_alias'] = current_db_alias
            messages.info(request, f'Используется организация "{available_organizations[current_db_alias]}".')

        DatabaseContext.set(current_db_alias)

        organization_user, created = OrganizationUser.objects.get_or_create(
            user_id=auth_user.id,
            defaults={'is_superuser': auth_user.is_superuser},
        )

        if created:
            organization_user.sync_and_save()

        request.user.organization_user = organization_user

        city_session_key = f'current_city_id:{current_db_alias}'
        city_id = request.session.get(city_session_key)

        if city_id in organization_user.allowed_city_ids:
            request.current_city_id = city_id
        else:
            request.current_city_id = None
            request.session.pop(city_session_key, None)

    @staticmethod
    def get_available_organizations(user: AuthUser):
        if user.is_superuser:
            return Organization.objects.order_by('name')
        return user.organizations.order_by('name')

    def process_response(self, request, response):
        if settings.IS_WEB:
            close_old_connections()
        DatabaseContext.set('default')
        return response

    def process_exception(self, request, exception):
        if settings.IS_WEB:
            close_old_connections()
        DatabaseContext.set('default')
        return None
