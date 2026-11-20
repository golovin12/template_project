from django.apps import AppConfig


class PromoterAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'promoter_app'
    verbose_name = 'ПромоТрек'

    def ready(self):
        from . import signals  # noqa: F401
