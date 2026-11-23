from django_select2.forms import Select2Widget

from django.core.exceptions import ValidationError

from common_tools.form import CustomModelChoiceFieldInterface
from .base import OrganizationRequest
from .models import Branch, City


class BranchControlMixinBase:
    """Общий код для Выбора текущего филиала."""
    request: OrganizationRequest
    branch_field = 'branch'

    def _set_branch_field(self):
        self.fields[self.branch_field] = CachedBranchChoiceField(request=self.request)


class BranchControlMixin(BranchControlMixinBase):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self._set_branch_field()


class BranchControlFilterMixin(BranchControlMixinBase):
    def __init__(self, request: OrganizationRequest, *args, **kwargs):
        self.request = request
        super().__init__(request, *args, **kwargs)
        self._set_branch_field()


class CachedBranchChoiceField(CustomModelChoiceFieldInterface):
    """Поле выбора филиала, из доступных пользователю."""

    def __init__(self, *args, request: OrganizationRequest | None = None, **kwargs):
        self.user = request.user.organization_user if request else None
        self.current_branch_ids = request.current_branch_ids if request else None
        kwargs.setdefault('label', 'Филиал')
        widget_attrs = kwargs.pop('widget_attrs', {})
        default_attrs = {'style': 'opacity: 0', 'data-placeholder': 'Филиал'}
        default_attrs.update(widget_attrs)

        kwargs.setdefault('widget', Select2Widget(attrs=default_attrs))
        super().__init__(*args, queryset=Branch.active_objects, **kwargs)

    def get_choices(self):
        yield '', ''
        user = self.user
        if user:
            yield from ((branch_id, label) for branch_id, label in user.allowed_branch_choices
                        if branch_id in self.current_branch_ids)
        else:
            yield from Branch.get_active_choices()

    def to_python(self, value):
        """Проверяем, что выбранный филиал действительно доступен пользователю."""
        branch = super().to_python(value)
        if self.user and branch and branch.id not in self.user.allowed_branch_ids:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice', params={'value': value})
        return branch


class CachedCityChoiceField(CustomModelChoiceFieldInterface):
    """Поле выбора города, из доступных пользователю."""

    def __init__(self, *args, request: OrganizationRequest | None = None, **kwargs):
        self.user = request.user.organization_user if request else None
        label = kwargs.get('label', 'Город')
        kwargs.setdefault('label', label)
        widget_attrs = kwargs.pop('widget_attrs', {})
        default_attrs = {'style': 'opacity: 0', 'data-placeholder': label}
        default_attrs.update(widget_attrs)

        kwargs.setdefault('widget', Select2Widget(attrs=default_attrs))
        super().__init__(*args, queryset=City.active_objects, **kwargs)

        if self.user and request.current_city_id:
            self.initial = request.current_city_id
            self.disabled = True

    def get_choices(self):
        yield '', ''
        if self.user:
            yield from self.user.allowed_city_choices
        else:
            yield from City.get_active_choices()

    def to_python(self, value):
        """Проверяем, что выбранный город действительно доступен пользователю."""
        city = super().to_python(value)
        if self.user and city and city.id not in self.user.allowed_city_ids:
            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice', params={'value': value})
        return city
