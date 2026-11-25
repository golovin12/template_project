from django_select2.forms import Select2Widget, Select2MultipleWidget

from django import forms

from accounts.models import OrganizationUser
from .models import DeviceType


class CachedDeviceTypeChoiceHelper:
    def __init__(self, user: OrganizationUser | None = None, current_branch_ids: list[int] | None = None):
        self.user = user
        self.current_branch_ids = current_branch_ids

    def _get_allowed_names(self):
        if self.user is None:
            return DeviceType.get_names()

        allowed_choices = set()

        for branch_id in self.current_branch_ids or []:
            allowed_choices.update(DeviceType.get_names(branch_id))

        return allowed_choices


class CachedDeviceTypeChoiceField(CachedDeviceTypeChoiceHelper, forms.ChoiceField):
    """
    Поле выбора типа техники, которое ограничивает выбор только типами,
    доступными для филиала пользователя.
    """

    def __init__(self, *, user: OrganizationUser = None, current_branch_ids: list[int] | None = None, **kwargs):
        kwargs.setdefault('label', 'Тип техники')
        widget_attrs = kwargs.pop('widget_attrs', {})
        default_attrs = {'style': 'opacity: 0', 'data-placeholder': 'Тип техники'}
        default_attrs.update(widget_attrs)
        kwargs.setdefault('widget', Select2Widget(attrs=default_attrs))

        super().__init__(user=user, current_branch_ids=current_branch_ids)
        self._cached_choices = [(name, name) for name in sorted(self._get_allowed_names())]

        forms.ChoiceField.__init__(self, **kwargs)
        self.choices = self.get_choices

    def get_choices(self):
        yield '', ''
        yield from self._cached_choices


class CachedDeviceTypeMultipleChoiceField(CachedDeviceTypeChoiceHelper, forms.MultipleChoiceField):
    """
    Поле множественного выбора типов техники, которое ограничивает выбор
    только типами, доступными для филиала пользователя.
    """

    def __init__(self, *, user: OrganizationUser = None, current_branch_ids: list[int] | None = None, **kwargs):
        kwargs.setdefault('label', 'Тип техники')
        widget_attrs = kwargs.pop('widget_attrs', {})
        default_attrs = {'style': 'opacity: 0', 'data-placeholder': 'Тип техники'}
        default_attrs.update(widget_attrs)
        kwargs.setdefault('widget', Select2MultipleWidget(attrs=default_attrs))

        super().__init__(user=user, current_branch_ids=current_branch_ids)
        self._cached_choices = [(name, name) for name in sorted(self._get_allowed_names())]

        forms.MultipleChoiceField.__init__(self, **kwargs)
        self.choices = self.get_choices

    def get_choices(self):
        yield from self._cached_choices


class DeviceTypeControlMixin:
    def __init__(self, *args, **kwargs):
        if hasattr(self, 'request'):
            self.base_fields['device_type'] = CachedDeviceTypeChoiceField(
                user=self.request.user.organization_user,
                current_branch_ids=self.request.current_branch_ids,
                required=False,
            )
        super().__init__(*args, **kwargs)
