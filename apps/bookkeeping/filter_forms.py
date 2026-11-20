from django_select2.forms import Select2Widget

from django import forms
from django.db.models import QuerySet

from accounts.base import OrganizationRequest
from accounts.form import BranchControlFilterMixin, CachedCityChoiceField
from accounts.models import City
from common_tools.date import parse_dates_from_string, get_last_day_prev_month
from common_tools.form import BaseFilterForm
from common_tools.widgets import DateRangeWidget
from .models import AccountingEntry


class DashboardFilterForm(BaseFilterForm):
    field_order = ('city', 'per_page')
    city = forms.ChoiceField(choices=())

    def __init__(self, request: OrganizationRequest):
        self.base_fields['city'] = CachedCityChoiceField(user=request.user.organization_user)
        super().__init__(request)

    def _filtration(self, qs: QuerySet[City]):
        cd = self.cleaned_data
        if city := cd.get('city'):
            qs = qs.filter(pk=city.pk)
        return qs


class AccountingEntryFilterForm(BranchControlFilterMixin, BaseFilterForm, forms.ModelForm):
    filter_update_fields = ('added_range',)
    added_range = forms.CharField(label='Период добавления', max_length=23,
                                  widget=DateRangeWidget(attrs=dict(style='width: 12rem;')))
    number = forms.CharField(label='Номер заявки')
    expense_subtype = forms.ChoiceField(
        label='Вид расходов',
        widget=Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Вид расходов'}),
        choices=AccountingEntry.EXPENSE_SUBTYPE.CHOICES,
    )
    entry_types = forms.ChoiceField(
        label='Тип',
        widget=Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Тип'}),
        choices=(
            *AccountingEntry.ENTRY_TYPE.CHOICES,
            ('manual_income', 'Доходы (вручную)'),
            ('manual_expense', 'Расходы (вручную)'),
        ),
    )

    class Meta:
        model = AccountingEntry
        fields = ('city', 'branch', 'entry_types', 'expense_subtype', 'added_range', 'description', 'number')
        widgets = {'description': forms.TextInput()}

    def __init__(self, request: OrganizationRequest, *args, **kwargs):
        self.base_fields['city'] = CachedCityChoiceField(user=request.user.organization_user)
        super().__init__(*args, request=request, **kwargs)
        self.fields['number'].widget.attrs['style'] = 'max-width: 10em'

        if self.fields['city'].disabled:
            self.fields.pop('city')

    def clean_added_range(self):
        if self.request.GET.get('as_month'):
            last_day = get_last_day_prev_month()
            first_day = last_day.replace(day=1)
            return f'{first_day.strftime("%d.%m.%Y")} - {last_day.strftime("%d.%m.%Y")}'
        return self.cleaned_data['added_range']

    def clean_branch(self):
        return self.cleaned_data[self.branch_field]

    def _choose_branch(self):
        return

    def _filtration(self, qs: QuerySet[AccountingEntry]):
        cd = self.cleaned_data

        if number := cd.get('number'):
            qs = qs.filter(service_request__request_number=number.lstrip('#'))
        if description := cd.get('description'):
            qs = qs.filter(description__icontains=description)
        if added_range := cd.get('added_range'):
            added_range_start, added_range_end = parse_dates_from_string(added_range)
            if added_range_start:
                qs = qs.filter(created_dt__date__gte=added_range_start)
                if added_range_end:
                    qs = qs.filter(created_dt__date__lte=added_range_end)
        if branch := cd.get('branch'):
            qs = qs.filter(branch=branch)
        elif city := cd.get('city'):
            qs = qs.filter(city=city)
        if expense_subtype := cd.get('expense_subtype'):
            qs = qs.filter(entry_type=AccountingEntry.ENTRY_TYPE.EXPENSE, expense_subtype=expense_subtype)
        if entry_type := cd.get('entry_types'):
            is_manual = entry_type.startswith('manual_')
            base_type = entry_type.removeprefix('manual_')
            filters = {'entry_type': base_type}
            if is_manual:
                filters['service_request__isnull'] = True
            qs = qs.filter(**filters)
        return qs
