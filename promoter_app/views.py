import json

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Count, Q, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, DetailView, FormView

from accounts.base import OrganizationRequest
from accounts.mixins import ForSuperUserMixin
from apps.bookkeeping.models import AccountingEntry
from common_tools.markdown import load_and_render_md
from common_tools.view import FilterSingleTableView
from . import models, forms, tables, auth
from .consts import DEFAULT_APP_VERSIONS, APP_VERSIONS_CACHE_KEY
from .forms import AppVersionsForm


class APP_URLS:
    """Актуальные ссылки на приложение"""
    APK_URL = 'https://int.atlantservice.space/promoter_app/download/apk'
    GOOGLE_PLAY_URL = ''
    APP_STORE_URL = 'https://apps.apple.com/ru/app/id6789844063'


class MainPageView(TemplateView):
    """Главная страница приложения ПромоТрек"""
    template_name = 'promoter_app/main_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'apk_url': APP_URLS.APK_URL,
            'google_play_url': APP_URLS.GOOGLE_PLAY_URL,
            'ios_url': APP_URLS.APP_STORE_URL,
        })

        return context


class PrivacyPolicyView(TemplateView):
    """Страница политики конфиденциальности"""
    template_name = 'promoter_app/privacy_policy.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['policy_content'] = load_and_render_md('promoter_app/docs/privacy_policy.md')
        return context


class TermsOfServiceView(TemplateView):
    """Страница пользовательского соглашения"""
    template_name = 'promoter_app/terms_of_service.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['terms_content'] = load_and_render_md('promoter_app/docs/terms_of_service.md')
        return context


class AppVersionsSettingsView(ForSuperUserMixin, FormView):
    template_name = 'promoter_app/app_versions.html'
    form_class = AppVersionsForm
    success_url = reverse_lazy('promoter_app:app_versions')

    def get_versions(self):
        return cache.get(APP_VERSIONS_CACHE_KEY, DEFAULT_APP_VERSIONS)

    def get_initial(self):
        initial = super().get_initial()

        value = self.get_versions()

        initial.update({
            'android_minimum': value['android']['minimum'],
            'android_latest': value['android']['latest'],
            'ios_minimum': value['ios']['minimum'],
            'ios_latest': value['ios']['latest'],
        })

        return initial

    def form_valid(self, form):
        cache.set(
            APP_VERSIONS_CACHE_KEY,
            {
                'android': {
                    'minimum': form.cleaned_data['android_minimum'],
                    'latest': form.cleaned_data['android_latest'],
                },
                'ios': {
                    'minimum': form.cleaned_data['ios_minimum'],
                    'latest': form.cleaned_data['ios_latest'],
                },
            },
            timeout=None,
        )

        messages.success(self.request, 'Версии приложений успешно обновлены!', )
        return super().form_valid(form)


class AppDashboardView(auth.PromoTreckRequiredMixin, TemplateView):
    """Главная страница"""
    template_name = 'promoter_app/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['city'] = self.city
        context.update({
            'apk_url': APP_URLS.APK_URL,
            'google_play_url': APP_URLS.GOOGLE_PLAY_URL,
            'ios_url': APP_URLS.APP_STORE_URL,
        })
        return context


class RoutesEditorView(auth.PromoTreckRequiredMixin, TemplateView):
    """Страница редактирования маршрутов"""
    template_name = 'promoter_app/routes_editor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        routes_qs = models.RouteZone.objects.filter(city=self.city).only('id', 'name', 'polygon')

        routes_list = [{'id': r.id, 'name': r.name, 'polygon': r.get_polygon()} for r in routes_qs]

        context.update({'city': self.city, 'routes': routes_list})
        context['map_key'] = settings.YANDEX_TILES['EDITOR_KEY']
        return context


class RoutesAssignView(auth.PromoTreckRequiredMixin, TemplateView):
    """Страница назначения промоутеров на маршрут"""
    template_name = 'promoter_app/routes_assign.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        promoters = models.PromoterProfile.objects.filter(city=self.city).select_related('city')

        routes_qs = models.RouteZone.objects.filter(city=self.city)

        routes_list = []
        for route in routes_qs:
            routes_list.append({
                'id': route.id,
                'name': route.name,
                'polygon': route.get_polygon(),
                'color': route.get_color_by_last_assigned(),
                'last_assigned_date': route.last_assigned_date.strftime(
                    '%d.%m.%Y %H:%M') if route.last_assigned_date else None,
            })

        context.update({
            'city': self.city,
            'routes': json.dumps(routes_list),
            'promoters': promoters,
        })

        context['map_key'] = settings.YANDEX_TILES['ASSIGN_KEY']
        return context


