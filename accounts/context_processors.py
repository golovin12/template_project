from .base import OrganizationRequest


def user_roles(request: OrganizationRequest):
    user = request.user
    if not user.is_authenticated:
        return {}

    organization_user = user.organization_user
    return {
        'is_manager': organization_user.is_manager,
        'is_city_admin': organization_user.is_city_admin,
        'is_chief': organization_user.is_chief,
    }
