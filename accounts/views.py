import io
import re
from pathlib import Path

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Value, CharField
from django.db.models.functions import Concat
from django.http import Http404, FileResponse, JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, UpdateView

from identity.models import AuthUser, Organization
from common_tools.view import FilterSingleTableView
from int.db_context import DatabaseContext
from .base import OrganizationRequest
from .forms import (
    UserFilterForm, UserCreateForm, UserEditForm, BranchCreateForm, BranchUpdateForm, BranchFilterForm,
    CityUpdateForm, CityCreateForm, CityFilterForm, UserAssociateForm
)
from .mixins import ManagerRequiredMixin, RoleRequiredMixin
from .models import Branch, City, OrganizationUser
from .tables import BranchTable, CityTable, UserTable


class HomePageView(RoleRequiredMixin, View):
    """Домашняя страница, куда попадает пользователь после авторизации"""

    def get(self, request: OrganizationRequest, *args, **kwargs):
        organization_user: OrganizationUser = request.user.organization_user
        if organization_user.is_manager or organization_user.is_city_admin or organization_user.is_chief:
            return redirect('service_request:request_main')
        return redirect('identity:login')


class UserListView(ManagerRequiredMixin, FilterSingleTableView):
    """Список пользователей"""
    queryset = OrganizationUser.objects.annotate(
        search_full_name=Concat('last_name', Value(' '), 'first_name', Value(' '), 'second_name',
                                output_field=CharField())
    ).prefetch_related('cities')
    table_class = UserTable
    filter_form_class = UserFilterForm
    template_name = 'accounts/list.html'


class UserCreateView(ManagerRequiredMixin, CreateView):
    """Создание пользователя"""
    model = OrganizationUser
    form_class = UserCreateForm
    template_name = 'accounts/create.html'
    success_url = reverse_lazy('accounts:list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, 'Пользователь успешно создан')
        return result


class UserDeleteView(ManagerRequiredMixin, View):
    """Удаление пользователя"""

    def get(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        qs = OrganizationUser.objects.all()
        if not self.request.user.is_superuser:
            qs = qs.filter(is_global_superuser=False)
        user = get_object_or_404(qs, pk=pk)
        if organization := Organization.objects.filter(database_alias=DatabaseContext.get()).first():
            organization.users.filter(id=user.user_id).delete()
        user.delete()
        messages.success(request, f'Пользователь {user.username} успешно удален!')
        return redirect('accounts:list')


class UserAssociateView(ManagerRequiredMixin, CreateView):
    """Создание пользователя для существующего акка"""
    model = OrganizationUser
    form_class = UserAssociateForm
    template_name = 'accounts/associate.html'
    success_url = reverse_lazy('accounts:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = get_object_or_404(AuthUser, id=self.request.GET.get('user_id'))
        return kwargs

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, 'Пользователь успешно привязан')
        return result


class UserUpdateView(ManagerRequiredMixin, UpdateView):
    """Обновление информации о пользователе"""
    queryset = OrganizationUser.objects
    form_class = UserEditForm
    template_name = 'accounts/edit.html'
    success_url = reverse_lazy('accounts:list')

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            return qs.filter(is_global_superuser=False)
        return qs

    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.object.auth_user
        return kwargs

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Пользователь {form.instance.username} успешно обновлен')
        return result


class ChangePasswordView(ManagerRequiredMixin, UpdateView):
    """Изменение пароля пользователя (manager может менять пароль любого пользователя)"""
    queryset = OrganizationUser.objects
    form_class = SetPasswordForm
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('accounts:list')

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            return qs.filter(is_global_superuser=False)
        return qs

    def get_form_kwargs(self) -> dict:
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.object.auth_user
        kwargs.pop('instance')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f'Пароль для {form.user.username} успешно изменен')
        return super().form_valid(form)


@login_required
def media_file(request: OrganizationRequest, file_path: str, app_name: str, model_name: str, field_name: str):
    """
    Обработчик получения файла из папки media, на основе разрешений пользователя
    :param request: объект запроса django
    :param file_path: полный путь к файлу
    :param app_name: приложение которому принадлежит файл
    :param model_name: имя модели
    :param field_name: имя поля модели
    """
    app_name, model_name, field_name = tuple(re.sub(r'[^\w\d_]', '', i) for i in [app_name, model_name, field_name])
    file_path = str(file_path)

    try:
        model = apps.get_model(app_name, model_name)
    except LookupError:
        raise Http404

    obj = model.objects.filter(**{field_name: file_path}).first()
    if not obj:
        raise Http404

    # *для proxy моделей нужно добавлять в права настоящие модели
    perm = '{app}.view_{model}'.format(app=app_name, model=model_name.lower())
    if not request.user.has_perm(perm) and not request.user.organization_user.has_perm(perm):
        raise PermissionDenied

    try:
        return FileResponse(io.BytesIO(getattr(obj, field_name).read()), filename=Path(file_path).name)
    except FileNotFoundError:
        raise Http404


class SelectCityView(LoginRequiredMixin, View):
    SESSION_KEY = 'current_city_id'

    def post(self, request: OrganizationRequest, *args, **kwargs):
        city_id = request.POST.get('city_id')
        organization_user = request.user.organization_user
        session_key = f'{self.SESSION_KEY}:{DatabaseContext.get()}'

        if city_id == 'all':
            request.session.pop(session_key, None)
            city_name = 'Все доступные'
        else:
            city = City.active_objects.filter(
                id=city_id,
                id__in=organization_user.allowed_city_ids,
            ).first()

            if city is None:
                messages.error(request, 'Недопустимый город')
                return JsonResponse({'ok': False})

            request.session[session_key] = city.id
            city_name = city.name

        messages.success(request, f'Теперь вы работаете с городом: {city_name}')
        return JsonResponse({'ok': True})


class BranchListView(ManagerRequiredMixin, FilterSingleTableView):
    """Список филиалов"""
    model = Branch
    table_class = BranchTable
    filter_form_class = BranchFilterForm
    template_name = 'accounts/branch_list.html'


class BranchCreateView(ManagerRequiredMixin, CreateView):
    """Добавление филиала"""
    model = Branch
    form_class = BranchCreateForm
    template_name = 'accounts/branch_create.html'
    success_url = reverse_lazy('accounts:branch_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Филиал {form.instance} успешно добавлен!')
        return result


class BranchUpdateView(ManagerRequiredMixin, UpdateView):
    """Изменение филиала"""
    model = Branch
    form_class = BranchUpdateForm
    template_name = 'accounts/branch_update.html'
    success_url = reverse_lazy('accounts:branch_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Данные филиала {form.instance} успешно обновлены!')
        return result


class CityListView(ManagerRequiredMixin, FilterSingleTableView):
    """Список филиалов"""
    model = City
    table_class = CityTable
    filter_form_class = CityFilterForm
    template_name = 'accounts/city_list.html'


class CityCreateView(ManagerRequiredMixin, CreateView):
    """Добавление города"""
    model = City
    form_class = CityCreateForm
    template_name = 'accounts/block/city_create_form.html'

    def form_valid(self, form):
        city = form.save()
        messages.success(self.request, f'Город {city} успешно добавлен!')
        return HttpResponse(status=204)


class CityUpdateView(ManagerRequiredMixin, UpdateView):
    """Изменение города"""
    model = City
    form_class = CityUpdateForm
    template_name = 'accounts/city_update.html'
    success_url = reverse_lazy('accounts:city_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Данные города {form.instance} успешно обновлены!')
        return result
