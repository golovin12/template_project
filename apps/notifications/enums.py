from django.conf import settings
from django.db import models


class NotificationProvider(models.TextChoices):
    TELEGRAM = 'telegram', 'Telegram'
    VK = 'vk', 'VK'


def get_info_bot_token(provider: NotificationProvider) -> str:
    match provider:
        case NotificationProvider.TELEGRAM:
            return settings.TELEGRAM['INFO_BOT_TOKEN']
        case NotificationProvider.VK:
            return settings.VK['INFO_BOT_TOKEN']
    return ''


class NotificationEventType(models.TextChoices):
    NEW = 'new', 'Создание'
    ASSIGN = 'assign', 'Назначение'
