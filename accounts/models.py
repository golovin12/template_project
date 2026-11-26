from django.core.cache import cache
from django.db import models
from django.http import Http404

from identity.models import AuthUser
from int.db_context import cache_key
from common_tools.managers import ActiveManager
from .consts import USER_ROLES


class City(models.Model):
    cache_identifier = 'city_active_choices'
    name = models.CharField(max_length=100, unique=True, verbose_name='Город')
    is_active = models.BooleanField('Активный', default=True, help_text='Уберите галочку, вместо удаления')

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        ordering = ('-is_active', 'name')

    def __str__(self):
        return self.name

    @classmethod
    def get_active_choices(cls):
        city_key = cache_key(cls.cache_identifier)
        choices = cache.get(city_key)

        if choices is None:
            choices = [(city.id, city.name) for city in cls.active_objects.all()]
            cache.set(city_key, choices, timeout=24 * 60 * 60)

        return choices

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(cache_key(self.cache_identifier))
        cache.delete(cache_key(Branch.cache_identifier))

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(cache_key(self.cache_identifier))
        cache.delete(cache_key(Branch.cache_identifier))


class Branch(models.Model):
    cache_identifier = 'branch_active_choices'
    name = models.CharField(max_length=100, verbose_name='Название')
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name='branches', verbose_name='Город')
    is_active = models.BooleanField('Активный', default=True, help_text='Уберите галочку, вместо удаления')

    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        verbose_name = 'Филиал'
        verbose_name_plural = 'Филиалы'
        ordering = ('-is_active', 'city__name', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('city', 'name'),
                name='unique_city_name'
            )
        ]

    def __str__(self):
        return f'{self.city} ({self.name})'

    @classmethod
    def get_active_choices(cls):
        branch_key = cache_key(cls.cache_identifier)
        choices = cache.get(branch_key)

        if choices is None:
            choices = [(branch.id, str(branch)) for branch in cls.active_objects.select_related('city')]
            cache.set(branch_key, choices, timeout=24 * 60 * 60)

        return choices

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(cache_key(self.cache_identifier))

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(cache_key(self.cache_identifier))


class OrganizationUser(models.Model):
    user_id = models.BigIntegerField(unique=True, db_index=True, verbose_name='ID пользователя')
    username = models.CharField('Логин', max_length=150, db_index=True)
    first_name = models.CharField('Имя', max_length=150, blank=True)
    last_name = models.CharField('Фамилия', max_length=150, blank=True)
    second_name = models.CharField('Отчество', max_length=150, blank=True)
    is_global_superuser = models.BooleanField('Глобальный суперпользователь', default=False, editable=False)

    is_superuser = models.BooleanField(
        'Статус суперпользователя', default=False,
        help_text='Означает, что у этого пользователя есть все разрешения без их явного назначения',
    )
    role = models.CharField('Роль', max_length=20, choices=USER_ROLES.choices, blank=True)

    cities = models.ManyToManyField(City, blank=True, related_name='users', verbose_name='Города')
    all_cities_access = models.BooleanField('Доступ ко всем городам', default=False,
                                            help_text='Поставьте галочку, если пользователь должен иметь доступ '
                                                      'ко всем городам.')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('-is_superuser', 'role')

    def __str__(self):
        return f'{self.full_name or self.username} ({self.get_role_display()})'

    @property
    def full_name(self):
        return f'{self.last_name} {self.first_name} {self.second_name}'.strip()

    @property
    def auth_user(self):
        if not hasattr(self, '_auth_user'):
            try:
                self._auth_user = AuthUser.objects.get(id=self.user_id)
                self._auth_user._organization_user = self
            except self.DoesNotExist:
                self.delete()
                raise Http404('Аккаунт был удалён')
        return self._auth_user

    @property
    def is_manager(self):
        return self.role == USER_ROLES.MANAGER or self.is_superuser

    @property
    def is_city_admin(self):
        return self.role == USER_ROLES.CITY_ADMIN

    @property
    def is_chief(self):
        return self.role == USER_ROLES.CHIEF

    @property
    def allowed_branch_choices(self):
        allowed_ids = set(self.allowed_branch_ids)
        return [(branch_id, label) for branch_id, label in Branch.get_active_choices() if branch_id in allowed_ids]

    @property
    def allowed_city_choices(self):
        allowed_ids = set(self.allowed_city_ids)
        return [(city_id, label) for city_id, label in City.get_active_choices() if city_id in allowed_ids]

    @property
    def allowed_branch_ids(self) -> list[int]:
        return self._get_access_data()['branch_ids']

    @property
    def allowed_city_ids(self) -> list[int]:
        return list(self._get_access_data()['city_branch_map'].keys())

    @property
    def city_branch_map(self) -> dict[int: int]:
        return self._get_access_data()['city_branch_map']

    def sync_and_save(self):
        auth_user = self.auth_user
        self.username = auth_user.username
        self.first_name = auth_user.first_name
        self.last_name = auth_user.last_name
        self.second_name = auth_user.second_name
        self.is_global_superuser = auth_user.is_superuser
        return super().save()

    def has_perm(self, perm, obj=None):
        # Проверка прав на доступ к media файлу
        if self.is_manager:
            return True
        elif perm == 'service_requests.view_closingphoto' and (self.is_chief or self.is_city_admin):
            return True
        elif perm == 'bookkeeping.view_accountingentry' and self.is_chief:
            return True
        elif perm == 'promoter_app.view_promoterphoto' and (self.is_chief or self.is_city_admin):
            return True
        return False

    def _get_access_data(self):
        if hasattr(self, '_access_data_cache'):
            return self._access_data_cache

        cached = self._get_cached_access()
        if cached:
            self._access_data_cache = cached
            return cached

        branches_qs = Branch.active_objects

        if not (self.all_cities_access or self.is_manager):
            branches_qs = branches_qs.filter(city__users=self)

        branch_ids = []
        city_branch_map = {}

        for branch_id, city_id in branches_qs.values_list('id', 'city_id'):
            branch_ids.append(branch_id)
            city_branch_map.setdefault(city_id, []).append(branch_id)

        data = {
            'branch_ids': branch_ids,
            'city_branch_map': city_branch_map,
        }

        self._set_cached_access(data)
        self._access_data_cache = data
        return data

    def _access_cache_key(self):
        return cache_key(f'user_access:{self.pk}')

    def _get_cached_access(self):
        return cache.get(self._access_cache_key())

    def _set_cached_access(self, data):
        cache.set(self._access_cache_key(), data, timeout=24 * 60 * 60)

    def clear_cache(self):
        cache.delete(self._access_cache_key())
