from accounts.models import OrganizationUser
from apps.bookkeeping.models import AccountingEntry
from .models import ServiceRequest


class RequestController:
    """Работа с заявками."""

    @staticmethod
    def create_request(instance: ServiceRequest, user: OrganizationUser, commit=True):
        """Создаёт заявку, назначая автора и порядковый номер."""
        instance.created_by = user
        last_request = ServiceRequest.objects.order_by('-request_number').first()
        instance.request_number = last_request.request_number + 1 if last_request else 100001

        if commit:
            instance.save()

        return instance

    @staticmethod
    def update_master_status(instance: ServiceRequest, new_status: str) -> bool:
        """Изменяет статус заявки на допустимый статус мастера."""
        statuses = ServiceRequest.STATUS

        if (new_status in (statuses.ON_WAY, statuses.IN_PROGRESS)
                and instance.status in (statuses.ASSIGNED, statuses.ON_WAY)):
            instance.status = new_status
            instance.save(update_fields=['status'])
            return True

        return False

    @staticmethod
    def complete_request(instance: ServiceRequest, commit=True):
        """Завершает заявку."""
        instance.status = ServiceRequest.STATUS.COMPLETED

        if commit:
            instance.save()

        return instance

    @staticmethod
    def start_diagnostics(instance: ServiceRequest, commit=True):
        """Переводит заявку в статус сервисной диагностики."""
        instance.status = ServiceRequest.STATUS.SERVICE_DIAGNOSTICS

        if commit:
            instance.save()

        return instance

    @staticmethod
    def cancel_request(instance: ServiceRequest) -> bool:
        """Отменяет заявку, если она ещё не завершена или отменена."""
        if instance.is_status_end:
            return False

        instance.status = ServiceRequest.STATUS.CANCELED
        instance.save(update_fields=['status'])
        return True

    @staticmethod
    def undo_closing(instance: ServiceRequest) -> ServiceRequest:
        """Отмена закрытия заявки, с удалением записи в бухгалтерии"""
        instance.status = ServiceRequest.STATUS.IN_PROGRESS
        instance.closing_time = None
        instance.closing_amount = None
        AccountingEntry.objects.filter(service_request=instance).delete()
        instance.save()
        return instance
