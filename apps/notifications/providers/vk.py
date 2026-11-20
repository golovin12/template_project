import time
import random
from datetime import timedelta

import requests

from django.conf import settings
from django.utils import timezone

from .base import BaseNotificationProvider
from ..models import NotificationMessage


class VKProvider(BaseNotificationProvider):
    API_URL = 'https://api.vk.ru/method/messages.send'
    API_VERSION = '5.199'

    def _generate_random_id(self) -> int:
        """Генерация уникального random_id"""
        return int(time.time() * 1000) + random.randint(0, 1000)

    def send(self, message: NotificationMessage, is_html=False) -> bool:
        try:
            payload = {
                'peer_id': int(message.recipient_id),
                'message': message.text[:9000],
                'random_id': self._generate_random_id(),
                'access_token': message.provider_token,
                'v': self.API_VERSION,
                'disable_mentions': 1,
                'dont_parse_links': 1,
            }

            response = requests.post(self.API_URL, data=payload, timeout=10)

            data = response.json()

            if 'error' in data:
                return self._handle_vk_error(message, data['error'])

            message.status = NotificationMessage.Status.SENT
            message.sent_dt = timezone.now()
            message.error_message = None
            message.save(update_fields=['status', 'sent_dt', 'error_message', 'updated_dt'])

            return True

        except requests.exceptions.Timeout:
            return self._retry(message, 'VK timeout')

        except requests.exceptions.ConnectionError:
            return self._retry(message, 'VK connection error')

        except Exception as e:
            return self._retry(message, f'Unexpected error: {str(e)}')

    def _handle_vk_error(self, message: NotificationMessage, error: dict) -> bool:
        """Обработка ошибок VK API"""
        error_code = error.get('error_code')
        error_msg = error.get('error_msg', '')

        full_error = f'[VK {error_code}] {error_msg}'

        if error_code == 104 or error_code >= 900:
            message.status = NotificationMessage.Status.FAILED
            message.error_message = full_error
            message.retry_count = settings.NOTIFICATIONS_MAX_RETRIES

            message.save(update_fields=['status', 'error_message', 'retry_count', 'updated_dt'])
            return False

        return self._retry(message, full_error)

    def _retry(self, message: NotificationMessage, error_msg: str) -> bool:
        """Retry"""
        message.status = NotificationMessage.Status.FAILED
        message.error_message = error_msg
        message.retry_count += 1

        delay = min(
            settings.NOTIFICATIONS_MAX_RETRY_DELAY,
            settings.NOTIFICATIONS_BASE_RETRY_DELAY * (2 ** (message.retry_count - 1))
        )

        message.scheduled_for = timezone.now() + timedelta(seconds=delay)

        message.save(update_fields=['status', 'error_message', 'retry_count', 'scheduled_for', 'updated_dt'])

        return False
