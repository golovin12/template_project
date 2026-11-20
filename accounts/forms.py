from django_select2.forms import Select2Widget, Select2MultipleWidget

from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.forms import UserCreationForm
from django.db.models import QuerySet

from identity.models import AuthUser, Organization
from common_tools.form import BaseFilterForm, WithoutPlaceholderMixin
from int.db_context import DatabaseContext
from .consts import USER_ROLES
from .form import CachedCityChoiceField
from .models import OrganizationUser, Branch, City


class OrganizationUserFieldsMixin(forms.Form):
    cities = forms.ModelMultipleChoiceField(City.active_objects, label='Города', required=False,
                                            widget=Select2MultipleWidget(attrs={'style': 'opacity: 0'}))
    all_cities_access = forms.BooleanField(
        label='Доступ ко всем городам', required=False,
        help_text='Поставьте галочку, если пользователь должен иметь доступ ко всем городам.')
    is_act_creation_access = forms.BooleanField(
        label='Доступ к созданию актов', required=False,
        help_text='Поставьте галочку, если пользователь должен иметь доступ к созданию актов.')
    role = forms.ChoiceField(choices=USER_ROLES.choices, label='Роль', required=False,
                             widget=Select2Widget(attrs={'style': 'opacity: 0'}))

    @staticmethod
    def save_organization_user(user: OrganizationUser, cleaned_data: dict):
        user.all_cities_access = cleaned_data.get('all_cities_access', False)
        user.is_act_creation_access = cleaned_data.get('is_act_creation_access', False)
        user.role = cleaned_data.get('role', '')
        user.sync_and_save()

        cities = cleaned_data.get('cities', [])
        user.cities.set(cities)

    def init_organization_user(self, user: OrganizationUser):
        self.initial.update({
            'all_cities_access': user.all_cities_access,
            'role': user.role,
            'cities': user.cities.all(),
        })


class UserEditForm(OrganizationUserFieldsMixin, WithoutPlaceholderMixin, UserChangeForm):
    password = None

    class Meta:
        model = AuthUser
        fields = ('username', 'last_name', 'first_name', 'second_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_organization_user(self.instance.organization_user)

    def save(self, commit=True):
        instance: AuthUser = super().save(commit)

        if commit:
            organization_user = instance.organization_user
            self.save_organization_user(organization_user, self.cleaned_data)
            organization_user.clear_cache()
        return instance


class UserAssociateForm(OrganizationUserFieldsMixin, WithoutPlaceholderMixin, UserChangeForm):
    password = None

    class Meta:
        model = AuthUser
        fields = tuple()

    def save(self, commit=True):
        if commit:
            if organization := Organization.objects.filter(database_alias=DatabaseContext.get()).first():
                organization.users.add(self.instance)

            organization_user = self.instance.organization_user
            self.save_organization_user(organization_user, self.cleaned_data)
        return self.instance


class UserCreateForm(OrganizationUserFieldsMixin, WithoutPlaceholderMixin, UserCreationForm):
    class Meta:
        model = AuthUser
        fields = ('username', 'last_name', 'first_name', 'second_name')

    def save(self, commit=True):
        instance: AuthUser = super().save(commit)
        if commit:
            if organization := Organization.objects.filter(database_alias=DatabaseContext.get()).first():
                organization.users.add(instance)

            organization_user = instance.organization_user
            self.save_organization_user(organization_user, self.cleaned_data)
        return instance


class UserFilterForm(BaseFilterForm, forms.ModelForm):
    """Форма фильтрации пользователей"""
    city = CachedCityChoiceField()
    full_name = forms.CharField(label='ФИО')
    user_name = forms.CharField(label='Логин')

    class Meta:
        model = OrganizationUser
        fields = ('full_name', 'user_name', 'role', 'city')
        widgets = {
            'role': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Роль'}),
        }

    def _filtration(self, qs: QuerySet[OrganizationUser]):
        cd = self.cleaned_data

        if full_name := cd.get('full_name'):
            qs = qs.filter(search_full_name__icontains=full_name.strip())
        if username := cd.get('user_name'):
            qs = qs.filter(username__iexact=username.strip())
        if role := cd.get('role'):
            qs = qs.filter(role=role)
        if city := cd.get('city'):
            qs = qs.filter(cities=city)
        return qs


class BranchCreateForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = Branch
        fields = ('name', 'city')
        widgets = {
            'city': Select2Widget(attrs={'style': 'opacity: 0'}),
        }

    def clean_city(self):
        city = self.cleaned_data.get('city')
        if city and not city.is_active:
            raise forms.ValidationError('Выбранный город не активен.')
        return city


class BranchUpdateForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = Branch
        fields = ('name', 'city', 'is_active')
        widgets = {
            'city': Select2Widget(attrs={'style': 'opacity: 0'}),
        }

    def clean_city(self):
        city = self.cleaned_data.get('city')
        if city and not city.is_active:
            raise forms.ValidationError('Выбранный город не активен.')
        return city


class BranchFilterForm(BaseFilterForm, forms.ModelForm):
    """Форма фильтрации филиалов"""

    class Meta:
        model = Branch
        fields = ('city', 'name')
        widgets = {
            'city': Select2Widget(attrs={'style': 'opacity: 0', 'data-placeholder': 'Город'}),
        }

    def _filtration(self, qs: QuerySet[Branch]):
        cd = self.cleaned_data

        if name := cd.get('name'):
            qs = qs.filter(name__icontains=name)
        if city := cd.get('city'):
            qs = qs.filter(city=city)
        return qs


class CityCreateForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = City
        fields = ('name',)


class CityUpdateForm(WithoutPlaceholderMixin, forms.ModelForm):
    class Meta:
        model = City
        fields = ('name', 'is_active')


class CityFilterForm(BaseFilterForm, forms.ModelForm):
    """Форма фильтрации городов"""

    class Meta:
        model = City
        fields = ('name',)

    def _filtration(self, qs: QuerySet[City]):
        cd = self.cleaned_data

        if name := cd.get('name'):
            qs = qs.filter(name__icontains=name)
        return qs
