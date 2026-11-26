import logging
import hashlib
import threading
import time

from django.conf import settings
from django.core.cache import cache


class TelegramBotHandler(logging.Handler):
    """Отправка сообщений в телеграм при ошибках на сервере с кешированием повторений"""

    CACHE_KEY_PREFIX = 'telegram_error_'
    DEDUPLICATION_WINDOW = 300  # 5 минут в секундах
    _local = threading.local()

    def __init__(self):
        super().__init__()
        self.bot_token = settings.TELEGRAM['ADMIN_BOT_TOKEN']
        self.chat_id = settings.TELEGRAM['ADMIN_CHAT_ID']
        self._message_cache: dict[str, float] = {}

    def _get_message_fingerprint(self, record: logging.LogRecord) -> str:
        """
        Создает устойчивый отпечаток ошибки.
        Убирает переменные части traceback'а, чтобы повторяющиеся ошибки считались одинаковыми.
        """
        parts = []

        base_msg = record.getMessage()
        parts.append(base_msg[:300])

        if record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            exc_name = exc_type.__name__
            exc_text = str(exc_value)
            parts.append(exc_name)
            parts.append(exc_text[:300])

        parts.append(f"{record.pathname}:{record.lineno}")

        content = "|".join(parts)
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def _should_send_message(self, fingerprint: str) -> bool:
        """
        Проверяет, нужно ли отправлять сообщение.
        Возвращает False, если такое же сообщение уже отправлялось в течение 5 минут.
        """
        current_time = time.time()
        if fingerprint in self._message_cache:
            last_sent = self._message_cache[fingerprint]
            if current_time - last_sent < self.DEDUPLICATION_WINDOW:
                return False

        cache_key = f"{self.CACHE_KEY_PREFIX}{fingerprint}"
        last_sent_cached = cache.get(cache_key)

        if last_sent_cached:
            if current_time - last_sent_cached < self.DEDUPLICATION_WINDOW:
                self._message_cache[fingerprint] = last_sent_cached
                return False

        self._message_cache[fingerprint] = current_time
        cache.set(cache_key, current_time, timeout=self.DEDUPLICATION_WINDOW + 60)

        self._cleanup_local_cache()
        return True

    def _cleanup_local_cache(self):
        """Очищает старые записи из локального кеша"""
        current_time = time.time()
        old_fingerprints = [
            fp for fp, timestamp in self._message_cache.items()
            if current_time - timestamp > self.DEDUPLICATION_WINDOW * 2
        ]
        for fp in old_fingerprints:
            del self._message_cache[fp]

    def emit(self, record):
        if getattr(self._local, 'handling', False):
            return

        self._local.handling = True
        try:
            # Импорт не выносить: для акторов инициализируется не тот брокер
            from apps.notifications.tasks import create_telegram_message

            error_msg = self.format(record).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

            if not record.exc_info:
                text = f'<b>Сообщение из Django:</b>\n<code>{error_msg}</code>'
                create_telegram_message.send(self.bot_token, self.chat_id, text, 0, 'html')
                return

            fingerprint = self._get_message_fingerprint(record)

            if not self._should_send_message(fingerprint):
                return

            text = f'<b>Ошибка в Django:</b>\n<code>{error_msg}</code>'
            create_telegram_message.send(self.bot_token, self.chat_id, text, 0, 'html')
        except Exception:
            pass
        finally:
            self._local.handling = False
