from django_tables2 import tables

from django.urls import reverse
from django.utils.safestring import mark_safe

from accounts.base import OrganizationRequest
from accounts.models import City
from common_tools.number import format_money
from common_tools.table import MoneyColumn
from .models import AccountingEntry


class DashboardTable(tables.Table):
    actions = tables.Column(verbose_name='Ссылки', empty_values=(), orderable=False)
    balance = MoneyColumn(verbose_name='Баланс', empty_values=(), orderable=False)

    class Meta:
        fields = ('name', 'balance', 'actions')
        model = City
        attrs = {'class': 'table table-hover shadow table-responsive-md'}

    def render_balance(self, record: City):
        balance = AccountingEntry.get_city_balance(record.id)
        color = 'text-success' if balance >= 0 else 'text-danger'
        return mark_safe(f'<span class ="{color}">{format_money(balance)} руб.</span>')

    def render_actions(self, record: City):
        bookkeeping_btn = f'''
            <a class="btn btn-sm btn-outline-success" title="Бухгалтерия"
               href="{reverse("bookkeeping:entry_list")}?city={record.pk}">
                <i class="material-icons align-bottom">request_quote</i>
                <span class="d-none d-sm-inline"> Бухгалтерия</span>
            </a>
        '''
        statistic_btn = f'''
            <a class="btn btn-sm btn-primary" title="Статистика"
               href="{reverse("statistics:city_detail", args=(record.pk,))}">
                <i class="material-icons align-bottom">bar_chart</i>
                <span class="d-none d-sm-inline"> Статистика</span>
            </a>
        '''
        return mark_safe(f'<div class="text-nowrap">{bookkeeping_btn}{statistic_btn}<div>')


def get_entry_type_color(entry_type: str) -> str:
    """Получение цвета бухгалтерской записи"""
    if entry_type == AccountingEntry.ENTRY_TYPE.INCOME:
        return 'success'
    elif entry_type == AccountingEntry.ENTRY_TYPE.EXPENSE:
        return 'danger'
    return 'light'


class AccountingEntryTable(tables.Table):
    branch = tables.Column(verbose_name='Филиал', empty_values=())
    request_link = tables.Column(verbose_name='Заявка', empty_values=(), orderable=False)
    amount = MoneyColumn()

    class Meta:
        fields = ('created_dt', 'created_by', 'branch', 'entry_type', 'amount', 'description', 'request_link')
        model = AccountingEntry
        attrs = {'class': 'table table-hover shadow table-responsive-md'}
        row_attrs = {
            'class': lambda record: f'table-{get_entry_type_color(record.entry_type)}'
        }

    def before_render(self, request: OrganizationRequest):
        if not request.user.organization_user.is_manager:
            self.columns.hide('created_by')

    def render_branch(self, record: AccountingEntry):
        city_name = record.city.name if record.city else ''
        branch_name = f' ({record.branch.name})' if record.branch else ''
        return f'{city_name}{branch_name}'

    def render_entry_type(self, record: AccountingEntry):
        entry_type_class = f'badge bg-{get_entry_type_color(record.entry_type)} text-white'
        return mark_safe(f'<span class ="{entry_type_class}">{record.get_entry_type_display()}</span>')

    def render_description(self, record: AccountingEntry):
        photo_link = f'''
            <a target="_blank" class="btn btn-sm btn-primary" href={record.receipt_photo.url} title="Фото чека">
                <i class="material-icons align-bottom">receipt</i>
            </a>
        ''' if record.receipt_photo else ''
        return mark_safe(f'{record.description}{photo_link}')

    def render_request_link(self, record: AccountingEntry):
        detail_url = f'''
            <a class="btn btn-sm btn-info" href={reverse("service_request:request_detail",
                                                         args=(record.service_request.pk,))} title="Просмотр">
                #{record.service_request.request_number}
            </a>
        ''' if record.service_request else '—'
        return mark_safe(f'<div class="text-nowrap">{detail_url}<div>')
