import json

from django.contrib import messages
from django.http import HttpResponse
from django.views import View
from django.views.generic import DetailView

from accounts.base import OrganizationRequest
from accounts.mixins import ChiefRequiredMixin, RoleRequiredMixin
from accounts.models import City
from .services import CityStatisticsCacheService


class CityStatisticsView(ChiefRequiredMixin, DetailView):
    model = City
    template_name = 'statistics/city_statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statistics'] = json.loads(CityStatisticsCacheService.get(self.object.pk))
        return context

    def get_queryset(self):
        allowed_city_ids = self.request.user.organization_user.allowed_city_ids
        return super().get_queryset().filter(id__in=allowed_city_ids).prefetch_related('branches')


class ClearStaticCacheView(RoleRequiredMixin, View):

    def get(self, request: OrganizationRequest, *args, **kwargs):
        if request.user.is_superuser:
            for city in City.objects.values_list('id', flat=True):
                CityStatisticsCacheService.rebuild(city)
            messages.success(request, 'Кэш статистики успешно обновлён')
        return HttpResponse(status=204)
