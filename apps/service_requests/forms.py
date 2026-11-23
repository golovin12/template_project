from decimal import Decimal

from django_select2.forms import Select2Widget, Select2MultipleWidget

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from accounts.form import BranchControlMixin
from accounts.models import Branch
from common_tools.form import WithoutPlaceholderMixin, PhoneField
from common_tools.widgets import DateWidget, DateTimeWidget
from .controllers import RequestController
from .form import DeviceTypeControlMixin
from .models import ServiceRequest, DeviceType

validate_full_name = RegexValidator(r'^[А-ЯЁа-яё]+(?:-[А-ЯЁа-яё]+)? [А-ЯЁа-яё]+(?: [А-ЯЁа-яё]+)?$')


class ServiceRequestCreateForm(BranchControlMixin, DeviceTypeControlMixin, WithoutPlaceholderMixin, forms.ModelForm):
    client_phone = PhoneField(label='Телефон для связи', required=False)

    class Meta:
        model = ServiceRequest
        fields = ('request_type', 'branch', 'client_name', 'client_phone', 'client_address', 'problem_description',
                  'time_to_service', 'device_type')
        widgets = {
            'request_type': Select2Widget(attrs={'style': 'opacity: 0'}),
            'problem_description': forms.Textarea(attrs={'rows': 3}),
            'time_to_service': DateTimeWidget(attrs={'data-position': 'top right'}),
        }

    def clean(self):
        cd = self.cleaned_data
        branch = cd.get('branch')
        device_type = cd.get('device_type')
        if device_type and branch and device_type not in DeviceType.get_names(branch.pk):
            self.add_error('device_type', 'Этот тип техники не доступен в выбранном филиале!')
        return cd

    def save(self, commit=True):
        instance: ServiceRequest = super().save(commit=False)
        return RequestController.create_request(instance, self.request.user.organization_user, commit)


class ServiceRequestUpdateForm(BranchControlMixin, DeviceTypeControlMixin, WithoutPlaceholderMixin, forms.ModelForm):
    closing_amount = forms.DecimalField(label='Прибыль (руб.)', required=False, min_value=0, decimal_places=2,
                                        max_digits=10)
    client_phone = PhoneField(label='Телефон для связи', required=False)
    other_expenses = forms.DecimalField(label='Прочие затраты (руб.)', required=False, min_value=0, decimal_places=2,
                                        max_digits=10)

    class Meta:
        model = ServiceRequest
        fields = ('request_type', 'branch', 'client_name', 'client_phone', 'client_address', 'problem_description',
                  'status', 'service_report', 'other_expenses', 'closing_amount', 'time_to_service', 'sd_closing_date',
                  'device_type')
        widgets = {
            'request_type': Select2Widget(attrs={'style': 'opacity: 0'}),
            'status': Select2Widget(attrs={'style': 'opacity: 0'}),
            'problem_description': forms.Textarea(attrs={'rows': 3}),
            'service_report': forms.Textarea(attrs={'rows': 3}),
            'time_to_service': DateTimeWidget(),
            'sd_closing_date': DateWidget(),
        }

    def clean_status(self):
        if self.instance.is_completed:
            raise ValidationError('Нельзя внести изменения в уже закрытую заявку!')
        return self.cleaned_data['status']

    def clean(self):
        cd = self.cleaned_data
        closing_amount = cd.get('closing_amount') or 0
        other_expenses = cd.get('other_expenses') or 0
        branch = cd.get('branch')
        device_type = cd.get('device_type')
        if other_expenses > closing_amount:
            self.add_error('other_expenses', 'Расходы не могут превышать прибыль!')
        if cd.get('status') == ServiceRequest.STATUS.COMPLETED:
            if cd.get('closing_amount') is None:
                self.add_error('closing_amount', 'Для закрытия заявки необходимо указать сумму закрытия!')
            if cd.get('other_expenses') is None:
                self.add_error('other_expenses', 'Для закрытия заявки необходимо указать расходы!')
        if device_type and branch and device_type not in DeviceType.get_names(branch.pk):
            self.add_error('device_type', 'Этот тип техники не доступен в выбранном филиале!')
        return cd


class ServiceRequestCityAdminUpdateForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ('time_to_service', 'sd_closing_date')
        widgets = {
            'time_to_service': DateTimeWidget(),
            'sd_closing_date': DateWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status != ServiceRequest.STATUS.SERVICE_DIAGNOSTICS:
            self.fields.pop('sd_closing_date')
        else:
            self.fields.pop('time_to_service')


class ServiceRequestCompleteForm(WithoutPlaceholderMixin, forms.ModelForm):
    closing_amount = forms.DecimalField(label='Прибыль (руб.)', required=True, min_value=0, decimal_places=2,
                                        max_digits=10)
    other_expenses = forms.DecimalField(label='Прочие затраты (руб.)', min_value=0, decimal_places=2, max_digits=10)

    class Meta:
        model = ServiceRequest
        fields = ('closing_amount', 'other_expenses', 'service_report')
        widgets = {
            'service_report': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status == ServiceRequest.STATUS.SERVICE_DIAGNOSTICS and not self.instance.service_report:
            self.initial['service_report'] = 'Диагностика выполнена.'

    def clean(self):
        if self.instance.is_status_end:
            raise ValidationError('Нельзя завершить уже закрытую заявку.')

        cd = self.cleaned_data
        closing_amount = cd.get('closing_amount') or Decimal(0)
        other_expenses = cd.get('other_expenses') or Decimal(0)
        if other_expenses > closing_amount:
            self.add_error('other_expenses', 'Расходы не могут превышать прибыль!')
        return cd

    def save(self, commit=True):
        instance = super().save(commit=False)
        return RequestController.complete_request(instance, commit)


class ServiceRequestDiagnosticForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = ServiceRequest
        fields = ('service_report', 'sd_closing_date')
        widgets = {
            'service_report': forms.Textarea(attrs={'rows': 3}),
            'sd_closing_date': DateWidget(),
        }

    def clean(self):
        cleaned_data = super().clean()

        if self.instance.is_status_end:
            raise ValidationError('Нельзя перевести в диагностику уже закрытую заявку.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        return RequestController.start_diagnostics(instance, commit)


class DeviceTypeCreateForm(WithoutPlaceholderMixin, forms.ModelForm):
    """Форма создания типа техники с выбором филиалов"""

    class Meta:
        model = DeviceType
        fields = ('name', 'is_available_for_all', 'branches')
        widgets = {
            'branches': Select2MultipleWidget(attrs={'style': 'opacity: 0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['branches'].queryset = Branch.active_objects
        self.fields['branches'].required = False
        self.fields['branches'].help_text = 'Выберите филиалы, в которых будет доступен этот тип техники.'

        for field_name, field in self.fields.items():
            if field_name != 'is_available_for_all':
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-check-input'

    def clean(self):
        cleaned_data = super().clean()
        is_available_for_all = cleaned_data.get('is_available_for_all')
        branches = cleaned_data.get('branches')

        if is_available_for_all:
            cleaned_data['branches'] = self.fields['branches'].queryset.none()
        elif not branches:
            raise forms.ValidationError(
                'Выберите хотя бы один филиал или отметьте "Доступно для всех филиалов"'
            )
        return cleaned_data


class DeviceTypeUpdateForm(DeviceTypeCreateForm):
    """Форма редактирования типа техники"""

    class Meta(DeviceTypeCreateForm.Meta):
        fields = DeviceTypeCreateForm.Meta.fields
