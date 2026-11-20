from django_tables2 import tables

from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.base import OrganizationRequest
from accounts.models import Branch, OrganizationUser
from common_tools.table import MoneyColumn, BOOTSTRAP_TABLE_ATTRS
from common_tools.text import truncate_text
from .models import ServiceRequest, DeviceType
from .templatetags.svc_request_tags import get_status_badge


class CreatedServiceRequestsTable(tables.Table):
    search_full_name = tables.Column(verbose_name='ФИО')
    counts = tables.Column(verbose_name='Кол-во заявок')

    class Meta:
        fields = ('search_full_name', 'counts')
        model = OrganizationUser
        attrs = BOOTSTRAP_TABLE_ATTRS


class ServiceRequestTable(tables.Table):
    request: OrganizationRequest
    links = tables.Column(verbose_name='Действие', empty_values=(), orderable=False)
    closing_amount = MoneyColumn(verbose_name='Прибыль (руб.)')

    class Meta:
        fields = ('request_number', 'sd_closing_date', 'time_to_service', 'branch', 'request_type', 'client_name',
                  'client_address', 'problem_description', 'closing_amount', 'status', 'links')
        model = ServiceRequest
        attrs = {'class': 'table table-hover shadow table-responsive-xl'}

    def before_render(self, request: OrganizationRequest):
        if request.GET.get('condition') == 'diagnostic':
            self.columns.hide('time_to_service')
        else:
            self.columns.hide('sd_closing_date')

    def render_branch(self, record: ServiceRequest):
        branch_choices = Branch.get_active_choices()
        income_branch_id = record.branch_id
        for branch_id, branch_name in branch_choices:
            if branch_id == income_branch_id:
                return branch_name
        return str(record.branch)

    def render_request_number(self, record: ServiceRequest):
        detail_url = f'''
            <a class="font-weight-bold" href={reverse("service_request:request_detail",
                                                      args=(record.pk,))} title="Просмотр">
                #{record.request_number}
            </a>
        '''
        return mark_safe(f'<div class="text-nowrap">{detail_url}<div>')

    def render_status(self, record: ServiceRequest):
        return mark_safe(get_status_badge(record))

    def render_problem_description(self, record: ServiceRequest):
        device_type = '' if not record.device_type else f'{record.device_type}: '
        return format_html('{}', f'{device_type}{truncate_text(record.problem_description, 180)}')

    def render_links(self, record: ServiceRequest):
        detail_link = f'''
               <a href={reverse("service_request:request_detail", args=(record.pk,))} title="Просмотр">
                   <i class="material-icons align-top text-primary">info</i>
               </a>
           '''
        edit_link = f'''
               <a href={reverse("service_request:request_update", args=(record.pk,))} title="Редактировать">
                   <i class="material-icons align-top text-warning">edit</i>
               </a>
           '''
        copy_link = f'''
               <a href={reverse("service_request:request_copy", args=(record.pk,))} title="Создать копию">
                   <i class="material-icons align-top text-info">difference</i>
               </a>
           ''' if record.is_completed else ''
        return format_html(
            '''
            <div class="text-nowrap">
                {}{}{}
                <a href="#" class="copy-btn" data-text="{}" title="Копировать данные заявки">
                    <i class="material-icons align-top text-secondary">content_copy</i>
                </a>
            <div>''',
            mark_safe(detail_link),
            mark_safe(edit_link),
            mark_safe(copy_link),
            record.get_data_to_text())


class DeviceTypeTable(tables.Table):
    branches = tables.Column('Филиалы', empty_values=(), orderable=False)
    actions = tables.Column('Действия', empty_values=(), orderable=False)

    class Meta:
        fields = ('name', 'branches', 'actions')
        model = DeviceType
        attrs = {'class': 'table table-hover shadow table-responsive-sm'}

    def render_branches(self, record: DeviceType):
        """Отображение филиалов с иконкой"""
        if record.is_available_for_all:
            return format_html(
                '<span class="badge badge-success">Все филиалы</span>'
            )

        device_branches = set(record.get_available_branches().values_list('id', flat=True))
        if not device_branches:
            return format_html(
                '<span class="badge badge-warning">Нет доступных филиалов</span>'
            )
        branch_choices = Branch.get_active_choices()

        branches_html = '<br>'.join((
            f'<span class="badge badge-primary mr-1">{branch_name}</span>'
            for branch_id, branch_name in branch_choices if branch_id in device_branches))
        return format_html(branches_html)

    def render_actions(self, record: DeviceType):
        """Кнопки действий"""
        update_url = reverse('service_request:device_type_update', kwargs={'pk': record.id})
        delete_url = reverse('service_request:device_type_delete', kwargs={'pk': record.id})

        return format_html(
            '''
            <div class="btn-group btn-group-sm" role="group">
                <button type="button" class="btn btn-outline-primary mr-2" title="Редактировать"
                        onclick="ajaxLoadForm('{}', '#deviceUpdateModal', '#deviceUpdate', '#deviceUpdateBody')">
                    <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
                    <i class="material-icons align-bottom">edit</i>
                </button>
                <button class="btn btn-outline-danger" onclick="confirmDelete('{}', '{}?delete=true')"
                        title="Удалить тип техники">
                    <i class="material-icons align-bottom">delete</i>
                </button>
            </div>
            ''',
            update_url,
            record.name,
            delete_url
        )
