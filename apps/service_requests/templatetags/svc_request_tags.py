from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.models import OrganizationUser
from ..consts import SPECIFIC_FIELDS_VIEW_BEFORE_MINUTES
from ..models import ServiceRequest

register = template.Library()


@register.filter
def client_phone_for_user(svc_request: ServiceRequest, user: OrganizationUser) -> str:
    """Возвращает номер телефона или заглушку."""
    client_phone = svc_request.client_phone
    if client_phone:
        if svc_request.can_view_specific_fields(user):
            return client_phone
        tooltip_text = f'Будет доступен за {SPECIFIC_FIELDS_VIEW_BEFORE_MINUTES} мин до обслуживания'
        html = f'<span class="text-muted" data-toggle="tooltip" title="{tooltip_text}">{"#" * len(client_phone)}</span>'
        return mark_safe(html)
    return ''


def get_status_color(svc_request: ServiceRequest) -> str:
    """Цвет статуса заявки"""
    statuses = ServiceRequest.STATUS
    color_map = {
        statuses.NEW: 'secondary text-white',
        statuses.ASSIGNED: 'info text-white',
        statuses.ON_WAY: 'primary text-white',
        statuses.IN_PROGRESS: 'warning text-white',
        statuses.SERVICE_DIAGNOSTICS: 'danger text-white',
        statuses.COMPLETED: 'success text-white',
        statuses.CANCELED: 'dark text-white',
    }
    return color_map.get(svc_request.status, 'light')


@register.simple_tag
def get_status_badge(svc_request: ServiceRequest) -> str:
    return format_html(f'''
        <span class="d-inline badge bg-{get_status_color(svc_request)}">
        {svc_request.get_status_display()}
        </span>
    ''')


@register.filter
def is_none(value):
    return value is None
