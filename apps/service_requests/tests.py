from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City
from apps.bookkeeping.models import AccountingEntry
from apps.service_requests.controllers import RequestController
from apps.service_requests.models import DeviceType, ServiceRequest
from common_tools.test import BaseTestCase


class ServiceRequestTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Москва')
        self.branch = Branch.objects.create(name='Центральный', city=self.city)
        self.user = create_user_with_role(
            'chief',
            USER_ROLES.CHIEF,
            cities=[self.city],
        )
        self.client.force_login(self.user)

    def create_request(self, **kwargs):
        data = {
            'request_number': 100001,
            'request_type': ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
            'branch': self.branch,
            'client_name': 'Иван Иванов',
            'client_address': 'Москва',
            'problem_description': 'Не работает',
            'time_to_service': timezone.now(),
        }
        data.update(kwargs)
        return ServiceRequest.objects.create(**data)


class TestRequestController(ServiceRequestTestCase):

    def test_create_request_increments_number(self):
        self.create_request(request_number=100005)

        instance = ServiceRequest(
            request_type=ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
            branch=self.branch,
            client_name='Иван Иванов',
            client_address='Москва',
            problem_description='Не работает',
            time_to_service=timezone.now(),
        )

        with patch('apps.service_requests.signals.push_new_request_message.send'):
            result = RequestController.create_request(
                instance,
                self.user.organization_user,
            )

        self.assertEqual(result.request_number, 100006)
        self.assertEqual(result.created_by, self.user.organization_user)
        self.assertTrue(ServiceRequest.objects.filter(pk=result.pk).exists())

    def test_update_master_status(self):
        instance = self.create_request(status=ServiceRequest.STATUS.ASSIGNED)

        result = RequestController.update_master_status(
            instance,
            ServiceRequest.STATUS.ON_WAY,
        )

        self.assertTrue(result)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.ON_WAY)

    def test_update_master_status_rejects_invalid_transition(self):
        instance = self.create_request()

        result = RequestController.update_master_status(
            instance,
            ServiceRequest.STATUS.ON_WAY,
        )

        self.assertFalse(result)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.NEW)

    def test_complete_request(self):
        instance = self.create_request()

        result = RequestController.complete_request(instance)

        self.assertEqual(result.status, ServiceRequest.STATUS.COMPLETED)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.COMPLETED)

    def test_start_diagnostics(self):
        instance = self.create_request()

        result = RequestController.start_diagnostics(instance)

        self.assertEqual(result.status, ServiceRequest.STATUS.SERVICE_DIAGNOSTICS)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.SERVICE_DIAGNOSTICS)

    def test_cancel_request(self):
        instance = self.create_request()

        result = RequestController.cancel_request(instance)

        self.assertTrue(result)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.CANCELED)

    def test_cancel_request_rejects_completed_request(self):
        instance = self.create_request(status=ServiceRequest.STATUS.COMPLETED)

        result = RequestController.cancel_request(instance)

        self.assertFalse(result)
        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.COMPLETED)

    def test_cancel_request_rejects_canceled_request(self):
        instance = self.create_request(status=ServiceRequest.STATUS.CANCELED)

        result = RequestController.cancel_request(instance)

        self.assertFalse(result)

    def test_undo_closing(self):
        instance = self.create_request(
            status=ServiceRequest.STATUS.COMPLETED,
            closing_amount=Decimal('5000'),
            other_expenses=Decimal('1000'),
            closing_time=timezone.now(),
        )
        entry = AccountingEntry.objects.create(
            entry_type=AccountingEntry.ENTRY_TYPE.INCOME,
            amount=Decimal('4000'),
            description='Доход от заявки',
            branch=self.branch,
            service_request=instance,
        )

        result = RequestController.undo_closing(instance)

        self.assertEqual(result.status, ServiceRequest.STATUS.IN_PROGRESS)
        self.assertIsNone(result.closing_time)
        self.assertIsNone(result.closing_amount)
        self.assertFalse(AccountingEntry.objects.filter(pk=entry.pk).exists())


