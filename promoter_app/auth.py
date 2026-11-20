from functools import wraps

from django.contrib import messages
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404

from accounts.base import OrganizationRequest
from accounts.consts import USER_ROLES
from accounts.mixins import RoleRequiredMixin
from accounts.models import City
from int.db_context import DatabaseContext
from . import models

APP_KEY = 'my-promoter-app-key-v1'

error_response = JsonResponse({'error': 'Доступ запрещён', 'code': 'ACCESS_DENIED'}, status=403)


async def promoter_request_exists(request: OrganizationRequest) -> tuple[bool, int | None]:
    app_key = request.headers.get('X-APP-KEY')
    api_key = request.headers.get('X-API-KEY')

    if app_key != APP_KEY:
        return False, None

    if not api_key:
        return False, None

    database_alias, promoter_id = await models.PromoterZone.get_promoter_by_api_key(api_key)
    if database_alias:
        DatabaseContext.set(database_alias)
        return True, promoter_id
    else:
        return False, None


def promoter_required(view_func):
    @wraps(view_func)
    async def wrapper(self, request, *args, **kwargs):
        has_promoter, promoter_id = await promoter_request_exists(request)

        if not has_promoter:
            return error_response

        request.promoter_id = promoter_id

        return await view_func(self, request, *args, **kwargs)

    return wrapper


class PromoTreckRequiredMixin(RoleRequiredMixin):
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)

    def additional_permission_checks(self, request: OrganizationRequest, *args, **kwargs):
        current_city_id = request.current_city_id
        if not current_city_id:
            organization_user = request.user.organization_user
            if organization_user.allowed_city_ids:
                current_city_id = organization_user.allowed_city_ids[0]
                organization_user.current_city_id = current_city_id
                organization_user.save(update_fields=['current_city_id'])
            else:
                messages.warning(request, 'Пожалуйста, выберите город для продолжения работы')
                return render(request=request, template_name='promoter_app/base.html')
        self.city = get_object_or_404(City, id=current_city_id)


class PromoAccessChecker:
    """Проверка доступа по выбранному городу"""

    @staticmethod
    def check_promoter_or_404(promoter: models.PromoterProfile, city):
        if promoter.city_id != city.id:
            raise Http404("No PromoterProfile matches the given query.")

    @staticmethod
    def check_assignment_or_404(assignment: models.PromoterAssignment, city):
        if assignment.route_zone.city_id != city.id:
            raise Http404("No PromoterAssignment matches the given query.")
