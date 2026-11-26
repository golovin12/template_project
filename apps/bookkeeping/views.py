from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum, Case, When, F
from django.urls import reverse
from django.views.generic import CreateView

from accounts.base import OrganizationRequest
from accounts.consts import USER_ROLES
from accounts.mixins import RoleRequiredMixin, UserCityControlMixin, ChiefRequiredMixin
from accounts.models import City
from common_tools.view import FilterSingleTableView, attachment_response, PassRequestToFormMixin
from . import excel, models, forms, filter_forms, tables


class DashboardView(ChiefRequiredMixin, FilterSingleTableView):
    """Баланс городов"""
    model = City
    table_class = tables.DashboardTable
    filter_form_class = filter_forms.DashboardFilterForm
    template_name = 'bookkeeping/dashboard.html'

    def get_queryset(self):
        return super().get_queryset().filter(id__in=self.request.user.organization_user.allowed_city_ids)


class AccountingEntryListView(UserCityControlMixin, ChiefRequiredMixin, FilterSingleTableView):
    """Записи бухгалтерии"""
    model = models.AccountingEntry
    table_class = tables.AccountingEntryTable
    filter_form_class = filter_forms.AccountingEntryFilterForm
    template_name = 'bookkeeping/entry_list.html'

    def get_queryset(self):
        return super().get_queryset().select_related('service_request', 'branch', 'city', 'created_by')

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        type_income = models.AccountingEntry.ENTRY_TYPE.INCOME
        type_expense = models.AccountingEntry.ENTRY_TYPE.EXPENSE
        aggregates = self.get_queryset().aggregate(
            total_income=Sum(Case(When(entry_type=type_income, then=F('amount')), default=Decimal(0))),
            total_expense=Sum(Case(When(entry_type=type_expense, then=F('amount')), default=Decimal(0))),
            total_expense_salary=Sum(
                Case(When(entry_type=type_expense, service_request__isnull=False, then=F('amount')),
                     default=Decimal(0)))
        )

        context['total_income'] = aggregates['total_income'] or 0
        context['total_expense'] = aggregates['total_expense'] or 0
        context['total_expense_salary'] = aggregates['total_expense_salary'] or 0
        context['balance'] = context['total_income'] - context['total_expense']
        context['city_id'] = self.request.GET.get('city', '')
        return context

    def get(self, request: OrganizationRequest, *args, **kwargs):
        if request.GET.get('to_excel'):
            qs = self.get_queryset()[:2500]
            filter_text = (self.filter_text or 'все')[:150]
            file_name = 'Бухгалтерия от {dt}, {filter_text}.xlsx'.format(
                dt=datetime.now().strftime('%d.%m.%Y %H.%M'), filter_text=filter_text)
            return attachment_response(request, excel.accounting_entry_list(qs).get_bytes_buffer(), file_name)

        return super().get(request, *args, **kwargs)


class AccountingEntryCreateView(PassRequestToFormMixin, RoleRequiredMixin, CreateView):
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)
    model = models.AccountingEntry
    form_class = forms.AccountingEntryForm
    template_name = 'bookkeeping/entry_create.html'

    def get_success_url(self):
        if self.request.user.organization_user.is_city_admin:
            return reverse('service_request:request_main')
        return reverse('bookkeeping:entry_list', query={'city': self.object.city_id})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.organization_user.is_city_admin:
            kwargs['mode'] = models.AccountingEntry.ENTRY_TYPE.EXPENSE
        else:
            kwargs['mode'] = self.request.GET.get('mode')
        return kwargs

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, 'Запись в бухгалтерию успешно добавлена!')
        return result