class TestServiceRequestForms(ServiceRequestTestCase):
    def setUp(self):
        super().setUp()
        self.device_type = DeviceType.objects.create(name='Холодильник')

    def test_create_form_rejects_unavailable_device_type(self):
        other_city = City.objects.create(name='Казань')
        other_branch = Branch.objects.create(name='Северный', city=other_city)
        unavailable_type = DeviceType.objects.create(
            name='Стиральная машина',
            is_available_for_all=False,
        )
        unavailable_type.branches.add(other_branch)

        response = self.client.post(
            reverse('service_request:request_create'),
            {
                'request_type': ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
                'branch': self.branch.pk,
                'client_name': 'Иван Иванов',
                'client_address': 'Москва',
                'problem_description': 'Не работает',
                'time_to_service': '2030-01-01 10:00',
                'device_type': unavailable_type.name,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ServiceRequest.objects.filter(
                client_name='Иван Иванов',
            ).exists()
        )
        self.assertIn('device_type', response.context['form'].errors)

    def test_update_form_rejects_changes_to_completed_request(self):
        instance = self.create_request(status=ServiceRequest.STATUS.COMPLETED)

        response = self.client.post(
            reverse('service_request:request_update', args=[instance.pk]),
            {
                'request_type': instance.request_type,
                'branch': self.branch.pk,
                'client_name': instance.client_name,
                'client_address': instance.client_address,
                'problem_description': instance.problem_description,
                'status': ServiceRequest.STATUS.COMPLETED,
                'time_to_service': '2030-01-01 10:00',
                'device_type': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.context['form'].errors)

    def test_complete_form_rejects_expenses_greater_than_income(self):
        instance = self.create_request()

        response = self.client.post(
            reverse('service_request:complete_request', args=[instance.pk]),
            {
                'closing_amount': '1000',
                'other_expenses': '2000',
                'service_report': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('other_expenses', response.context['closing_form'].errors)

        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.NEW)

    def test_diagnostic_form_rejects_closed_request(self):
        instance = self.create_request(status=ServiceRequest.STATUS.COMPLETED)

        response = self.client.post(
            reverse('service_request:diagnostic_request', args=[instance.pk]),
            {
                'service_report': 'Диагностика выполнена',
                'sd_closing_date': '2030-01-01',
            },
        )

        self.assertEqual(response.status_code, 200)

        instance.refresh_from_db()
        self.assertEqual(instance.status, ServiceRequest.STATUS.COMPLETED)

    def test_create_form_accepts_available_device_type(self):
        response = self.client.post(
            reverse('service_request:request_create'),
            {
                'request_type': ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
                'branch': self.branch.pk,
                'client_name': 'Иван Иванов',
                'client_address': 'Москва',
                'problem_description': 'Не работает',
                'time_to_service': '2030-01-01 10:00',
                'device_type': self.device_type.name,
            },
        )

        self.assertRedirects(
            response,
            reverse('service_request:request_list'),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            ServiceRequest.objects.filter(device_type=self.device_type.name).exists()
        )


class TestServiceRequestSignals(ServiceRequestTestCase):
    @patch('apps.service_requests.signals.push_new_request_message.send')
    def test_sends_notification_for_new_request(self, send):
        instance = self.create_request()

        send.assert_called_once_with(
            instance.get_data_to_vk(),
            self.city.pk,
        )

    @patch('apps.service_requests.signals.push_new_request_message.send')
    def test_does_not_send_notification_without_city(self, send):
        ServiceRequest.objects.create(
            request_number=100001,
            request_type=ServiceRequest.REQUEST_TYPE_CHOICES.FIRST_TIME,
            client_name='Иван Иванов',
            client_address='Москва',
            problem_description='Не работает',
            time_to_service=timezone.now(),
        )

        send.assert_not_called()

    def test_creates_income_when_request_is_completed(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.COMPLETED
        instance.closing_amount = Decimal('5000')
        instance.other_expenses = Decimal('1000')
        instance.save()

        entry = AccountingEntry.objects.get(service_request=instance)

        self.assertEqual(entry.entry_type, AccountingEntry.ENTRY_TYPE.INCOME)
        self.assertEqual(entry.amount, Decimal('4000'))
        self.assertEqual(entry.branch, self.branch)

    def test_creates_income_with_zero_expenses_when_not_specified(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.COMPLETED
        instance.closing_amount = Decimal('5000')
        instance.other_expenses = None
        instance.save()

        entry = AccountingEntry.objects.get(service_request=instance)

        self.assertEqual(entry.amount, Decimal('5000'))
        instance.refresh_from_db()
        self.assertEqual(instance.other_expenses, Decimal('0'))

    def test_does_not_create_income_for_zero_closing_amount(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.COMPLETED
        instance.closing_amount = Decimal('0')
        instance.other_expenses = Decimal('0')
        instance.save()

        self.assertFalse(
            AccountingEntry.objects.filter(service_request=instance).exists()
        )

    def test_sets_closing_time_for_canceled_request(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.CANCELED
        instance.save()

        instance.refresh_from_db()

        self.assertIsNotNone(instance.closing_time)

    def test_clears_closing_time_for_reopened_request(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.CANCELED
        instance.save()

        instance = ServiceRequest.objects.get(pk=instance.pk)
        instance.status = ServiceRequest.STATUS.IN_PROGRESS
        instance.save()

        instance.refresh_from_db()

        self.assertIsNone(instance.closing_time)


class TestServiceRequestMiddleware(ServiceRequestTestCase):
    def test_sets_user_for_accounting_entry_created_by_request(self):
        instance = self.create_request()
        instance = ServiceRequest.objects.get(pk=instance.pk)

        response = self.client.post(
            reverse('service_request:complete_request', args=[instance.pk]),
            {
                'closing_amount': '5000',
                'other_expenses': '1000',
                'service_report': 'Работа выполнена',
            },
        )

        self.assertEqual(response.status_code, 204)

        entry = AccountingEntry.objects.get(service_request=instance)

        self.assertEqual(entry.created_by, self.user.organization_user)


class TestDeviceTypeViews(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user_with_role('manager', USER_ROLES.MANAGER)
        self.client.force_login(self.user)

    def test_creates_device_type(self):
        response = self.client.post(
            reverse('service_request:device_type_create'),
            {
                'name': 'Холодильник',
                'is_available_for_all': True,
            },
        )

        self.assertRedirects(
            response,
            reverse('service_request:device_type_list'),
            fetch_redirect_response=False,
        )

        self.assertTrue(
            DeviceType.objects.filter(name='Холодильник').exists()
        )

    def test_deletes_device_type(self):
        device_type = DeviceType.objects.create(name='Холодильник')

        response = self.client.get(
            reverse('service_request:device_type_delete', args=[device_type.pk]),
            {'delete': 'true'},
        )

        self.assertRedirects(
            response,
            reverse('service_request:device_type_list'),
            fetch_redirect_response=False,
        )

        self.assertFalse(
            DeviceType.objects.filter(pk=device_type.pk).exists()
        )
