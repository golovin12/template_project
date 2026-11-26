from django.apps import AppConfig
from django.contrib import admin


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Пользователи'

    def ready(self):
        from . import signals  # noqa: F401
        from .base import MyAdminSite
        admin.site.__class__ = MyAdminSite
