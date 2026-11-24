from typing import Any

from django_tables2 import tables

from .number import format_money

# Атрибуты для одинакового отображения таблиц
BOOTSTRAP_TABLE_ATTRS = {'class': 'table table-hover shadow'}


class MoneyColumn(tables.Column):
    """Для денежных значений"""
    def render(self, value: Any) -> str:
        return format_money(value)
