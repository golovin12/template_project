from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models import OrganizationUser
from apps.bookkeeping.models import AccountingEntry
from apps.notifications.tasks import push_new_request_message
from .middleware import LoggedInUserMiddleware
from .models import ServiceRequest


def get_logged_in_user():
    return getattr(LoggedInUserMiddleware.context, 'user', None)


def create_income_on_request_close(instance: ServiceRequest, user: Optional[OrganizationUser]):
    """Создаём запись о чистой прибыли"""
    clean_income = instance.closing_amount - instance.other_expenses
    AccountingEntry.objects.create(
        entry_type=AccountingEntry.ENTRY_TYPE.INCOME,
        amount=clean_income,
        description=f'Доход от заявки #{instance.request_number}',
        branch=instance.branch,
        service_request=instance,
        created_by=user,
    )


@receiver(post_save, sender=ServiceRequest)
def after_change_service_request(sender, instance: ServiceRequest, created: bool = False, **kwargs):
    if getattr(instance, '_signal_handled', False):
        return
    instance._signal_handled = True

    if created and instance.city_id:
        try:
            push_new_request_message.send(instance.get_data_to_vk(), instance.city_id)
        except Exception:
            pass

    elif instance.status == ServiceRequest.STATUS.CANCELED and instance.closing_time is None:
        ServiceRequest.objects.filter(pk=instance.pk).update(closing_time=timezone.now())

    elif not instance.is_status_completed and instance.closing_time:
        ServiceRequest.objects.filter(pk=instance.pk).update(closing_time=None)

    elif instance.is_status_completed and instance.closing_amount is not None:
        if instance.closing_time is None:
            with transaction.atomic():
                if instance.other_expenses is None:
                    instance.other_expenses = Decimal(0)

                if instance.closing_amount:
                    user = get_logged_in_user()

                    create_income_on_request_close(instance, user)

                ServiceRequest.objects.filter(pk=instance.pk).update(
                    other_expenses=instance.other_expenses,
                    closing_time=timezone.now()
                )
