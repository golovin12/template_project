from django_select2.forms import Select2Widget

from django import forms
from django.db.models import QuerySet

from common_tools.date import parse_dates_from_string
from common_tools.form import BaseFilterForm
from common_tools.widgets import DateRangeWidget
from .consts import Version
from .models import PromoterAssignment


class PromoterAssignmentFilterForm(BaseFilterForm, forms.ModelForm):
    assigned_range = forms.CharField(label='Период назначения', max_length=23,
                                     widget=DateRangeWidget(attrs=dict(style='width: 12rem;')))

    class Meta:
        model = PromoterAssignment
        fields = ('promoter', 'assigned_range', 'route_zone', 'status')
        widgets = {
            'promoter': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Промоутер'}),
            'route_zone': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Маршрут'}),
            'status': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Статус'}),
        }

    def _filtration(self, qs: QuerySet[PromoterAssignment]):
        cd = self.cleaned_data

        if promoter := cd.get('promoter'):
            qs = qs.filter(promoter=promoter)
        if route_zone := cd.get('route_zone'):
            qs = qs.filter(route_zone=route_zone)
        if status := cd.get('status'):
            qs = qs.filter(status=status)
        if assigned_range := cd.get('assigned_range'):
            assigned_range_start, assigned_range_end = parse_dates_from_string(assigned_range)
            if assigned_range_start:
                qs = qs.filter(assigned_date__date__gte=assigned_range_start)
                if assigned_range_end:
                    qs = qs.filter(assigned_date__date__lte=assigned_range_end)
        return qs


class PromotersFilterForm(BaseFilterForm):
    nickname = forms.CharField(label='Ник', widget=forms.TextInput(attrs={'placeholder': 'Ник промоутера'}))

    class Meta:
        fields = ('nickname',)

    def _filtration(self, qs):
        nickname = self.cleaned_data.get('nickname')

        if nickname:
            qs = qs.filter(nickname__icontains=nickname)

        return qs


class AppVersionsForm(forms.Form):
    android_minimum = forms.CharField(label='Android: минимальная версия')
    android_latest = forms.CharField(label='Android: последняя версия')
    ios_minimum = forms.CharField(label='iOS: минимальная версия')
    ios_latest = forms.CharField(label='iOS: последняя версия')

    def clean(self):
        cleaned = super().clean()

        fields = ('android_minimum', 'android_latest', 'ios_minimum', 'ios_latest')
        for field in fields:
            try:
                Version.from_string(cleaned[field])
            except Exception:
                self.add_error(field, 'Некорректная версия')

        if Version.try_parse(cleaned['android_minimum']) > Version.try_parse(cleaned['android_latest']):
            self.add_error('android_latest', 'Последняя версия должна быть не меньше минимальной.')

        if Version.try_parse(cleaned['ios_minimum']) > Version.try_parse(cleaned['ios_latest']):
            self.add_error('ios_latest', 'Последняя версия должна быть не меньше минимальной.')

        return cleaned
