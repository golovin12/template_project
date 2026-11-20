from dramatiq.middleware import Middleware

from django.conf import settings


class CloseConnectionAfterEnqueue(Middleware):
    def after_enqueue(self, broker, message, delay):
        """Соединения плохо дружат с gunicorn workers, поэтому лучше их закрывать."""
        if settings.IS_WEB:
            try:
                del broker.connection
            except Exception:
                pass
