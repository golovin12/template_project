from django.apps import AppConfig


class BookkeepingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.bookkeeping'
    verbose_name = 'Бухгалтерия'

    def ready(self):
        from . import signals  # noqa: F401
