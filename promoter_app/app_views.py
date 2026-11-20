import io
import json

from PIL import Image
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.handlers.asgi import ASGIRequest
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from . import auth, models
from .consts import APP_VERSIONS_CACHE_KEY, DEFAULT_APP_VERSIONS, Version


@method_decorator(csrf_exempt, name='dispatch')
class VersionCheckApiView(View):

    async def post(self, request: ASGIRequest):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        version_str = data.get('version')
        platform = data.get('platform')

        if not version_str:
            return JsonResponse({'error': 'Version is required'}, status=400)

        if platform not in ('android', 'ios'):
            return JsonResponse({'error': 'Unsupported platform'}, status=400)

        versions = await cache.aget(APP_VERSIONS_CACHE_KEY, DEFAULT_APP_VERSIONS)

        platform_versions = versions.get(platform, {})

        minimum_version = Version.try_parse(platform_versions.get('minimum'))

        latest_version = Version.try_parse(platform_versions.get('latest'))

        current_version = Version.try_parse(version_str)

        return JsonResponse({
            'needUpdate': current_version < minimum_version,
            'hasNewVersion': current_version < latest_version,
        })


class AuthCheckApiView(View):
    """Api для проверки данных подключения. + Выдача ника"""

    async def get(self, request):
        promoter_id = request.GET.get('promoter_id')
        has_promoter, promoter_id_valid = await auth.promoter_request_exists(request)

        if not has_promoter or promoter_id != str(promoter_id_valid):
            return JsonResponse({'error': 'Доступ запрещён', 'code': 'ACCESS_DENIED'}, status=403)

        try:
            promoter = await models.PromoterProfile.objects.aget(id=promoter_id_valid)
        except models.PromoterProfile.DoesNotExist:
            return JsonResponse({'error': 'Доступ запрещён', 'code': 'ACCESS_DENIED'}, status=403)
        return JsonResponse({'success': True, 'nickname': promoter.nickname})


class MyAssignmentsApiView(View):
    """API для получения назначений промоутера"""

    @auth.promoter_required
    async def get(self, request, *args, **kwargs):
        promoter_id = request.GET.get('promoter_id')

        if promoter_id != str(request.promoter_id):
            return JsonResponse({'error': 'Доступ запрещён', 'code': 'ACCESS_DENIED'}, status=403)

        assignments = models.PromoterAssignment.objects.filter(
            promoter_id=promoter_id
        ).exclude(status=models.PromoterAssignment.Status.ENDED).exclude(is_cleaned=True).select_related('route_zone')

        data = []
        async for a in assignments:
            data.append({
                'assignment_id': a.id,
                'route_id': a.route_zone.id,
                'route_name': a.route_zone.name,
                'polygon': a.route_zone.get_polygon(),
                'status': a.status,
                'assigned_date': a.assigned_date.strftime('%d.%m.%Y %H:%M')
            })

        return JsonResponse({'routes': data, 'success': True})


@method_decorator(csrf_exempt, name='dispatch')
class AssignmentUploadAPIView(View):
    """API для загрузки фотографий и обновления статуса назначения"""

    MAX_PHOTO_SIZE = 300 * 1024

    @auth.promoter_required
    async def post(self, request, *args, **kwargs):
        assignment_id = request.POST.get('assignment_id')
        new_status = request.POST.get('status')

        if not assignment_id:
            return JsonResponse({'error': 'Не указан ID назначения', 'code': 'MISSING_ASSIGNMENT_ID'}, status=400)

        try:
            assignment = await models.PromoterAssignment.objects.select_related('route_zone').aget(id=assignment_id)
        except models.PromoterAssignment.DoesNotExist:
            return JsonResponse({'error': 'Назначение не найдено', 'code': 'NOT_FOUND'}, status=404)

        if assignment.promoter_id != request.promoter_id:
            return JsonResponse({'error': 'Доступ запрещён', 'code': 'ACCESS_DENIED'}, status=403)

        if assignment.is_cleaned:
            return JsonResponse({'success': True, 'message': ' Назначение уже закрыто, фото больше не сохраняются!'})

        statuses = models.PromoterAssignment.Status
        if new_status in (statuses.PROCESS, statuses.ENDED):
            if assignment.status != statuses.ENDED:
                assignment.status = new_status
                if new_status == statuses.ENDED:
                    await assignment.end_route()

        assignment.full_data_loaded = request.POST.get('full_data_loaded') == 'true'

        files = request.FILES.getlist('photos')
        lat_list = request.POST.getlist('lat')
        lng_list = request.POST.getlist('lng')
        has_location_list = request.POST.getlist('has_location')

        created_photos_count = 0

        for idx, file in enumerate(files):
            compressed_file = await self._compress_photo(file)

            lat = self._parse_float(lat_list[idx]) if idx < len(lat_list) else None
            lng = self._parse_float(lng_list[idx]) if idx < len(lng_list) else None
            has_location = self._parse_bool(has_location_list[idx]) if idx < len(has_location_list) else True

            await models.PromoterPhoto.objects.acreate(
                assignment=assignment,
                image=compressed_file,
                created_at=timezone.now(),
                lat=lat,
                lng=lng,
                has_location=has_location
            )
            created_photos_count += 1

        await assignment.recalc_stat_and_save()

        return JsonResponse({
            'success': True,
            'message': f'Успешно загружено {created_photos_count} фотографий',
            'stats': {
                'total_photos': assignment.total_photos,
                'photos_no_gps': assignment.photos_no_gps,
            }
        })

    async def _compress_photo(self, file):
        if file.size <= self.MAX_PHOTO_SIZE + 100 * 1024:
            return file

        return await sync_to_async(self._compress_photo_sync)(file)

    def _compress_photo_sync(self, file):
        image = Image.open(file)
        image.load()

        if image.mode != 'RGB':
            image = image.convert('RGB')

        max_dimension = 1920
        quality = 70

        while True:
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            image.save(
                output,
                format='JPEG',
                quality=quality,
                optimize=True,
                progressive=True
            )

            if output.tell() <= self.MAX_PHOTO_SIZE:
                output.seek(0)
                return InMemoryUploadedFile(
                    output,
                    field_name='photos',
                    name=f'{file.name.rsplit(".", 1)[0]}.jpg',
                    content_type='image/jpeg',
                    size=output.tell(),
                    charset=None,
                )

            if quality > 40:
                quality -= 10
            else:
                max_dimension = int(max_dimension * 0.8)
                quality = 70

    def _parse_float(self, value: str) -> float | None:
        """Безопасный парсинг float"""
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_bool(self, value: str) -> bool:
        """Безопасный парсинг boolean"""
        return value == 'true' if value else True
