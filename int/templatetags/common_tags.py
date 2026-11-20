from django import template

from common_tools import number, date

register = template.Library()


@register.filter
def month_name_by_number(month_number):
    return date.MONTH_NAMES_RU.get(month_number, '—')


@register.filter
def format_money(value, decimal_pos: int = 2):
    if value is None:
        return '—'
    return number.format_money(value, decimal_pos)
