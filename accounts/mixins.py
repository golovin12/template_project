from typing import TypeVar

from django.contrib.auth.mixins import AccessMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Model, QuerySet
from django.http import JsonResponse

from .base import OrganizationRequest
from .consts import USER_ROLES

T = TypeVar('T', bound=Model)


class ForSuperUserMixin(UserPassesTestMixin):
    """Миксин: разрешить только для суперпользователей"""

    def test_func(self):
        return self.request.user.is_superuser


class RoleRequiredMixin(AccessMixin):
    """Миксин: разрешить только для ролей из roles_required. Поддерживает AJAX запросы."""
    roles_required = None
    request: OrganizationRequest

    def dispatch(self, request: OrganizationRequest, *args, **kwargs):
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true'

        error_response = self.check_permissions(request, is_ajax)
        if error_response:
            return error_response

        if hasattr(self, 'additional_permission_checks'):
            result = self.additional_permission_checks(request, *args, **kwargs)
            if result:
                return result

        return super().dispatch(request, *args, **kwargs)

    def check_permissions(self, request: OrganizationRequest, is_ajax=False):
        """Проверяет права доступа и возвращает ответ при ошибке"""
        auth_user = request.user
        if not auth_user.is_authenticated:
            return self.get_error_response(is_ajax, status=401, error_code='AUTH_REQUIRED',
                                           message='Необходимо авторизоваться')

        organization_user = auth_user.organization_user
        if self.roles_required and (
                organization_user.role not in self.roles_required and not organization_user.is_manager):
            return self.get_error_response(is_ajax, status=403, error_code='NO_PERMISSION',
                                           message='У вас нет прав для выполнения этого действия',
                                           extra_data={'required_roles': list(self.roles_required)})
        return None

    def get_error_response(self, is_ajax: bool, status: int, error_code: str, message: str, extra_data: dict = None):
        """Возвращает ответ в нужном формате в зависимости от типа запроса"""
        if is_ajax:
            response_data = {'success': False, 'error': error_code, 'message': message}
            if extra_data:
                response_data.update(extra_data)
            return JsonResponse(response_data, status=status)

        if status == 401:
            return self.handle_no_permission()
        elif status == 403:
            raise PermissionDenied(message)

        return self.handle_no_permission()


class ManagerRequiredMixin(RoleRequiredMixin):
    roles_required = (USER_ROLES.MANAGER,)


class CityAdminRequiredMixin(RoleRequiredMixin):
    roles_required = (USER_ROLES.CITY_ADMIN,)


class ChiefRequiredMixin(RoleRequiredMixin):
    roles_required = (USER_ROLES.CHIEF,)


class BranchControlHelperMixin:
    request: OrganizationRequest

    def get_filter_by_branch(self, field='branch') -> dict:
        organization_user = self.request.user.organization_user
        filter_kwargs = {}
        if self.request.current_city_id or not organization_user.all_cities_access:
            filter_kwargs[f'{field}__in'] = self.request.current_branch_ids
        return filter_kwargs

    def apply_branch_restriction(self, qs: QuerySet[T], field='branch') -> QuerySet[T]:
        filter_by_branch = self.get_filter_by_branch(field)
        qs = qs.filter(**filter_by_branch)
        if field.endswith('s'):
            qs = qs.distinct()
        return qs


class UserBranchControlMixin(BranchControlHelperMixin):
    """Ограничение доступа к объекту по филиалу (если пользователь ограничен филиалом)"""
    branch_restriction_field = 'branch'

    def get_queryset(self) -> QuerySet[T]:
        qs = super().get_queryset()
        return self.apply_branch_restriction(qs, self.branch_restriction_field)


class CityControlHelperMixin:
    request = OrganizationRequest

    def get_city_filter_kwargs(self, field='city') -> dict:
        organization_user = self.request.user.organization_user
        filter_kwargs = {}

        if self.request.current_city_id:
            filter_kwargs[field] = self.request.current_city_id
        elif not organization_user.all_cities_access and not organization_user.is_manager:
            filter_kwargs[f'{field}__in'] = organization_user.allowed_city_ids
        return filter_kwargs

    def apply_city_restriction(self, qs: QuerySet[T], field='city') -> QuerySet[T]:
        filter_by_branch = self.get_city_filter_kwargs(field)
        qs = qs.filter(**filter_by_branch)
        if field.endswith('s'):
            qs = qs.distinct()
        return qs


class UserCityControlMixin(CityControlHelperMixin):
    """Ограничение доступа к объекту по городу (если пользователь ограничен городом)"""
    city_restriction_field = 'city'

    def get_queryset(self) -> QuerySet[T]:
        qs = super().get_queryset()
        return self.apply_city_restriction(qs, self.city_restriction_field)
