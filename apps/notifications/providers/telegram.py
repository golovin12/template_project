from datetime import timedelta

import requests

from django.conf import settings
from django.utils import timezone

from .base import BaseNotificationProvider, clean_html
from ..models import NotificationMessage


class TelegramProvider(BaseNotificationProvider):
    def send(self, message: NotificationMessage, is_html=False) -> bool:
        """Отправляет сообщение с опцией для HTML-форматирования."""
        try:
            url = f'https://api.telegram.org/bot{message.provider_token}/sendMessage'
            payload = {
                'chat_id': message.recipient_id,
                'text': self.prepare_text(message.text, is_html),
                'disable_web_page_preview': True,
            }

            if is_html:
                payload['parse_mode'] = 'HTML'

            r = requests.post(url, json=payload, timeout=(2, 4))
            r.raise_for_status()

            message.status = NotificationMessage.Status.SENT
            message.sent_dt = timezone.now()
            message.save()
            return True

        except Exception as e:
            message.status = NotificationMessage.Status.FAILED
            message.error_message = str(e)
            message.retry_count += 1

            delay = min(
                settings.NOTIFICATIONS_MAX_RETRY_DELAY,
                settings.NOTIFICATIONS_BASE_RETRY_DELAY * (2 ** (message.retry_count - 1))
            )

            message.scheduled_for = timezone.now() + timedelta(seconds=delay)
            message.save()

            return False

    def prepare_text(self, text: str, is_html: bool) -> str:
        """Подготовка текста с учетом необходимости HTML-разметки."""
        if is_html:
            return clean_html(text[:4050])  # Для HTML-текста применяем чистку
        return text[:4096]  # Обычный текст обрезаем до 4096 символов
