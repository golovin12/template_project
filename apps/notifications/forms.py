from django import forms

from accounts.models import OrganizationUser
from .models import NotificationSettings, CityNotificationPreference


class NotificationSettingsForm(forms.ModelForm):
    """Форма всех настроек уведомлений (основные + филиалы)"""

    class Meta:
        model = NotificationSettings
        fields = ('enabled',)

    def __init__(self, *args, user: OrganizationUser, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.user:
            for city_id, city_name in self.user.allowed_city_choices:
                pref, created = CityNotificationPreference.objects.get_or_create(
                    notification_settings=self.instance,
                    city_id=city_id,
                    defaults={'enabled': True}
                )

                field_name = f'city_{city_id}'
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    initial=pref.enabled,
                    label=f'{city_name}',
                    widget=forms.CheckboxInput(attrs={
                        'class': 'city-toggle',
                        'data-city-id': city_id
                    })
                )

    def save(self, commit=True):
        """Сохранение формы и настроек филиалов"""
        instance = super().save(commit=commit)

        if commit and self.user:
            for field_name, value in self.cleaned_data.items():
                if field_name.startswith('city_'):
                    city_id = field_name.replace('city_', '')
                    CityNotificationPreference.objects.update_or_create(
                        notification_settings=instance,
                        city_id=city_id,
                        defaults={'enabled': value}
                    )
        return instance
