import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone

from int.db_context import DatabaseContext
from .enums import NotificationProvider, NotificationEventType


class NotificationMessage(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'В ожидании'
        SENT = 'sent', 'Отправлено'
        FAILED = 'failed', 'Ошибка отправки'
        RATE_LIMITED = 'rate_limited', 'Ограничение частоты'

    class ParseMode(models.TextChoices):
        TEXT = 'text', 'Текст'
        HTML = 'html', 'HTML'

    provider = models.CharField(max_length=20, choices=NotificationProvider.choices)

    provider_token = models.CharField(max_length=255, blank=True, null=True)

    recipient_id = models.CharField(max_length=100, help_text='chat_id (TG) или peer_id (VK)')

    text = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    priority = models.IntegerField(default=0)  # Приоритет отправки (0 - обычный, 1 - высокий)
    mode = models.CharField(max_length=5, choices=ParseMode.choices, default=ParseMode.TEXT)
    scheduled_for = models.DateTimeField(default=timezone.now)
    sent_dt = models.DateTimeField(null=True, blank=True)
    created_dt = models.DateTimeField(auto_now_add=True)
    updated_dt = models.DateTimeField(auto_now=True)
    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Уведомление пользователю'
        verbose_name_plural = 'Уведомления пользователям'
        ordering = ('-priority', 'scheduled_for')
        indexes = [
            models.Index(fields=['provider', 'status', 'scheduled_for']),
        ]

    def __str__(self):
        return f'{self.provider} → {self.recipient_id} ({self.status})'


class NotificationSettings(models.Model):
    user = models.OneToOneField('accounts.OrganizationUser', on_delete=models.CASCADE, verbose_name='Пользователь')
    enabled = models.BooleanField('Уведомления включены', default=True)

    notif_type = models.CharField(max_length=10, choices=NotificationEventType.choices, verbose_name='Тип уведомления')

    created_dt = models.DateTimeField(auto_now_add=True)
    updated_dt = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Настройка уведомлений'
        verbose_name_plural = 'Настройки уведомлений'

    def __str__(self):
        return f'Настройки {self.user}'


class NotificationChannel(models.Model):
    notification_settings = models.ForeignKey(
        NotificationSettings,
        on_delete=models.CASCADE,
        related_name='channels'
    )

    provider = models.CharField(max_length=20, choices=NotificationProvider.choices)

    recipient_id = models.CharField(
        max_length=100,
        help_text='chat_id (TG) или peer_id (VK)'
    )

    username = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Провайдер уведомлений'
        verbose_name_plural = 'Провайдеры уведомлений'

    def __str__(self):
        return f'{self.provider}: {self.recipient_id}'


class CityNotificationPreference(models.Model):
    notification_settings = models.ForeignKey(NotificationSettings, on_delete=models.CASCADE,
                                              verbose_name='Настройки уведомлений')
    city = models.ForeignKey('accounts.City', on_delete=models.CASCADE, verbose_name='Город')
    enabled = models.BooleanField('Уведомления включены', default=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Настройка уведомлений по городам'
        verbose_name_plural = 'Настройки уведомлений по городам'
        unique_together = ('notification_settings', 'city')

    def __str__(self):
        return f'{self.city}'


class NotificationConnectCode(models.Model):
    """Код для подключения к бд, хранится в default"""
    user_id = models.BigIntegerField(verbose_name='ID пользователя')
    code = models.CharField(max_length=32, unique=True)

    provider = models.CharField(max_length=20, choices=NotificationProvider.choices)
    database_alias = models.CharField('Алиас БД', max_length=50)

    created_dt = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.code} ({self.provider})'


def get_or_create_connect_code(user, provider):
    """Получить или создать код подключения для пользователя"""
    db_alias = DatabaseContext.get()

    now = timezone.now()

    obj = NotificationConnectCode.objects.filter(
        database_alias=db_alias,
        user_id=user.id,
        provider=provider
    ).first()

    if obj and obj.expires_at > now and not obj.is_used:
        return obj

    code = f'{provider[:2].upper()}-{secrets.token_hex(4).upper()}'

    expires_at = now + timedelta(minutes=30)

    if obj:
        obj.code = code
        obj.expires_at = expires_at
        obj.is_used = False
        obj.save(update_fields=['code', 'expires_at', 'is_used'])
        return obj

    return NotificationConnectCode.objects.create(
        database_alias=db_alias,
        user_id=user.id,
        provider=provider,
        code=code,
        expires_at=expires_at
    )
