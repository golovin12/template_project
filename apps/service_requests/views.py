from django_tables2 import SingleTableView

from django.contrib import messages
from django.db.models import Count, Q, Value, CharField
from django.db.models.functions import Concat
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView, TemplateView
from django.views.generic.detail import SingleObjectMixin

from accounts.base import OrganizationRequest
from accounts.consts import USER_ROLES
from accounts.mixins import (
    ChiefRequiredMixin, ManagerRequiredMixin, RoleRequiredMixin, CityAdminRequiredMixin, UserCityControlMixin,
    BranchControlHelperMixin
)
from accounts.models import OrganizationUser
from common_tools.view import FilterSingleTableView, PassRequestToFormMixin, QuerySetMixin
from . import models, forms, filter_forms, tables


class CreatedServiceRequestsView(ChiefRequiredMixin, FilterSingleTableView):
    queryset = OrganizationUser.objects.annotate(
        search_full_name=Concat('last_name', Value(' '), 'first_name', Value(' '), 'second_name',
                                output_field=CharField())
    )
    table_class = tables.CreatedServiceRequestsTable
    filter_form_class = filter_forms.CreatedServiceRequestsFilterForm
    template_name = 'service_request/created_service_requests_list.html'


class ServiceRequestMainView(UserCityControlMixin, BranchControlHelperMixin, RoleRequiredMixin, QuerySetMixin,
                             TemplateView):
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest
    template_name = 'service_request/request_main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = filter_forms.ServiceRequestFilterPhoneForm()
        req_statuses = models.ServiceRequest.STATUS
        service_request_counts = self.get_queryset().aggregate(
            in_progress_count=Count('id', filter=Q(status__in=(
                req_statuses.NEW, req_statuses.ASSIGNED, req_statuses.ON_WAY, req_statuses.IN_PROGRESS))),
            diagnostic_count=Count('id', filter=Q(status=req_statuses.SERVICE_DIAGNOSTICS)),
            diagnostic_today_count=Count('id', filter=Q(status=req_statuses.SERVICE_DIAGNOSTICS,
                                                        sd_closing_date=timezone.now().date())),
        )
        context['request_stat'] = service_request_counts
        return context


class ServiceRequestListView(UserCityControlMixin, RoleRequiredMixin, FilterSingleTableView):
    """Список созданных заявок"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    queryset = models.ServiceRequest.objects.select_related('branch', 'assigned_master')
    table_class = tables.ServiceRequestTable
    filter_form_class = filter_forms.ServiceRequestFilterForm
    template_name = 'service_request/request_list.html'


class ServiceRequestCreateView(PassRequestToFormMixin, RoleRequiredMixin, CreateView):
    """Создание заявки"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest
    form_class = forms.ServiceRequestCreateForm
    template_name = 'service_request/request_create.html'
    success_url = reverse_lazy('service_request:request_list')

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context['device_type_branches'] = models.DeviceType.get_branch_by_name()
        return context

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Заявка #{self.object.request_number} успешно добавлена!')
        return result


class ServiceRequestCopyView(UserCityControlMixin, ServiceRequestCreateView):
    """Создание копии заявки (для гарантии и повтора)"""

    def get_initial(self) -> dict:
        self.original = self.get_object()
        initial = super().get_initial()
        initial['branch'] = self.original.branch.pk
        initial['client_name'] = self.original.client_name
        initial['client_phone'] = self.original.client_phone
        initial['client_address'] = self.original.client_address
        initial['device_type'] = self.original.device_type
        return initial

    def form_valid(self, form):
        form.instance.parent = self.original
        result = super().form_valid(form)
        return result


class ServiceRequestUpdateView(UserCityControlMixin, PassRequestToFormMixin, ChiefRequiredMixin, UpdateView):
    """Изменение данных заявки"""
    model = models.ServiceRequest
    form_class = forms.ServiceRequestUpdateForm
    template_name = 'service_request/request_update.html'
    context_object_name = 'svc_request'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['device_type_branches'] = models.DeviceType.get_branch_by_name()
        return context

    def get_success_url(self):
        return reverse('service_request:request_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Заявка #{form.instance.request_number} успешно изменена!')
        return result


class ServiceRequestCityAdminUpdateView(UserCityControlMixin, CityAdminRequiredMixin, UpdateView):
    """Изменение данных заявки"""
    model = models.ServiceRequest
    form_class = forms.ServiceRequestCityAdminUpdateForm
    template_name = 'service_request/block/city_admin_update_request_body.html'
    context_object_name = 'svc_request'

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f'Заявка #{form.instance.request_number} успешно изменена!')
        return HttpResponse(status=204)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['prefix'] = 'city_admin_form'
        return kwargs


