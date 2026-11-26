import threading
import time
from datetime import timedelta

from django.utils import timezone
from django.conf import settings

from .enums import NotificationProvider
from .models import NotificationMessage
from .providers.registry import ProviderRegistry


class BaseRateLimiter:
    def can_send(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    def record(self, *args, **kwargs):
        raise NotImplementedError


class TelegramRateLimiter:
    def __init__(self):
        self.global_messages = []
        self.chat_messages = {}
        self.window_size = 5  # для chat (1 сообщение в 5 сек)
        self.lock = threading.Lock()

    def can_send(self, chat_id: str) -> bool:
        now = time.time()

        with self.lock:
            if chat_id in self.chat_messages:
                self.chat_messages[chat_id] = [
                    ts for ts in self.chat_messages[chat_id] if now - ts < self.window_size
                ]

                if len(self.chat_messages[chat_id]) >= 1:
                    return False

            self.global_messages = [ts for ts in self.global_messages if now - ts < 1.0]

            if len(self.global_messages) >= 30:
                return False

            return True

    def record(self, chat_id: str):
        now = time.time()

        with self.lock:
            self.global_messages.append(now)
            self.chat_messages.setdefault(chat_id, []).append(now)


class VKRateLimiter:
    def __init__(self):
        self.messages = []
        self.window = 1.0
        self.lock = threading.Lock()

    def can_send(self) -> bool:
        now = time.time()

        with self.lock:
            self.messages = [ts for ts in self.messages if now - ts < self.window]

            return len(self.messages) < 10

    def record(self):
        with self.lock:
            self.messages.append(time.time())


class NotificationSender:
    def __init__(self):
        self.rate_limiters = {
            NotificationProvider.TELEGRAM: TelegramRateLimiter(),
            NotificationProvider.VK: VKRateLimiter(),
        }

    def get_pending_messages(self, limit: int, provider: str):
        now = timezone.now()

        return list(
            NotificationMessage.objects.filter(
                provider=provider,
                status__in=[
                    NotificationMessage.Status.PENDING,
                    NotificationMessage.Status.RATE_LIMITED,
                    NotificationMessage.Status.FAILED
                ],
                scheduled_for__lte=now,
                retry_count__lt=settings.NOTIFICATIONS_MAX_RETRIES
            ).order_by('-priority', 'scheduled_for')[:limit]
        )

    def send_message(self, message: NotificationMessage) -> bool:
        provider_enum = message.provider
        provider = ProviderRegistry.get(provider_enum)
        limiter = self.rate_limiters.get(provider_enum)

        if isinstance(limiter, TelegramRateLimiter):
            if not limiter.can_send(message.recipient_id):
                message.status = NotificationMessage.Status.RATE_LIMITED
                message.scheduled_for = timezone.now() + timedelta(seconds=1)
                message.save()
                return False

            limiter.record(message.recipient_id)

        elif isinstance(limiter, VKRateLimiter):
            if not limiter.can_send():
                message.status = NotificationMessage.Status.RATE_LIMITED
                message.scheduled_for = timezone.now() + timedelta(seconds=1)
                message.save()
                return False

            limiter.record()

        is_html = message.mode == NotificationMessage.ParseMode.HTML
        return provider.send(message, is_html=is_html)

    def cleanup_old_messages(self, days_old: int = 30) -> None:
        """Удаление старых сообщений"""
        cutoff_date = timezone.now() - timedelta(days=days_old)

        NotificationMessage.objects.filter(
            status=NotificationMessage.Status.SENT,
            sent_dt__lt=cutoff_date
        ).delete()
        NotificationMessage.objects.filter(
            retry_count__gte=settings.NOTIFICATIONS_MAX_RETRIES,
        ).delete()


notification_sender = NotificationSender()
