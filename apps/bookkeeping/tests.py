from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City
from apps.service_requests.models import Master, ServiceRequest
from common_tools.test import BaseTestCase
from .models import AccountingEntry


class AccountingRecordListViewTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        city = City.objects.create(name='Moscow')
        cls.branch = Branch.objects.create(name='Main Branch', city=city)
        cls.manager = create_user_with_role(
            username='main_manager',
            role=USER_ROLES.MANAGER,
        )

        cls.master = Master.objects.create(
            full_name='Test Master',
            hire_date='2023-01-01',
        )
        cls.master.branches.add(cls.branch)
        # Создаем тестовые заявки и бухгалтерские записи
        for i in range(1, 6):
            ServiceRequest.objects.create(
                request_number=i,
                status='completed',
                closing_amount=1000 * i,
                branch=cls.branch,
                assigned_master=cls.master,
                time_to_service=timezone.now()
            )
            # Записи о доходах компании и зп мастеру создаются автоматически при закрытии заявки
            cls.master.refresh_from_db()

        # Создаем несколько расходов
        AccountingEntry.objects.create(
            entry_type='expense',
            amount=500,
            description='Office supplies',
            branch=cls.branch
        )

        cls.url = reverse('bookkeeping:entry_list')
        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)

    def test_list_accounting_record_unauthorized(self):
        """Тест доступа для неавторизованных пользователей"""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Должен перенаправить на login
        self.assertRedirects(response, f'/auth_zone/login/?next={self.url}')

    def test_view_url_exists(self):
        """Тест доступности URL"""
        valid_roles = (USER_ROLES.MANAGER, USER_ROLES.ACCOUNTANT, USER_ROLES.CHIEF)
        for role in USER_ROLES.choices:
            user = create_user_with_role(username=role[0], role=role[0], current_city=self.branch.city,
                                         cities=[self.branch.city])
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200 if user.zone_user.role in valid_roles else 403)

    def test_view_shows_all_records(self):
        """Тест отображения всех записей"""
        response = self.client.get(self.url)
        self.assertEqual(len(response.context[0]['object_list']), 11)  # 5 доходов + 6 расход

    def test_view_filtering_by_type(self):
        """Тест фильтрации по типу записи"""
        # Фильтруем только доходы
        response = self.client.get(self.url + '?entry_types=income')
        self.assertEqual(len(response.context[0]['object_list']), 5)
        for record in response.context[0]['object_list']:
            self.assertEqual(record.entry_type, 'income')

        # Фильтруем только расходы
        response = self.client.get(self.url + '?entry_types=expense')
        self.assertEqual(len(response.context[0]['object_list']), 6)
        self.assertEqual(response.context[0]['object_list'][0].entry_type, 'expense')

    def test_view_filtering_by_branch(self):
        """Тест фильтрации по филиалу"""
        response = self.client.get(self.url + f'?branch={self.branch.id}')
        self.assertEqual(len(response.context[0]['object_list']), 11)
        for record in response.context[0]['object_list']:
            self.assertEqual(record.branch, self.branch)

    def test_view_filtering_by_date(self):
        """Тест фильтрации по дате"""
        date_from = (timezone.now() - timedelta(days=3)).strftime('%d.%m.%Y')
        date_to = (timezone.now() + timedelta(days=1)).strftime('%d.%m.%Y')

        response = self.client.get(
            self.url + f'?added_range={date_from}+-+{date_to}'
        )
        self.assertEqual(len(response.context[0]['object_list']), 11)

    def test_view_context_totals(self):
        """Тест корректности расчетов итоговых сумм"""
        response = self.client.get(self.url + '?entry_types=income')
        self.assertEqual(response.context[0]['total_income'], 15000)  # 1000+2000+3000+4000+5000
        self.assertEqual(response.context[0]['total_expense'], 0)
        self.assertEqual(response.context[0]['balance'], 15000)

        response = self.client.get(self.url)
        self.assertEqual(response.context[0]['total_income'], 15000)
        self.assertEqual(response.context[0]['total_expense'], 6500)
        self.assertEqual(response.context[0]['balance'], 8500)


class AccountingRecordCreateViewTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city = City.objects.create(name='Moscow')
        cls.branch = Branch.objects.create(name='Main Branch', city=cls.city)
        cls.manager = create_user_with_role(
            username='main_manager',
            role=USER_ROLES.MANAGER,
        )

        cls.master = Master.objects.create(
            full_name='Test Master',
            hire_date='2023-01-01',
        )
        cls.master.branches.add(cls.branch)
        cls.url = reverse('bookkeeping:entry_create')
        cls.client = Client()

    def setUp(self):
        super().setUp()
        self.client.force_login(self.manager)

    def test_view_url_exists(self):
        """Тест доступности URL"""
        valid_roles = (USER_ROLES.MANAGER, USER_ROLES.ACCOUNTANT, USER_ROLES.CHIEF, USER_ROLES.CITY_ADMIN)
        for role in USER_ROLES.choices:
            user = create_user_with_role(username=role[0], role=role[0], current_city=self.branch.city,
                                         cities=[self.branch.city])
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200 if user.zone_user.role in valid_roles else 403)

    def test_create_accounting_record_unauthorized(self):
        """Тест доступа для неавторизованных пользователей"""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Должен перенаправить на login
        self.assertRedirects(response, f'/auth_zone/login/?next={self.url}')

    def test_create_accounting_record_authorized(self):
        """Тест доступа для авторизованных пользователей"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookkeeping/entry_create.html')

    def test_create_valid_accounting_record(self):
        """Тест создания валидной бухгалтерской записи"""
        initial_count = AccountingEntry.objects.count()

        response = self.client.post(self.url, {
            'entry_type': 'income',
            'amount': '1500.00',
            'description': 'Test income record',
            'branch': self.branch.id,
        })

        self.assertEqual(response.status_code, 302)  # Проверяем редирект после успешного создания
        self.assertEqual(AccountingEntry.objects.count(), initial_count + 1)
        self.assertRedirects(response, reverse('bookkeeping:entry_list', query={'city': self.branch.city_id}))

        # Проверяем созданную запись
        record = AccountingEntry.objects.latest('id')
        self.assertEqual(record.amount, 1500)
        self.assertEqual(record.entry_type, 'income')
        self.assertEqual(record.branch, self.branch)

    def test_create_invalid_accounting_record(self):
        """Тест создания невалидной бухгалтерской записи"""
        initial_count = AccountingEntry.objects.count()

        response = self.client.post(self.url, {
            'entry_type': 'invalid_type',  # Невалидный тип
            'amount': '',  # Пропущено обязательное поле
            'branch': self.branch.id
        })

        self.assertEqual(response.status_code, 200)  # Форма должна вернуться с ошибками
        self.assertEqual(AccountingEntry.objects.count(), initial_count)  # Запись не должна быть создана

    def test_other_branch_create(self):
        """Проверка, что пользователь из другого филиала может создавать записи только для своего филиала"""
        other_branch = Branch.objects.create(name='Other Branch', city=City.objects.create(name='Other City'))
        user = create_user_with_role(username='city_admin', role=USER_ROLES.CITY_ADMIN, current_city=other_branch.city,
                                     cities=[other_branch.city])
        self.client.force_login(user)
        response = self.client.post(self.url, {
            'entry_type': 'income',
            'amount': '1500.00',
            'description': 'Test income record',
            'branch': self.branch.id,
        })
        self.assertFormError(response.context[0]['form'], 'branch',
                             f'Выберите корректный вариант. {self.branch.id} нет среди допустимых значений.')
