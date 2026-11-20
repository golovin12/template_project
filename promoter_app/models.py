import json
import secrets

from asgiref.sync import async_to_sync

from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone

from common_tools.validators import validate_file_field
from int.db_context import DatabaseContext


class PromoterZone(models.Model):
    """
    Модель для хранения привязки промоутера к зоне.
    Хранится в default БД.
    """
    api_key = models.CharField(max_length=64, unique=True, db_index=True, editable=False, verbose_name='API ключ')
    database_alias = models.CharField(max_length=50, verbose_name='Алиас базы данных зоны',
                                      help_text='Алиас БД, к которой принадлежит промоутер')
    promoter_id = models.BigIntegerField(verbose_name='ID промоутера', help_text='ID промоутера в БД зоны')

    class Meta:
        db_table = 'promoter_zone_mapping'
        verbose_name = 'Привязка промоутера к зоне'
        verbose_name_plural = 'Привязки промоутеров к зонам'
        unique_together = [['database_alias', 'promoter_id']]
        indexes = [
            models.Index(fields=['api_key']),
            models.Index(fields=['database_alias', 'promoter_id']),
        ]

    def __str__(self):
        return f'Промоутер {self.promoter_id} -> {self.database_alias}'

    @classmethod
    def get_by_promoter(cls, promoter: 'PromoterProfile'):
        """Получить или создать привязку промоутера к зоне"""
        database_alias = DatabaseContext.get()

        try:
            return cls.objects.get(promoter_id=promoter.id, database_alias=database_alias)
        except cls.DoesNotExist:
            return cls.objects.create(promoter_id=promoter.id, database_alias=database_alias,
                                      api_key=secrets.token_hex(32))

    def regenerate_api_key(self):
        """Регенерация API ключа"""
        old_api_key = self.api_key
        self.api_key = secrets.token_hex(32)
        self.save(update_fields=['api_key'])
        cache_key = f'promoter_api_key:{old_api_key}'
        cache.delete(cache_key)

    @classmethod
    async def get_promoter_by_api_key(cls, api_key: str) -> tuple[str, int]:
        """Получить данные промоутера по API ключу"""
        cache_key = f'promoter_api_key:{api_key}'
        cached = await cache.aget(cache_key)

        if cached:
            return cached['database_alias'], cached['promoter_id']

        try:
            mapping = await cls.objects.aget(api_key=api_key)
            data = {'database_alias': mapping.database_alias, 'promoter_id': mapping.promoter_id}
            await cache.aset(cache_key, data, timeout=60 * 60 * 24)
            return mapping.database_alias, mapping.promoter_id
        except cls.DoesNotExist:
            return '', 0


class PromoterProfile(models.Model):
    city = models.ForeignKey('accounts.City', on_delete=models.CASCADE, related_name='promoters', verbose_name='Город')
    nickname = models.CharField(max_length=100, verbose_name='Ник')

    class Meta:
        verbose_name = 'Промоутер'
        verbose_name_plural = 'Промоутеры'
        ordering = ('city', 'nickname',)
        indexes = [
            models.Index(fields=['city', 'nickname']),
        ]

    def __str__(self):
        return f'{self.nickname} ({self.city})'

    def get_api_key(self):
        """Получить API ключ промоутера"""
        return PromoterZone.get_by_promoter(self).api_key

    def get_zone_alias(self):
        """Получить алиас зоны промоутера"""
        return self._state.db

    def regenerate_api_key(self):
        """Регенерировать API ключ"""
        zone = PromoterZone.get_by_promoter(self)
        zone.regenerate_api_key()
        return zone.api_key


class RouteZone(models.Model):
    city = models.ForeignKey('accounts.City', on_delete=models.CASCADE, related_name='route_zones',
                             verbose_name='Город')

    name = models.CharField(max_length=255, verbose_name='Название маршрута')
    last_assigned_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата последнего назначения')
    is_active = models.BooleanField(default=False, verbose_name='Активный')

    polygon = models.JSONField(verbose_name='Polygon GeoJSON')

    class Meta:
        verbose_name = 'Маршрут'
        verbose_name_plural = 'Маршруты'
        ordering = ('name',)

    def __str__(self):
        return f'{self.city} - {self.name}'

    def get_polygon(self):
        if isinstance(self.polygon, str):
            return json.loads(self.polygon)
        return self.polygon

    def get_color_by_last_assigned(self):
        """Определяет цвет зоны на основе даты последнего назначения"""
        if not self.last_assigned_date:
            return 'green'
        elif self.is_active:
            return 'red'

        now = timezone.now()
        days_diff = (now - self.last_assigned_date).days

        if days_diff <= 15:
            return 'yellow'
        return 'green'


