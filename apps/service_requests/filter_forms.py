from django_select2.forms import Select2Widget

from django import forms
from django.core.validators import RegexValidator
from django.db.models import QuerySet, Count, Q
from django.utils import timezone

from accounts.form import BranchControlFilterMixin, CachedCityChoiceField
from accounts.models import OrganizationUser
from common_tools.date import parse_dates_from_string, get_last_day_prev_month
from common_tools.form import BaseFilterForm, PhoneField
from common_tools.widgets import DateRangeWidget
from .form import DeviceTypeControlMixin
from .models import ServiceRequest

request_number_validator = RegexValidator(r'^#?\d*$', 'Номер заявки должен состоять из цифр')


class ServiceRequestFilterPhoneForm(forms.Form):
    client_phone = PhoneField(label='Поиск по телефону', is_search=True)


class CreatedServiceRequestsFilterForm(BaseFilterForm, forms.ModelForm):
    """Форма фильтрации для просмотра количества созданных заявок"""
    filter_update_fields = ('created_period',)
    full_name = forms.CharField(label='ФИО')
    city = CachedCityChoiceField(label='Город заявок')
    created_period = forms.CharField(label='Период создания', max_length=23,
                                     widget=DateRangeWidget(attrs=dict(style='width: 12rem;')))

    class Meta:
        model = OrganizationUser
        fields = ('full_name', 'city', 'created_period')

    def clean_created_period(self):
        if self.request.GET.get('as_month'):
            last_day = get_last_day_prev_month()
            first_day = last_day.replace(day=1)
            return f'{first_day.strftime("%d.%m.%Y")} - {last_day.strftime("%d.%m.%Y")}'
        return self.cleaned_data['created_period']

    def _filtration(self, qs: QuerySet[OrganizationUser]):
        cd = self.cleaned_data

        if full_name := cd.get('full_name'):
            qs = qs.filter(search_full_name__icontains=full_name.strip())

        requests_filter = Q()
        if city := cd.get('city'):
            requests_filter &= Q(created_requests__city=city)
        if created_period := cd.get('created_period'):
            created_period_start, created_period_end = parse_dates_from_string(created_period)
            if created_period_start:
                requests_filter &= Q(created_requests__request_time__date__gte=created_period_start)
            if created_period_end:
                requests_filter &= Q(created_requests__request_time__date__lte=created_period_end)

        return qs.annotate(counts=Count('created_requests', filter=requests_filter))


class ServiceRequestFilterForm(BranchControlFilterMixin, DeviceTypeControlMixin, BaseFilterForm, forms.ModelForm):
    """Форма фильтрации для заявок"""
    filter_update_fields = ('condition',)

    number = forms.CharField(label='Номер заявки', validators=[request_number_validator])
    client_phone = PhoneField(label='Телефон', widget_style='width: 10rem;')
    service_date_range = forms.CharField(label='Период обслуживания', max_length=23,
                                         widget=DateRangeWidget(attrs=dict(style='width: 12rem;')))
    closing_date_range = forms.CharField(label='Период закрытия', max_length=23,
                                         widget=DateRangeWidget(attrs=dict(style='width: 12rem;')))
    condition = forms.ChoiceField(label='Статус',
                                  widget=Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Статус'}),
                                  choices=(('all', 'Все'), ('in_process', 'В работе'), ('diagnostic', 'Диагностика'),
                                           ('completed', 'Завершена'), ('canceled', 'Отменена')))
    sd_closing_today = forms.BooleanField(label='Закрыть сегодня')

    class Meta:
        model = ServiceRequest
        fields = (
            'number', 'client_phone', 'service_date_range', 'branch', 'request_type', 'device_type', 'condition',
            'closing_date_range', 'sd_closing_today'
        )
        widgets = {
            'request_type': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Тип заявки'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.request.GET.get('condition') != 'diagnostic':
            self.fields.pop('sd_closing_today')
        self.fields['number'].widget.attrs['style'] = 'max-width: 10em'

    def clean_condition(self):
        # По умолчанию - отображаем только заявки "В работе"
        condition = self.cleaned_data['condition']
        if self.request.GET.get('req_all'):
            condition = 'all'
        elif self.request.GET.get('req_diag'):
            condition = 'diagnostic'
        elif not condition:
            condition = 'in_process'
        return condition

    def _filtration(self, qs: QuerySet[ServiceRequest]):
        cd = self.cleaned_data
        if branch := cd.get('branch'):
            qs = qs.filter(branch=branch)
        if number := cd.get('number'):
            qs = qs.filter(request_number=number.lstrip('#'))
        if service_date_range := cd.get('service_date_range'):
            service_range_start, service_range_end = parse_dates_from_string(service_date_range)
            if service_range_start:
                qs = qs.filter(time_to_service__date__gte=service_range_start)
                if service_range_end:
                    qs = qs.filter(time_to_service__date__lte=service_range_end)
        if closing_date_range := cd.get('closing_date_range'):
            closing_range_start, closing_range_end = parse_dates_from_string(closing_date_range)
            if closing_range_start:
                qs = qs.filter(closing_time__date__gte=closing_range_start)
                if closing_range_end:
                    qs = qs.filter(closing_time__date__lte=closing_range_end)
        if request_type := cd.get('request_type'):
            qs = qs.filter(request_type=request_type)
        if device_type := cd.get('device_type'):
            qs = qs.filter(device_type=device_type)
        if client_phone := cd.get('client_phone'):
            qs = qs.filter(client_phone=client_phone)
        if condition := cd.get('condition'):
            if condition == 'completed':
                qs = qs.filter(status=ServiceRequest.STATUS.COMPLETED)
            elif condition == 'canceled':
                qs = qs.filter(status=ServiceRequest.STATUS.CANCELED)
            elif condition == 'in_process':
                qs = qs.filter(status__in=(ServiceRequest.STATUS.NEW, ServiceRequest.STATUS.ASSIGNED,
                                           ServiceRequest.STATUS.ON_WAY, ServiceRequest.STATUS.IN_PROGRESS))
                qs = qs.order_by('time_to_service')
            elif condition == 'diagnostic':
                qs = qs.filter(status=ServiceRequest.STATUS.SERVICE_DIAGNOSTICS)
                qs = qs.order_by('time_to_service')
        if cd.get('sd_closing_today'):
            qs = qs.filter(sd_closing_date=timezone.now().date())
        return qs