class AssignmentsListView(auth.PromoTreckRequiredMixin, FilterSingleTableView):
    """Страница с информацией о прогрессе промоутеров на маршрутах"""
    model = models.PromoterAssignment
    table_class = tables.PromoterAssignmentTable
    template_name = 'promoter_app/assignments.html'
    filter_form_class = forms.PromoterAssignmentFilterForm

    def get_queryset(self, **kwargs):
        return super().get_queryset(**kwargs).filter(route_zone__city=self.city).select_related(
            'promoter', 'route_zone', 'route_zone__city', 'assigned_by'
        ).order_by('is_confirmed', '-assigned_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['city'] = self.city
        return context


class AssignmentDetailView(auth.PromoTreckRequiredMixin, DetailView):
    """Страница для просмотра данных с маршрута"""
    queryset = models.PromoterAssignment.objects.select_related('route_zone')
    template_name = 'promoter_app/assignment_detail.html'
    context_object_name = 'assignment'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment = self.get_object()
        auth.PromoAccessChecker.check_assignment_or_404(assignment, self.city)

        photos = list(assignment.photos.all().order_by('created_at'))

        photos_by_location = {}
        photos_without_location = []

        for photo in photos:
            if photo.has_location and photo.lat and photo.lng:
                lat_rounded = round(photo.lat, 6)
                lng_rounded = round(photo.lng, 6)
                key = f'{lat_rounded},{lng_rounded}'

                if key not in photos_by_location:
                    photos_by_location[key] = {
                        'lat': lat_rounded,
                        'lng': lng_rounded,
                        'photos': []
                    }
                photos_by_location[key]['photos'].append({
                    'id': photo.id,
                    'url': photo.s3_url,
                    'created_at': photo.created_at.strftime('%d.%m.%Y %H:%M:%S'),
                    'has_location': photo.has_location
                })
            else:
                photos_without_location.append({
                    'id': photo.id,
                    'url': photo.s3_url,
                    'created_at': photo.created_at.strftime('%d.%m.%Y %H:%M:%S'),
                    'has_location': False
                })

        route_zone = assignment.route_zone
        polygon_geojson = route_zone.get_polygon()

        photos_by_location_list = list(photos_by_location.values())

        context['photos_by_location'] = json.dumps(photos_by_location_list)
        context['photos_by_location_count'] = len(photos_by_location_list)
        context['photos_without_location'] = json.dumps(photos_without_location)
        context['photos_without_location_count'] = len(photos_without_location)
        context['photos_with_gps'] = assignment.total_photos - assignment.photos_no_gps
        context['polygon_geojson'] = json.dumps(polygon_geojson)
        context['all_photos'] = json.dumps([
            {
                'id': p.id,
                'url': p.s3_url,
                'lat': p.lat,
                'lng': p.lng,
                'created_at': p.created_at.strftime('%d.%m.%Y %H:%M:%S'),
                'has_location': p.has_location
            }
            for p in photos
        ])

        context['map_key'] = settings.YANDEX_TILES['DETAIL_KEY']
        return context


class SaveRoutesApiView(auth.PromoTreckRequiredMixin, View):
    """Api для изменения маршрутов"""

    def post(self, request: OrganizationRequest, *args, **kwargs):
        data = json.loads(request.body)

        routes = data.get('routes', [])

        existing_ids = []

        for item in routes:
            route_id = item.get('id')

            if route_id:
                route, _ = models.RouteZone.objects.update_or_create(
                    id=route_id,
                    defaults={
                        'city': self.city,
                        'name': item['name'],
                        'polygon': item['polygon'],
                    }
                )
            else:
                route = models.RouteZone.objects.create(
                    city=self.city,
                    name=item['name'],
                    polygon=item['polygon'],
                )

            existing_ids.append(route.id)

        models.RouteZone.objects.filter(city=self.city).exclude(id__in=existing_ids).delete()

        messages.success(request, 'Маршруты успешно обновлены!')
        return JsonResponse({'success': True})


class AssignPromoRouteApiView(auth.PromoTreckRequiredMixin, View):
    """Api для назначения промоутеров на маршрут"""

    def post(self, request: OrganizationRequest, *args, **kwargs):
        data = json.loads(request.body)
        route_ids = data.get('route_ids', [])
        promoter_id = data.get('promoter_id')

        if not route_ids or not promoter_id:
            return JsonResponse({'error': 'Не указаны маршруты или промоутер'}, status=400)

        promoter = get_object_or_404(models.PromoterProfile, id=promoter_id)
        auth.PromoAccessChecker.check_promoter_or_404(promoter, self.city)

        assignments_count = 0
        for route_id in route_ids:
            route = get_object_or_404(models.RouteZone, id=route_id)
            if route.city_id != promoter.city_id:
                continue

            models.PromoterAssignment.objects.create(promoter=promoter, route_zone=route,
                                                     assigned_by=request.user.zone_profile)
            assignments_count += 1

            route.last_assigned_date = timezone.now()
            route.is_active = True
            route.save()

        messages.success(request, f'Промоутер {promoter.nickname} назначен на {assignments_count} маршрут(ов)')
        return JsonResponse({'success': True})


class AssignmentConfirmView(auth.PromoTreckRequiredMixin, View):
    """Подтверждение окончания маршрута"""

    def post(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        assignment = get_object_or_404(models.PromoterAssignment.objects.select_related('route_zone'), pk=pk)
        auth.PromoAccessChecker.check_assignment_or_404(assignment, self.city)

        try:
            payment_amount = float(request.POST.get('payment_amount'))
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Укажите корректную сумму выплаты'}, status=400)

        assignment.confirm()
        AccountingEntry.objects.create(
            entry_type=AccountingEntry.ENTRY_TYPE.EXPENSE,
            amount=payment_amount,
            description=f'Выплата по маршруту промоутеру: {assignment.promoter.nickname}. '
                        f'Фото: {assignment.total_photos}',
            city_id=assignment.route_zone.city_id,
            expense_subtype=AccountingEntry.EXPENSE_SUBTYPE.PROMO,
            created_by=self.request.user.organization_user
        )
        messages.success(request, 'Маршрут успешно подтверждён, запись в бухгалтерию добавлена.')
        return JsonResponse({'status': 'success'})


class AssignmentCancelView(auth.PromoTreckRequiredMixin, View):
    """Отмена назначения промоутера"""

    def post(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        assignment = get_object_or_404(models.PromoterAssignment.objects.select_related('route_zone'), pk=pk)
        auth.PromoAccessChecker.check_assignment_or_404(assignment, self.city)

        if assignment.is_ended:
            messages.error(request, 'Завершённое назначение нельзя отменить!')
            return JsonResponse({'status': 'success'})

        assignment.cancel()

        messages.success(request, 'Назначение успешно отменено.')
        return JsonResponse({'status': 'success'})


class PromotersListView(auth.PromoTreckRequiredMixin, FilterSingleTableView):
    """Список промоутеров"""
    template_name = 'promoter_app/promoters_list.html'
    model = models.PromoterProfile
    table_class = tables.PromotersTable
    filter_form_class = forms.PromotersFilterForm

    def get_queryset(self, **kwargs):
        return super().get_queryset(**kwargs).filter(city=self.city).annotate(
            total_assignments=Count('assignments'),
            completed_assignments=Count('assignments', filter=Q(assignments__status='ended')),
            last_assignment_date=Max('assignments__assigned_date')
        ).order_by('nickname')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['city'] = self.city
        context['open_qr_id'] = self.request.GET.get('show_qr')
        return context


class PromoterCreateView(auth.PromoTreckRequiredMixin, View):
    """Создание промоутера"""

    def post(self, request: OrganizationRequest, *args, **kwargs):
        nickname = request.POST.get('nickname', '').strip()

        if not nickname:
            return JsonResponse({'success': False, 'error': 'Введите ник'}, status=400)

        promoter = models.PromoterProfile.objects.create(city=self.city, nickname=nickname[:100])

        messages.success(request, f'Промоутер {promoter.nickname} успешно создан!')
        return JsonResponse({
            'success': True,
            'reload_url': f'{reverse("promoter_app:promoters_list")}?show_qr={promoter.id}'
        })


class PromoterUpdateView(auth.PromoTreckRequiredMixin, View):
    """Обновление данных промоутера"""

    def post(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        promoter = get_object_or_404(models.PromoterProfile, pk=pk)
        auth.PromoAccessChecker.check_promoter_or_404(promoter, self.city)

        nickname = request.POST.get('nickname', '').strip()

        if not nickname:
            return JsonResponse({'success': False, 'error': 'Введите ник'}, status=400)

        promoter.nickname = nickname[:100]
        promoter.save(update_fields=['nickname'])

        messages.success(request, f'Ник промоутера успешно обновлён на {promoter.nickname}!')
        return JsonResponse({'success': True, 'nickname': promoter.nickname})


class PromoterDeleteView(auth.PromoTreckRequiredMixin, View):
    """Удаление промоутера"""

    def post(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        promoter = get_object_or_404(models.PromoterProfile, pk=pk)
        auth.PromoAccessChecker.check_promoter_or_404(promoter, self.city)

        promoter.delete()

        messages.success(request, f'Промоутер {promoter.nickname} успешно удалён!')
        return JsonResponse({'success': True})


class PromoterLogoutView(auth.PromoTreckRequiredMixin, View):
    """Обновления ключа промоутера"""

    def post(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        promoter = get_object_or_404(models.PromoterProfile, pk=pk)
        auth.PromoAccessChecker.check_promoter_or_404(promoter, self.city)

        promoter.regenerate_api_key()
        return JsonResponse({'success': True})


class PromoterQrView(auth.PromoTreckRequiredMixin, View):
    """Получение данных для QR-кода (для входа промоутера)"""

    def get(self, request: OrganizationRequest, pk: int, *args, **kwargs):
        promoter = get_object_or_404(models.PromoterProfile, pk=pk)
        auth.PromoAccessChecker.check_promoter_or_404(promoter, self.city)

        return JsonResponse({
            'success': True,
            'nickname': promoter.nickname,
            'qr_data': json.dumps({
                'promoter_id': promoter.id,
                'nickname': promoter.nickname,
                'api_key': promoter.get_api_key(),
            }, ensure_ascii=False)
        })
