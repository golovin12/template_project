from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City
from common_tools.test import BaseTestCase
from .controllers import RequestController
from .models import Master, ServiceRequest


class ServiceRequestViewsTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.city = City.objects.create(name='Moscow')
        cls.city2 = City.objects.create(name='NoMoscow')
        cls.branch = Branch.objects.create(name='Main Branch', city=cls.city)
        cls.manager = create_user_with_role(username='manager', role=USER_ROLES.MANAGER)
        cls.master_user = create_user_with_role(
            username='master',
            role=USER_ROLES.MASTER,
            first_name='John',
            last_name='LastName',
            current_city=cls.city,
            cities=[cls.city]
        )
        cls.request = ServiceRequest.objects.create(
            request_number=1,
            request_type='first_time',
            branch=cls.branch,
            status='new',
            time_to_service=timezone.now(),
        )
        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)

    def test_request_list_view(self):
        response = self.client.get(reverse('service_request:request_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'service_request/request_list.html')
        self.client.force_login(self.master_user)
        response = self.client.get(reverse('service_request:request_list'))
        self.assertEqual(response.status_code, 403)

    def test_request_manager_create_view(self):
        response = self.client.post(reverse('service_request:request_create'), {
            'request_type': 'first_time',
            'status': 'new',
            'client_name': 'name',
            'problem_description': 'problem...',
            'client_address': 'New address',
            'client_phone': '+79999999999',
            'branch': self.branch.id,
            'time_to_service': timezone.now(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceRequest.objects.count(), 2)

    def test_request_chief_create_view(self):
        other_branch = Branch.objects.create(name='Other Branch', city=self.city2)
        chief = create_user_with_role(
            username='chief',
            role=USER_ROLES.CHIEF,
            cities=[other_branch.city]
        )
        self.client.force_login(chief)
        response = self.client.post(reverse('service_request:request_create'), {
            'request_type': 'first_time',
            'client_name': 'name',
            'problem_description': 'problem...',
            'client_address': 'New address',
            'client_phone': '89999999999',
            'branch': other_branch.id,
            'time_to_service': timezone.now(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceRequest.objects.count(), 2)

        # Попытка передать другой филиал - филиал должен остаться, который привязан к пользователю
        response = self.client.post(reverse('service_request:request_create'), {
            'request_type': 'first_time',
            'client_name': 'name2',
            'problem_description': 'problem...',
            'client_address': 'New address',
            'client_phone': '79999999999',
            'branch': self.branch.id,
            'time_to_service': timezone.now(),
        })
        self.assertFormError(response.context[0]['form'], 'branch',
                             f'Выберите корректный вариант. {self.branch.id} нет среди допустимых значений.')


class ServiceRequestUpdateViewTestCase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city = City.objects.create(name='Moscow')
        cls.branch = Branch.objects.create(name='Main Branch', city=cls.city)
        cls.branch2 = Branch.objects.create(name='Two Branch', city=cls.city)
        cls.manager = create_user_with_role(
            username='manager',
            role=USER_ROLES.MANAGER,
        )
        cls.chief = create_user_with_role(
            username='chief',
            role=USER_ROLES.CHIEF,
            current_city=cls.city,
            cities=[cls.city]
        )
        cls.master_user = create_user_with_role(
            username='master',
            role=USER_ROLES.MASTER,
            first_name='John',
            last_name='LastName',
            current_city=cls.city,
            cities=[cls.city]
        )
        master = Master.objects.create(
            full_name='LastName John',
            hire_date='2023-01-01',
            associated_user=cls.master_user.zone_user
        )
        master.branches.set([cls.branch])
        cls.master2 = Master.objects.create(
            full_name='Master 3',
            hire_date='2023-01-01',
        )
        cls.master2.branches.set([cls.branch2])
        cls.request = ServiceRequest.objects.create(
            request_number=1,
            request_type='first_time',
            branch=cls.branch,
            status='new',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            problem_description='Updated problem description',
        )
        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.url = reverse('service_request:request_update', kwargs={'pk': self.request.pk})
        self.client.force_login(self.manager)
        self.fields_data = {field.name: (getattr(self.request, field.name) or '')
                            for field in self.request._meta.fields}
        self.fields_data['branch'] = str(self.fields_data['branch'].id)

    def test_access_permissions(self):
        """Тестирование прав доступа к представлению"""
        # Анонимный пользователь
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Редирект на логин

        # Обычный пользователь без прав
        self.client.force_login(self.master_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)  # Forbidden

        # Директор
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_basic_update_functionality(self):
        """Тест базового функционала обновления"""
        updated_data = {
            'request_type': 'repeat',
            'client_name': 'name client',
            'client_address': 'Updated address',
            'branch': self.branch.id,
            'client_phone': '+79998887766',
            'status': 'assigned',
            'assigned_master': self.master_user.zone_user.master.id,
            'problem_description': 'Updated problem description',
            'time_to_service': timezone.now(),
        }

        response = self.client.post(self.url, updated_data)

        # Проверяем редирект
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('service_request:request_detail', kwargs={'pk': self.request.pk}))

        # Проверяем обновленные данные
        self.request.refresh_from_db()
        self.assertEqual(self.request.client_address, 'Updated address')
        self.assertEqual(self.request.assigned_master, self.master_user.zone_user.master)
        self.assertEqual(self.request.status, 'assigned')
        self.assertEqual(self.request.problem_description, 'Updated problem description')

    def test_status_transition_workflow(self):
        """Тест автоматических переходов статусов"""
        # Назначение мастера должно менять статус на assigned
        response = self.client.post(self.url, {
            'assigned_master': self.master_user.zone_user.master.id,
            **{name: value for name, value in self.fields_data.items() if name not in ['assigned_master']}
        })
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'assigned')

    def test_status_transition_bad_workflow(self):
        self.client.force_login(self.chief)
        # Попытка назначить мастера из другого филиала
        response = self.client.post(self.url, {
            'assigned_master': self.master2.id,
            **{name: value for name, value in self.fields_data.items() if name not in ['assigned_master']}
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'assigned_master',
                             'Мастер должен принадлежать филиалу обслуживания!')
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'new')
        # Назначение мастера
        response = self.client.post(self.url, {
            'assigned_master': self.master_user.zone_user.master.id,
            **{name: value for name, value in self.fields_data.items() if name not in ['assigned_master']}
        })
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'assigned')

    def test_validation_errors(self):
        """Тест валидации данных формы"""
        # Невалидный мастер
        self.client.force_login(self.chief)
        response = self.client.post(self.url, {
            'assigned_master': self.master2.id,
            **{name: value for name, value in self.fields_data.items() if name not in ['assigned_master']}
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'assigned_master',
                             'Мастер должен принадлежать филиалу обслуживания!')

        # Невалидный статус
        response = self.client.post(self.url, {
            'status': '',
            **{name: value for name, value in self.fields_data.items() if name not in ['status']}
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'status', 'Это поле обязательно для заполнения.')

    def test_completion_requirements(self):
        """Тест обязательных полей при завершении заявки"""
        # Попытка завершить без суммы

        response = self.client.post(self.url, {
            'status': 'completed',
            'assigned_master': self.master_user.zone_user.master.id,
            **{name: value for name, value in self.fields_data.items() if name not in ['status', 'assigned_master']}
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'closing_amount',
                             'Для закрытия заявки необходимо указать сумму закрытия!')
        self.assertFormError(response.context[0]['form'], 'other_expenses',
                             'Для закрытия заявки необходимо указать расходы!')

        # Попытка завершить с отрицательной суммой
        response = self.client.post(self.url, {
            'status': 'completed',
            'closing_amount': '-100',
            'assigned_master': self.master_user.zone_user.master.id,
            **{name: value for name, value in self.fields_data.items()
               if name not in ['status', 'closing_amount', 'assigned_master']}
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'closing_amount',
                             ['Убедитесь, что это значение больше либо равно 0.',
                              'Для закрытия заявки необходимо указать сумму закрытия!'])

        # Завершение заявки
        response = self.client.post(self.url, {
            'status': 'completed',
            'closing_amount': '100',
            'other_expenses': '0',
            'assigned_master': self.master_user.zone_user.master.id,
            **{name: value for name, value in self.fields_data.items()
               if name not in ['status', 'closing_amount', 'other_expenses', 'assigned_master']}
        })
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, 'completed')

        # Попытка внести изменения в закрытую заявку
        response = self.client.post(self.url, {
            'status': 'canceled',
            **{name: value for name, value in self.fields_data.items() if name not in ['status']}
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'], 'status', 'Нельзя внести изменения в уже закрытую заявку!')


class MasterProgressViewTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city = City.objects.create(name='Moscow')
        cls.city2 = City.objects.create(name='NoMoscow')
        cls.branch = Branch.objects.create(name='Main Branch', city=cls.city)
        cls.branch2 = Branch.objects.create(name='Two Branch', city=cls.city2)
        cls.manager = create_user_with_role(
            username='manager',
            role=USER_ROLES.MANAGER,
        )
        cls.chief = create_user_with_role(
            username='chief',
            role=USER_ROLES.CHIEF,
            current_city=cls.city,
            cities=[cls.city]
        )
        cls.master_user = create_user_with_role(
            username='master',
            role=USER_ROLES.MASTER,
            first_name='John',
            last_name='LastName',
            cities=[cls.city]
            # current_city=cls.branch.city  # Должно работать без неё
        )
        master = Master.objects.create(
            full_name='LastName John',
            hire_date='2023-01-01',
            associated_user=cls.master_user.zone_user
        )
        master.branches.add(cls.branch)
        cls.master2 = Master.objects.create(
            full_name='Master 3',
            hire_date='2023-01-01',
        )
        cls.master2.branches.add(cls.branch2)
        cls.master3 = Master.objects.create(
            full_name='Master 4',
            hire_date='2023-01-01',
            deposit_disabled=True,
        )
        cls.master3.branches.add(cls.branch)
        cls.master3.branches.add(cls.branch2)
        cls.new_request = ServiceRequest.objects.create(
            request_number=1,
            request_type='first_time',
            branch=cls.branch,
            status='new',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            problem_description='Updated problem description',
        )

        cls.assigned_request = ServiceRequest.objects.create(
            request_number=2,
            request_type='first_time',
            branch=cls.branch2,
            status='assigned',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            assigned_master=cls.master_user.zone_user.master,
            problem_description='Updated problem description',
        )

        cls.on_way_request = ServiceRequest.objects.create(
            request_number=3,
            request_type='first_time',
            branch=cls.branch,
            status='on_way',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            assigned_master=cls.master_user.zone_user.master,
            problem_description='Updated problem description',
        )

        cls.in_progress_request = ServiceRequest.objects.create(
            request_number=4,
            request_type='first_time',
            branch=cls.branch,
            status='in_progress',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            assigned_master=cls.master_user.zone_user.master,
            problem_description='Updated problem description',
        )
        cls.in_progress_request2 = ServiceRequest.objects.create(
            request_number=5,
            request_type='first_time',
            branch=cls.branch,
            status='in_progress',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            assigned_master=cls.master3,
            problem_description='Updated problem description',
        )

        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.client.force_login(self.chief)

    def test_assigned_master(self):
        """Тест назначения мастера"""
        response = self.client.post(
            reverse('service_request:assign_master', args=[self.new_request.pk]),
            {'new_master_id': self.master_user.zone_user.master.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.new_request.refresh_from_db()
        self.assertEqual(self.new_request.assigned_master, self.master_user.zone_user.master)

    def test_fail_assigned_master(self):
        """Тест попытки назначения мастера из другого филиала"""
        response = self.client.post(
            reverse('service_request:assign_master', args=[self.new_request.pk]),
            {'new_master_id': self.master2.pk}
        )
        self.assertEqual(response.status_code, 302)
        self.new_request.refresh_from_db()
        self.assertEqual(self.new_request.assigned_master, None)

    def test_access_denied_for_other_masters(self):
        """Тест запрета доступа изменения статуса других заявок"""
        response = self.client.post(
            reverse('service_request:update_master_status', args=[self.assigned_request.pk]),
            {'new_status': ServiceRequest.STATUS.ON_WAY}
        )
        self.assertEqual(response.status_code, 404)  # Not Found

    def test_status_update_from_assigned_to_on_way(self):
        """Тест обновления статуса с 'assigned' на 'on_way'"""
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse('service_request:update_master_status', args=[self.assigned_request.pk]),
            {'new_status': 'on_way'}
        )

        self.assertEqual(response.status_code, 302)
        self.assigned_request.refresh_from_db()
        self.assertEqual(self.assigned_request.status, 'on_way')

    def test_status_update_from_on_way_to_in_progress(self):
        """Тест обновления статуса с 'on_way' на 'in_progress'"""
        response = self.client.post(
            reverse('service_request:update_master_status', args=[self.on_way_request.pk]),
            {'new_status': 'in_progress'}
        )

        self.assertEqual(response.status_code, 302)
        self.on_way_request.refresh_from_db()
        self.assertEqual(self.on_way_request.status, 'in_progress')

    def test_invalid_status_transition(self):
        """Тест недопустимого перехода статусов"""
        response = self.client.post(
            reverse('service_request:update_master_status', args=[self.on_way_request.pk]),
            {'new_status': 'completed'}
        )

        self.assertEqual(response.status_code, 302)
        self.on_way_request.refresh_from_db()
        self.assertNotEqual(self.on_way_request.status, 'completed')

    def test_cancel_request(self):
        """Тест отмены заявки"""
        response = self.client.post(
            reverse('service_request:cancel_request', args=[self.in_progress_request.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.in_progress_request.refresh_from_db()
        self.assertEqual(self.in_progress_request.status, 'canceled')

    def test_completing_request_with_details(self):
        """Тест завершения заявки с деталями"""
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.in_progress_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '0',
                'closing_amount': '1500.00',
            },
        )

        self.assertEqual(response.status_code, 204)
        self.in_progress_request.refresh_from_db()
        self.assertEqual(self.in_progress_request.status, 'completed')
        self.assertEqual(self.in_progress_request.closing_amount, 1500)

    def test_completing_request_with_details2(self):
        """Тест завершения заявки с деталями"""
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.in_progress_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '500.00',
                'closing_amount': '2000.00',
            },
        )

        self.assertEqual(response.status_code, 204)
        self.in_progress_request.refresh_from_db()
        self.assertEqual(self.in_progress_request.status, 'completed')
        self.assertEqual(self.in_progress_request.closing_amount, 2000)
        self.assertEqual(self.in_progress_request.masterincome.closing_amount, 1500)
        self.assertEqual(self.in_progress_request.masterincome.profit, 600)

    def test_completing_request_with_deposit(self):
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.in_progress_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '0',
                'closing_amount': '1500.00',
                'deposit_to_master': '300',
            },
        )
        self.assertEqual(response.status_code, 204)
        self.in_progress_request.refresh_from_db()
        self.assertEqual(self.in_progress_request.masterincome.deposit, 300)

    def test_completing_request_without_deposit(self):
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.in_progress_request2.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '0',
                'closing_amount': '1500.00',
                'deposit_to_master': '300',
            },
        )
        self.assertEqual(response.status_code, 204)
        self.in_progress_request2.refresh_from_db()
        self.assertEqual(self.in_progress_request2.masterincome.deposit, 0)

    def test_completing_request_with_deposit2(self):
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.in_progress_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '1600',
                'closing_amount': '1500.00',
                'deposit_to_master': '300',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.in_progress_request.refresh_from_db()
        self.assertFormError(response.context[0]['closing_form'], 'deposit_to_master',
                             'Отчисления в депозит не могут превышать 0.5% от дохода')

    def test_error_completing_request(self):
        """Невалидные попытки завершения заявки"""
        # Передача отрицательных значений
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.on_way_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '-100',
                'closing_amount': '-1500.00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.on_way_request.refresh_from_db()
        self.assertEqual(self.on_way_request.status, 'on_way')
        self.assertFormError(response.context[0]['closing_form'], 'closing_amount',
                             'Убедитесь, что это значение больше либо равно 0.')
        self.assertFormError(response.context[0]['closing_form'], 'other_expenses',
                             'Убедитесь, что это значение больше либо равно 0.')
        # Превышение депозита мастера
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.on_way_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '100',
                'closing_amount': '1500.00',
                'deposit_to_master': '1600.00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.on_way_request.refresh_from_db()
        self.assertEqual(self.on_way_request.status, 'on_way')
        self.assertFormError(response.context[0]['closing_form'], 'deposit_to_master',
                             'Отчисления в депозит не могут превышать 0.5% от дохода')
        # Отрицательный депозит мастера
        response = self.client.post(
            reverse('service_request:complete_request', args=[self.on_way_request.pk]),
            {
                'service_report': 'Замена детали',
                'other_expenses': '100',
                'closing_amount': '1500.00',
                'deposit_to_master': '-100.00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.on_way_request.refresh_from_db()
        self.assertEqual(self.on_way_request.status, 'on_way')
        self.assertFormError(response.context[0]['closing_form'], 'deposit_to_master',
                             'Убедитесь, что это значение больше либо равно 0.')


class MasterListViewTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city1 = City.objects.create(name='Moscow')
        cls.city2 = City.objects.create(name='St. Petersburg')
        cls.branch1 = Branch.objects.create(name='Branch 1', city=cls.city1)
        cls.branch2 = Branch.objects.create(name='Branch 2', city=cls.city2)

        cls.manager = create_user_with_role(
            username='manager',
            role=USER_ROLES.MANAGER,
        )

        cls.chief = create_user_with_role(
            username='chief',
            role=USER_ROLES.CHIEF,
            current_city=cls.city1,
            cities=[cls.city1]
        )

        cls.master1_user = create_user_with_role(
            username='master',
            role=USER_ROLES.MASTER,
            first_name='1',
            last_name='Master',
            current_city=cls.city1,
            cities=[cls.city1]
        )
        # Создаем мастеров с выполненными заявками
        cls.master1 = Master.objects.create(
            full_name='Master 1',
            hire_date='2023-02-01',
            associated_user=cls.master1_user.zone_user
        )
        cls.master1.branches.add(cls.branch1)
        cls.master2 = Master.objects.create(
            full_name='Master 2',
            hire_date='2023-02-01',
        )
        cls.master2.branches.add(cls.branch2)

        # Создаем завершенные заявки для мастеров
        for i in range(1, 4):
            ServiceRequest.objects.create(
                request_number=i,
                request_type='first_time',
                branch=cls.branch1,
                status='completed',
                time_to_service=timezone.now(),
                client_name='name client',
                client_address='Updated address',
                client_phone='+79998887766',
                problem_description='Updated problem description',
                closing_amount=1000 * i,
                assigned_master=cls.master1,
            )
            cls.master1.refresh_from_db()

        for i in range(1, 3):
            ServiceRequest.objects.create(
                request_number=i + 3,
                request_type='first_time',
                branch=cls.branch2,
                status='completed',
                time_to_service=timezone.now(),
                client_name='name client',
                client_address='Updated address',
                client_phone='+79998887766',
                problem_description='Updated problem description',
                closing_amount=2000 * i,
                assigned_master=cls.master2,
            )
            cls.master2.refresh_from_db()

        # Создаем незавершенную заявку (не должна учитываться)
        ServiceRequest.objects.create(
            request_number=6,
            request_type='first_time',
            branch=cls.branch1,
            status='assigned',
            time_to_service=timezone.now(),
            client_name='name client',
            client_address='Updated address',
            client_phone='+79998887766',
            problem_description='Updated problem description',
            assigned_master=cls.master1,
        )

        cls.salary_url = reverse('service_request:masters')
        cls.dashboard_url = reverse('service_request:master_dashboard')
        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.client.force_login(self.chief)

    def test_view_url_exists(self):
        """Тест доступности URL"""
        self.assertEqual(self.client.get(self.salary_url).status_code, 200)
        self.assertEqual(self.client.get(self.dashboard_url).status_code, 403)
        self.client.force_login(self.master1_user)
        self.assertEqual(self.client.get(self.salary_url).status_code, 403)
        self.assertEqual(self.client.get(self.dashboard_url).status_code, 200)

    def test_view_master_statistics_calculation(self):
        """Тест корректности расчетов статистики по мастерам"""
        response = self.client.get(self.salary_url)
        context = response.context[0]
        masters = context['object_list']
        self.assertEqual(len(masters), 1)

        self.client.force_login(self.manager)
        response = self.client.get(self.salary_url)
        context = response.context[0]
        masters = context['object_list']
        self.assertEqual(len(masters), 2)

    def test_master_dashboard_view(self):
        """Тест отображения заявок мастера"""
        self.client.force_login(self.master1_user)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(len(response.context[0]['object_list']), 4)


class MasterCreateViewTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city = City.objects.create(name='Moscow')
        cls.branch = Branch.objects.create(name='Branch 1', city=cls.city)

        cls.manager = create_user_with_role(
            username='manager',
            role=USER_ROLES.MANAGER,
        )

        cls.chief = create_user_with_role(
            username='chief',
            role=USER_ROLES.CHIEF,
            current_city=cls.city,
            cities=[cls.city]
        )

        cls.url = reverse('service_request:masters_create')

    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)

    def test_valid_master_create_manager(self):
        """Тест создания мастера"""
        response = self.client.post(self.url, {
            'full_name': 'Мастер Работник Сочи',
            'hire_date': '17.07.2025',
            'branches': [self.branch.id],
            'deposit_disabled': 'on',
            # Настройки формсета для процентов мастера
            'percentages-TOTAL_FORMS': ['3'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
            # Процент мастера 1
            'percentages-0-min_income': ['0'],
            'percentages-0-max_income': ['20000'],
            'percentages-0-percentage': ['50'],
            'percentages-0-id': [''],
            # Процент мастера 2
            'percentages-1-min_income': ['20000'],
            'percentages-1-max_income': ['30000'],
            'percentages-1-percentage': ['60'],
            'percentages-1-id': [''],
            # Процент мастера 3
            'percentages-2-min_income': ['30000'],
            'percentages-2-max_income': [''],
            'percentages-2-percentage': ['70'],
            'percentages-2-id': ['']
        })
        self.assertEqual(response.status_code, 302)  # Проверяем редирект после успешного создания
        self.assertEqual(Master.active_objects.count(), 1)
        master = Master.objects.first()
        self.assertEqual(master.percentages.count(), 3)
        self.assertEqual(master.deposit_disabled, True)
        self.assertRedirects(response, reverse('service_request:masters'))

        response = self.client.post(self.url, {
            'full_name': 'Мастер Работник Два',
            'hire_date': '17.08.2025',
            'branches': [self.branch.id],
            # Настройки формсета для процентов мастера
            'percentages-TOTAL_FORMS': ['0'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
        })

        self.assertEqual(response.status_code, 302)  # Проверяем редирект после успешного создания
        self.assertEqual(Master.active_objects.count(), 2)
        master = Master.objects.last()
        self.assertEqual(master.percentages.count(), 0)
        self.assertEqual(master.deposit_disabled, False)

    def test_invalid_master_create_manager(self):
        """Тест создания мастера"""
        response = self.client.post(self.url, {
            'full_name': 'Мастер Работник Сочи',
            'hire_date': '17.07.2025',
            'branches': [self.branch.id],
            # Настройки формсета для процентов мастера
            'percentages-TOTAL_FORMS': ['1'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
            # Процент мастера
            'percentages-0-min_income': ['-100'],
            'percentages-0-max_income': ['20000'],
            'percentages-0-percentage': ['0'],
            'percentages-0-id': [''],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Master.active_objects.count(), 0)
        self.assertFormError(response.context[0]['form'].formset[0], 'min_income',
                             'Убедитесь, что это значение больше либо равно 0.')
        self.assertFormError(response.context[0]['form'].formset[0], 'percentage',
                             'Убедитесь, что это значение больше либо равно 10.')

        response = self.client.post(self.url, {
            'full_name': 'Мастер Работник Сочи',
            'hire_date': '17.08.2025',
            'branches': [self.branch.id],
            # Настройки формсета для процентов мастера
            'percentages-TOTAL_FORMS': ['1'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
            # Процент мастера
            'percentages-0-min_income': ['30000'],
            'percentages-0-max_income': ['20000'],
            'percentages-0-percentage': ['120'],
            'percentages-0-id': [''],
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context[0]['form'].formset[0], 'min_income',
                             'Минимальный доход должен быть меньше максимального')
        self.assertFormError(response.context[0]['form'].formset[0], 'percentage',
                             'Убедитесь, что это значение меньше либо равно 99.')

    def test_valid_master_create_chief(self):
        """Тест создания мастера директором - не создаём проценты и не меняем статус депозита"""
        self.client.force_login(self.chief)
        response = self.client.post(self.url, {
            'full_name': 'Мастер Работник Сочи',
            'hire_date': '17.07.2025',
            'deposit_disabled': 'on',
            'branches': [self.branch.id],
            # Настройки формсета для процентов мастера
            'percentages-TOTAL_FORMS': ['1'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
            # Процент мастера 1
            'percentages-0-min_income': ['0'],
            'percentages-0-max_income': ['20000'],
            'percentages-0-percentage': ['50'],
            'percentages-0-id': [''],
        })

        self.assertEqual(response.status_code, 302)  # Проверяем редирект после успешного создания
        self.assertEqual(Master.active_objects.count(), 1)
        master = Master.objects.last()
        self.assertEqual(master.percentages.count(), 0)
        self.assertEqual(master.deposit_disabled, False)
        self.assertRedirects(response, reverse('service_request:masters'))

    def test_master_calculate_percent(self):
        """Тест расчёта процента мастера при включенном и выключенном депозите"""
        self.client.post(self.url, {
            'full_name': 'Мастер Работник Сочи',
            'hire_date': '17.07.2025',
            'branches': [self.branch.id],
            'deposit_disabled': 'on',
            'percentages-TOTAL_FORMS': ['0'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
        })
        master = Master.objects.first()
        svc_req = ServiceRequest(assigned_master=master, closing_amount=1500, other_expenses=500, request_number=1000,
                                 time_to_service=timezone.now())
        svc_req.save()
        RequestController.create_master_profit(svc_req)
        self.assertEqual(master.masterincome_set.first().profit, 500)
        self.assertEqual(master.masterincome_set.first().deposit, 0)
        self.assertEqual(master.masterincome_set.first().closing_amount, 1000)

        self.client.post(self.url, {
            'full_name': 'Мастер Работник СочиДва',
            'hire_date': '17.07.2025',
            'branches': [self.branch.id],
            'percentages-TOTAL_FORMS': ['0'],
            'percentages-INITIAL_FORMS': ['0'],
            'percentages-MIN_NUM_FORMS': ['0'],
            'percentages-MAX_NUM_FORMS': ['1000'],
        })
        master2 = Master.objects.last()
        svc_req2 = ServiceRequest(assigned_master=master2, closing_amount=1500, other_expenses=500, request_number=1001,
                                  time_to_service=timezone.now())
        svc_req2.save()
        RequestController.create_master_profit(svc_req2)
        self.assertEqual(master2.masterincome_set.first().profit, 400)
        self.assertEqual(master2.masterincome_set.first().deposit, 100)
        self.assertEqual(master2.masterincome_set.first().closing_amount, 1000)