class PromoterAssignment(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Назначен'
        PROCESS = 'process', 'В работе'
        ENDED = 'ended', 'Завершён'

    promoter = models.ForeignKey('PromoterProfile', on_delete=models.CASCADE, related_name='assignments',
                                 verbose_name='Промоутер')
    route_zone = models.ForeignKey('RouteZone', on_delete=models.CASCADE, related_name='assignments',
                                   verbose_name='Маршрут')
    assigned_date = models.DateTimeField(default=timezone.now, verbose_name='Дата назначения')
    assigned_by = models.ForeignKey('accounts.OrganizationUser', on_delete=models.SET_NULL, null=True, verbose_name='Кто назначил')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, verbose_name='Статус')
    is_confirmed = models.BooleanField(default=False, verbose_name='Подтверждён')
    confirmed_dt = models.DateTimeField(null=True, blank=True, verbose_name='Дата подтверждения')
    total_photos = models.IntegerField(default=0, verbose_name='Всего фотографий')
    photos_no_gps = models.IntegerField(default=0, verbose_name='Фото без GPS')
    full_data_loaded = models.BooleanField(default=False, verbose_name='Все данные загружены')
    is_cleaned = models.BooleanField(default=False, verbose_name='Данные очищены')

    class Meta:
        verbose_name = 'Назначение промоутера'
        verbose_name_plural = 'Назначения промоутеров'
        ordering = ('-assigned_date',)

    def __str__(self):
        return f'{self.promoter} - {self.route_zone} ({self.assigned_date.date()})'

    @property
    def is_ended(self):
        return self.status == self.Status.ENDED

    @transaction.atomic
    def cancel(self):
        """
        Отменить назначение промоутера.
        Удаляет назначение, снимает активность маршрута и
        восстанавливает дату предыдущего назначения.
        """
        route = self.route_zone

        if route.is_active:
            route.is_active = False

        latest_assignment = PromoterAssignment.objects.filter(route_zone=route).exclude(pk=self.pk).order_by(
            '-assigned_date').first()

        route.last_assigned_date = latest_assignment.assigned_date if latest_assignment else None

        route.save(update_fields=('is_active', 'last_assigned_date'))

        self.delete()

    async def recalc_stat_and_save(self):
        self.total_photos = await self.photos.acount()
        self.photos_no_gps = await self.photos.filter(has_location=False).acount()
        await self.asave()

    def confirm(self):
        """Метод для подтверждения назначения"""
        if not self.is_confirmed:
            async_to_sync(self.end_route)()
            self.is_confirmed = True
            self.status = self.Status.ENDED
            self.confirmed_dt = timezone.now()
            self.save()

    async def end_route(self):
        route_zone = self.route_zone
        route_zone.is_active = False
        await route_zone.asave(update_fields=('is_active',))


def promoter_photo_upload_to(instance, filename):
    assignment = instance.assignment
    zone = assignment._state.db or 'default'
    return f'promoter_app/models.PromoterPhoto.image/{zone}/{assignment.pk}/{filename}'


class PromoterPhoto(models.Model):
    assignment = models.ForeignKey(PromoterAssignment, on_delete=models.CASCADE, related_name='photos',
                                   verbose_name='Назначение')
    image = models.ImageField(upload_to=promoter_photo_upload_to, max_length=300,
                              validators=[validate_file_field], verbose_name='Изображение')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')
    lat = models.FloatField(null=True, blank=True, verbose_name='Широта')
    lng = models.FloatField(null=True, blank=True, verbose_name='Долгота')
    has_location = models.BooleanField(default=True, verbose_name='Имеет геолокацию')

    class Meta:
        verbose_name = 'Фото промоутера'
        verbose_name_plural = 'Фото промоутеров'
        ordering = ('-created_at',)

    def __str__(self):
        return f'Фото {self.id} - {self.assignment}'

    @property
    def s3_url(self):
        if not hasattr(self, '_cached_s3_url'):
            self._cached_s3_url = self.image.storage.direct_url(self.image.name)

        return self._cached_s3_url
