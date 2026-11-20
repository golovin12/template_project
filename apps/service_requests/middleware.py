from accounts.base import OrganizationRequest

try:
    from asgiref.local import Local as LocalContext
except ImportError:
    from threading import local as LocalContext

from django.utils.deprecation import MiddlewareMixin


class LoggedInUserMiddleware(MiddlewareMixin):
    """
    Хранит информацию о юзере для сохранения в историю изменений с помощью сигналов Django

    Пример реализации взят из библиотеки https://github.com/jazzband/django-simple-history

    This middleware sets request.user as a local context/thread variable, making it
    available to the model-level utilities to allow tracking of the authenticated user
    making a change.
    """
    context = LocalContext()

    def process_request(self, request: OrganizationRequest):
        if request.path.startswith('/requests/') and request.user.is_authenticated:
            # Запоминает юзера, выполнившего запрос для приложения service_requests
            LoggedInUserMiddleware.context.user = request.user.organization_user

    def process_response(self, request: OrganizationRequest, response):
        self._clear_context(request)
        return response

    def process_exception(self, request: OrganizationRequest, exception):
        self._clear_context(request)
        return None

    def _clear_context(self, request: OrganizationRequest):
        if request.path.startswith('/requests/'):
            if hasattr(LoggedInUserMiddleware.context, 'user'):
                del LoggedInUserMiddleware.context.user
