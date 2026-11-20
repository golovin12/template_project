from django.db.models import Q
from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver

from apps.service_requests.models import Master
from .models import City, Branch, OrganizationUser


@receiver([post_save, post_delete], sender=Branch)
def after_change_branch(sender, instance: Branch, **kwargs):
    signal = kwargs.get('signal')

    if signal != post_delete and not instance.is_active:
        Master.branches.through.objects.filter(branch_id=instance.id).delete()

    users = OrganizationUser.objects.filter(
        Q(cities__branches=instance) | Q(all_cities_access=True) | Q(is_superuser=True)).distinct()

    for user in users.iterator():
        user.clear_cache()


@receiver(post_save, sender=City)
def after_change_city(sender, instance: City, **kwargs):
    if not instance.is_active:
        for branch in instance.branches.all():
            branch.is_active = False
            branch.save(update_fields=['is_active'])


@receiver(m2m_changed, sender=OrganizationUser.cities.through)
def clear_user_cache_after_cities_change(sender, instance: OrganizationUser, action, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    instance.clear_cache()
