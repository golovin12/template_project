from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect
from django.utils import timezone


class AntiBruteForceMiddleware:
    """Защита от перебора паролей"""

    MAX_ATTEMPTS = 5
    BLOCK_TIME = 5 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def get_client_ip(request):
        return request.META.get('HTTP_X_REAL_IP', request.META.get('REMOTE_ADDR', 'unknown'))

    def __call__(self, request):
        if request.path == '/identity/login/' and request.method == 'POST':
            ip = self.get_client_ip(request)
            username = request.POST.get('username', '').strip().lower()

            key = f'login_attempts:{ip}:{username}'
            request.login_attempts_cache_key = key

            if cache.get(key, 0) >= self.MAX_ATTEMPTS:
                messages.error(request, 'Превышено число неудачных попыток входа. Попробуйте через 5 минут.')
                return redirect('identity:login')

        return self.get_response(request)


class SlidingSessionMiddleware:
    """Middleware для продления срока действия сессии, при активности пользователя."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.update_interval = getattr(settings, 'SESSION_UPDATE_INTERVAL_HOURS', 1)

    def __call__(self, request):
        response = self.get_response(request)

        if request.user.is_authenticated:
            now = timezone.now()
            last_activity = request.session.get('last_activity')

            if not last_activity or (
                    (now - timezone.datetime.fromisoformat(last_activity)) > timedelta(hours=self.update_interval)):
                request.session['last_activity'] = now.isoformat()
                request.session.modified = True

        return response
