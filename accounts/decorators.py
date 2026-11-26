from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .base import OrganizationRequest
from .consts import USER_ROLES


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request: OrganizationRequest, *args, **kwargs):
            organization_user = request.user.organization_user

            if organization_user.role not in roles and not organization_user.is_manager:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


manager_required = role_required(USER_ROLES.MANAGER)
city_admin_required = role_required(USER_ROLES.CITY_ADMIN)
chief_required = role_required(USER_ROLES.CHIEF)
