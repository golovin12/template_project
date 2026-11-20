from django.conf import settings

from accounts.base import actor
from .enums import NotificationProvider, get_info_bot_token
from .models import NotificationSettings, NotificationMessage
from .services import notification_sender

NOTIFICATIONS_QUEUE_NAME = 'notifications'


@actor(queue_name='notifications_queue', time_limit=1 * 60 * 1000, max_age=10 * 60 * 1000, max_retries=0)
def send_notifications():
    """Пакетная отправка сообщений"""
    messages = notification_sender.get_pending_messages(limit=settings.VK_BATCH_SIZE, provider=NotificationProvider.VK)
    send_messages(messages)


def send_messages(messages):
    unsent_messages = []
    for message in messages:
        try:
            if not notification_sender.send_message(message):
                unsent_messages.append(message)
        except Exception:
            unsent_messages.append(message)
    return unsent_messages


@actor(queue_name=NOTIFICATIONS_QUEUE_NAME, time_limit=5 * 60 * 1000, max_age=30 * 60 * 1000)
def cleanup_old_telegram_messages():
    """Задача для удаления старых сообщений (запускается по расписанию)"""
    notification_sender.cleanup_old_messages(days_old=settings.NOTIFICATIONS_CLEANUP_DAYS)


@actor(queue_name=NOTIFICATIONS_QUEUE_NAME, time_limit=30 * 1000, max_age=4 * 60 * 1000)
def create_telegram_message(bot_token: str, chat_id: str, text: str, priority: int = 0,
                            mode: str = NotificationMessage.ParseMode.TEXT):
    """Создание сообщения для отправки в тг"""
    NotificationMessage.objects.create(provider_token=bot_token, recipient_id=chat_id, text=text, mode=mode,
                                       provider=NotificationProvider.TELEGRAM, priority=priority)


@actor(queue_name=NOTIFICATIONS_QUEUE_NAME, time_limit=5 * 60 * 1000, max_age=30 * 60 * 1000)
def push_new_request_message(text: str, city_id: int):
    for notification_settings in NotificationSettings.objects.filter(
            enabled=True,
            notif_type='new',
            citynotificationpreference__enabled=True,
            citynotificationpreference__city_id=city_id).prefetch_related('channels'):
        for channel in notification_settings.channels.filter(enabled=True):
            provider = channel.provider
            NotificationMessage.objects.create(
                provider_token=get_info_bot_token(provider),
                provider=provider,
                recipient_id=channel.recipient_id,
                text=text,
                priority=1,
            )
