from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import Branch, OrganizationUser
from apps.service_requests.consts import SPECIFIC_FIELDS_VIEW_BEFORE_MINUTES
from common_tools.number import format_money
from int.db_context import cache_key


class DeviceType(models.Model):
    cache_identifier = 'device_type_choices'
    name = models.CharField(max_length=30, unique=True, verbose_name='Наименование')
    is_available_for_all = models.BooleanField(
        'Доступно для всех филиалов',
        default=True,
        help_text='Если отмечено, тип техники будет доступен во всех филиалах автоматически'
    )

    branches = models.ManyToManyField(
        'accounts.Branch',
        related_name='device_types',
        verbose_name='Филиалы',
        blank=True
    )

    class Meta:
        verbose_name = 'Тип техники'
        verbose_name_plural = 'Типы техники'
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_names(cls, branch_id=None) -> list[str]:
        """Получить names для селекта, с фильтрацией по филиалу если нужно"""
        device_types_key = cache_key(f'{cls.cache_identifier}_{branch_id}' if branch_id else cls.cache_identifier)
        names = cache.get(device_types_key)

        if names is None:
            queryset = cls.objects.all()

            if branch_id:
                queryset = queryset.filter(
                    models.Q(branches__id=branch_id) |
                    models.Q(is_available_for_all=True)
                ).distinct()

            names = [dt.name for dt in queryset]
            cache.set(device_types_key, names, timeout=24 * 60 * 60)
        return names

    @classmethod
    def get_branch_by_name(cls) -> dict:
        """Получить словарь типов техники сгруппированных по филиалам."""
        device_type_by_branch_key = cache_key(f'{cls.cache_identifier}_branches_dict')
        result = cache.get(device_type_by_branch_key)

        if result is None:
            result = {}

            for device_type in cls.objects.prefetch_related('branches').all():
                if device_type.is_available_for_all:
                    result[device_type.name] = 'all'
                else:
                    branch_ids = list(device_type.branches.values_list('id', flat=True))
                    result[device_type.name] = branch_ids

            cache.set(device_type_by_branch_key, result, timeout=24 * 60 * 60)

        return result

    @classmethod
    def clear_cache(cls):
        """Очистка кэша с поддержкой разных бэкендов"""
        try:
            cache.delete_pattern(cache_key(f'{cls.cache_identifier}_*'))
        except AttributeError:
            try:
                active_branches = Branch.active_objects.values_list('id', flat=True)
                for branch_id in active_branches:
                    cache.delete(cache_key(f'{cls.cache_identifier}_{branch_id}'))
                cache.delete(cache_key(f'{cls.cache_identifier}_branches_dict'))
            except:  # noqa: E722
                pass

        cache.delete(cache_key(cls.cache_identifier))

    def get_available_branches(self) -> models.QuerySet[Branch]:
        """Получить доступные филиалы для этого типа техники"""
        if self.is_available_for_all:
            return Branch.active_objects
        return self.branches.filter(is_active=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.clear_cache()

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        self.clear_cache()


class ServiceRequest(models.Model):
    class REQUEST_TYPE_CHOICES(models.TextChoices):
        FIRST_TIME = 'first_time', 'Впервые'
        REPEAT = 'repeat', 'Повтор'
        WARRANTY = 'warranty', 'Гарантия'

    class STATUS(models.TextChoices):
        NEW = 'new', 'Новая'
        ASSIGNED = 'assigned', 'Назначена'
        ON_WAY = 'on_way', 'В пути'
        IN_PROGRESS = 'in_progress', 'В работе'
        SERVICE_DIAGNOSTICS = 'service_diagnostics', 'Сервис. диагностика'
        COMPLETED = 'completed', 'Завершена'
        CANCELED = 'canceled', 'Отменена'

    request_number = models.PositiveIntegerField('Номер заявки', unique=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children',
                               verbose_name='Родительская заявка')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES.choices, verbose_name='Тип заявки')
    request_time = models.DateTimeField(default=timezone.now, verbose_name='Время заявки')
    created_by = models.ForeignKey('accounts.OrganizationUser', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_requests', verbose_name='Кем создана')
    status = models.CharField(max_length=20, choices=STATUS.choices, default=STATUS.NEW, verbose_name='Статус заявки')
    branch = models.ForeignKey('accounts.Branch', on_delete=models.SET_NULL, null=True, verbose_name='Филиал')
    city = models.ForeignKey('accounts.City', on_delete=models.SET_NULL, null=True, verbose_name='Город')
    client_name = models.CharField(max_length=100, verbose_name='Имя клиента')
    client_address = models.CharField(max_length=255, verbose_name='Адрес клиента')
    client_phone = models.CharField(max_length=15, verbose_name='Телефон для связи', blank=True)
    problem_description = models.TextField(verbose_name='Описание проблемы')
    device_type = models.CharField(max_length=30, verbose_name='Тип техники', blank=True)
    time_to_service = models.DateTimeField(verbose_name='Время для обслуживания')

    service_report = models.TextField(blank=True, verbose_name='Отчет о работе')
    sd_closing_date = models.DateField('Дата для закрытия СД', null=True, blank=True)
    other_expenses = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name='Прочие затраты (руб.)')
    closing_time = models.DateTimeField(null=True, blank=True, verbose_name='Время закрытия')
    closing_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                         verbose_name='Прибыль (руб.)')

    class Meta:
        verbose_name = 'Заявка на ремонт'
        verbose_name_plural = 'Заявки на ремонт'
        ordering = ('-pk',)
        indexes = (
            models.Index(fields=('branch', 'status')),
            models.Index(fields=('city', 'status', 'closing_time')),
        )

    def __str__(self):
        return f'Заявка #{self.request_number}'

    def save(self, *args, **kwargs):
        if self.branch:
            self.city_id = self.branch.city_id
        super().save(*args, **kwargs)

    @property
    def is_status_end(self) -> bool:
        return self.status == self.STATUS.COMPLETED or self.status == self.STATUS.CANCELED

    @property
    def is_status_diagnostic(self) -> bool:
        return self.status == self.STATUS.SERVICE_DIAGNOSTICS

    @property
    def is_status_progress(self) -> bool:
        return self.status == self.STATUS.IN_PROGRESS

    @property
    def is_status_assigned(self) -> bool:
        return self.status == self.STATUS.ASSIGNED

    @property
    def is_status_on_way(self) -> bool:
        return self.status == self.STATUS.ON_WAY

    @property
    def is_status_completed(self) -> bool:
        return self.status == self.STATUS.COMPLETED

    @property
    def is_status_new(self) -> bool:
        return self.status == self.STATUS.NEW

    def get_data_to_text(self) -> str:
        """Возвращает информацию о заявке в текстовом виде"""
        client_address = self.client_address

        device_type = '' if not self.device_type else f'{self.device_type}: '
        problem = f'{device_type}{self.problem_description}'
        result_text = (f'Заявка #{self.request_number}, {self.get_request_type_display()}, {client_address}, '
                       f'{problem}, {self.client_name}, {self.get_time_to_service_display()}')
        return result_text

    def get_data_to_html(self, sender: str = '') -> str:
        """Возвращает удобочитаемое HTML-сообщение."""
        client_address = self.client_address

        device_type = f'{self.device_type}: ' if self.device_type else ''
        problem = f'{device_type}{self.problem_description}'

        svc_path = reverse('service_request:request_detail', kwargs={'pk': self.pk})
        url = f'https://{settings.SERVER_DOMAIN}{svc_path}'
        title = f'<b>🛠 Новая заявка</b> <a href="{url}">#{self.request_number}</a>'

        html_lines = [
            title,
            f'<b>Филиал:</b> {self.branch}',
            f'<b>Тип:</b> {self.get_request_type_display()}',
            f'<b>Проблема:</b> {problem}',
            f'<b>Адрес:</b> {client_address}',
            f'<b>Клиент:</b> {self.client_name}',
            f'<b>Время обслуживания:</b> {self.get_time_to_service_display()}',
        ]

        return '\n'.join(html_lines)

    def get_data_to_vk(self, sender: str = '') -> str:
        """Возвращает текстовое сообщение для ВКонтакте без форматирования."""
        client_address = self.client_address

        device_type = f'{self.device_type}: ' if self.device_type else ''
        problem = f'{device_type}{self.problem_description}'

        svc_path = reverse('service_request:request_detail', kwargs={'pk': self.pk})
        url = f'https://{settings.SERVER_DOMAIN}{svc_path}'
        title = f'Новая заявка #{self.request_number}\n{url}'

        message_lines = [
            title,
            f'Филиал: {self.branch}',
            f'Тип: {self.get_request_type_display()}',
            f'Проблема: {problem}',
            f'Адрес: {client_address}',
            f'Клиент: {self.client_name}',
            f'Время обслуживания: {self.get_time_to_service_display()}',
        ]

        return '\n'.join(message_lines)

    def get_closing_amount_display(self) -> str:
        return 'Не указана' if self.closing_amount is None else f'{format_money(self.closing_amount)} руб.'

    def get_request_time_display(self) -> str:
        return self.request_time.strftime('%d.%m.%Y %H:%M')

    def get_closing_time_display(self) -> str:
        return 'Не закрыта' if self.closing_time is None else self.closing_time.strftime('%d.%m.%Y %H:%M')

    def get_time_to_service_display(self) -> str:
        return self.time_to_service.strftime('%d.%m.%Y %H:%M')

    def get_sd_closing_date_display(self) -> str:
        return self.sd_closing_date.strftime('%d.%m.%Y')

    def get_other_expenses_display(self) -> str:
        return '—' if self.other_expenses is None else f'{format_money(self.other_expenses)} руб.'

    def can_view_specific_fields(self, user: OrganizationUser = None) -> bool:
        """Проверка: может ли данный пользователь видеть номер квартиры и телефон"""
        if user and not user.is_city_admin:
            return True

        # Админы видят только за N минут до обслуживания
        return timezone.now() >= self.time_to_service - timedelta(minutes=SPECIFIC_FIELDS_VIEW_BEFORE_MINUTES)
