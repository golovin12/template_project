from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from accounts.models import OrganizationUser
from .models import CityNotificationPreference


@receiver(m2m_changed, sender=OrganizationUser.cities.through)
def after_change_user_cities(sender, instance: OrganizationUser, action, **kwargs):
    """Отписка от недоступных пользователю уведомлений при изменении городов пользователя"""
    if action not in ('post_add', 'post_remove', 'post_clear'):
        return

    allowed_city_ids = instance.allowed_city_ids

    for city_settings in CityNotificationPreference.objects.filter(notification_settings__user=instance):
        if city_settings.city_id not in allowed_city_ids:
            city_settings.enabled = False
            city_settings.save(update_fields=['enabled'])