class ServiceRequestDetailView(UserCityControlMixin, RoleRequiredMixin, DetailView):
    """Просмотр информации о заявке"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    queryset = models.ServiceRequest.objects.select_related('branch', 'created_by', 'parent')
    template_name = 'service_request/request_detail.html'
    context_object_name = 'svc_request'

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        if self.object.assigned_master and not self.object.is_status_end:
            context['closing_form'] = forms.ServiceRequestCompleteForm(instance=self.object)
            if self.object.is_status_progress:
                context['diagnostic_form'] = forms.ServiceRequestDiagnosticForm(instance=self.object)
        if self.request.user.organization_user.is_city_admin and not self.object.is_status_end:
            context['city_admin_form'] = forms.ServiceRequestCityAdminUpdateForm(instance=self.object,
                                                                                 prefix='city_admin_form')
        return context


class ServiceRequestUpdateMasterStatusView(UserCityControlMixin, RoleRequiredMixin, SingleObjectMixin, View):
    """Обновление статусов заявки (только статусы мастера)"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest

    def post(self, request: OrganizationRequest, **kwargs):
        self.request = request
        self.kwargs = kwargs
        service_request = self.get_object()
        statuses = models.ServiceRequest.STATUS
        new_status = request.POST.get('new_status')
        if (new_status in (statuses.ON_WAY, statuses.IN_PROGRESS)
                and service_request.status in (statuses.ASSIGNED, statuses.ON_WAY)):
            service_request.status = new_status
            service_request.save(update_fields=['status'])
        return redirect('service_request:request_detail', **kwargs)


class ServiceRequestCompleteView(UserCityControlMixin, RoleRequiredMixin, SingleObjectMixin, View):
    """Завершение заявки"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest

    def post(self, request: OrganizationRequest, **kwargs):
        self.request = request
        self.kwargs = kwargs
        service_request = self.get_object()
        form = forms.ServiceRequestCompleteForm(request.POST, instance=service_request, files=request.FILES)
        if not service_request.is_status_end and service_request.assigned_master and form.is_valid():
            form.save()
            messages.success(request, 'Заявка завершена')
            return HttpResponse(status=204)
        return render(request, 'service_request/block/complete_request_body.html', {'closing_form': form})


class ServiceRequestDiagnosticView(UserCityControlMixin, RoleRequiredMixin, SingleObjectMixin, View):
    """Перевод в диагностику"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest

    def post(self, request: OrganizationRequest, **kwargs):
        self.request = request
        self.kwargs = kwargs
        service_request = self.get_object()
        form = forms.ServiceRequestDiagnosticForm(request.POST, instance=service_request, files=request.FILES)
        if not service_request.is_status_end and service_request.assigned_master and form.is_valid():
            form.save()
            messages.success(request, 'Заявка переведена в статус диагностики!')
            return HttpResponse(status=204)
        return render(request, 'service_request/block/diagnostic_request_body.html', {'diagnostic_form': form})


class ServiceRequestCancelView(UserCityControlMixin, RoleRequiredMixin, SingleObjectMixin, View):
    """Отмена заявки"""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.ServiceRequest

    def post(self, request: OrganizationRequest, **kwargs):
        self.request = request
        self.kwargs = kwargs
        service_request = self.get_object()
        if not service_request.is_status_end:
            service_request.status = models.ServiceRequest.STATUS.CANCELED
            service_request.save(update_fields=['status'])
            messages.success(request, 'Заявка отменена')
        return redirect('service_request:request_detail', **kwargs)


class DeviceTypeListView(ManagerRequiredMixin, SingleTableView):
    """Список типов техники"""
    model = models.DeviceType
    table_class = tables.DeviceTypeTable
    template_name = 'service_request/device_type_list.html'


class DeviceTypeCreateView(ManagerRequiredMixin, CreateView):
    """Добавление типов техники"""
    model = models.DeviceType
    form_class = forms.DeviceTypeCreateForm
    template_name = 'service_request/device_type_create.html'
    success_url = reverse_lazy('service_request:device_type_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, f'Тип "{form.instance}" успешно добавлен!')
        return result


class DeviceTypeUpdateView(ManagerRequiredMixin, UpdateView):
    """Редактирование типа техники"""
    model = models.DeviceType
    form_class = forms.DeviceTypeUpdateForm
    template_name = 'service_request/block/device_type_update_body.html'

    def form_valid(self, form):
        device_type = form.save()
        messages.success(self.request, f'Тип техники {device_type.name} обновлён!')
        return HttpResponse(status=204)


class DeviceTypeDeleteView(ManagerRequiredMixin, View):
    """Удаление типа техники"""

    def get(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        if 'delete' in request.GET:
            device_type = get_object_or_404(models.DeviceType, pk=pk)
            device_type.delete()
            messages.success(request, 'Тип техники успешно удален!')
        return redirect('service_request:device_type_list')
