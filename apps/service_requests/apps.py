from django.apps import AppConfig


class ServiceRequestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.service_requests'
    verbose_name = 'Заявки на ремонт'

    def ready(self):
        from . import signals  # noqa: F401
