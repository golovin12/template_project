from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City
from apps.bookkeeping.models import AccountingEntry
from common_tools.test import BaseTestCase


class BaseBookkeepingViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Москва')
        self.branch = Branch.objects.create(name='Центральный', city=self.city)
        self.user = create_user_with_role(
            'manager',
            USER_ROLES.MANAGER,
        )
        self.client.force_login(self.user)


class TestDashboardView(BaseBookkeepingViewTestCase):
    def test_renders_dashboard(self):
        response = self.client.get(reverse('bookkeeping:dashboard'))

        self.assertEqual(response.status_code, 200)


class TestAccountingEntryListView(BaseBookkeepingViewTestCase):
    def test_renders_entry_list_with_totals(self):
        AccountingEntry.objects.create(
            entry_type=AccountingEntry.ENTRY_TYPE.INCOME,
            amount='5000.00',
            description='Пополнение',
            city=self.city,
        )
        AccountingEntry.objects.create(
            entry_type=AccountingEntry.ENTRY_TYPE.EXPENSE,
            amount='1500.00',
            description='Расход',
            city=self.city,
        )

        response = self.client.get(reverse('bookkeeping:entry_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_income'], 5000)
        self.assertEqual(response.context['total_expense'], 1500)
        self.assertEqual(response.context['balance'], 3500)

    def test_exports_entries_to_excel(self):
        response = self.client.get(
            reverse('bookkeeping:entry_list'),
            {'to_excel': '1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment;', response['Content-Disposition'])


class TestAccountingEntryCreateView(BaseBookkeepingViewTestCase):
    def test_displays_income_form(self):
        response = self.client.get(
            reverse('bookkeeping:entry_create'),
            {'mode': AccountingEntry.ENTRY_TYPE.INCOME},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].fields['entry_type'].disabled)
        self.assertEqual(
            response.context['form'].fields['entry_type'].initial,
            AccountingEntry.ENTRY_TYPE.INCOME,
        )

    def test_displays_expense_form(self):
        response = self.client.get(
            reverse('bookkeeping:entry_create'),
            {'mode': AccountingEntry.ENTRY_TYPE.EXPENSE},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].fields['entry_type'].disabled)
        self.assertEqual(
            response.context['form'].fields['entry_type'].initial,
            AccountingEntry.ENTRY_TYPE.EXPENSE,
        )

    def test_creates_income_entry(self):
        response = self.client.post(
            reverse('bookkeeping:entry_create') + '?mode=income',
            {
                'entry_type': AccountingEntry.ENTRY_TYPE.INCOME,
                'amount': '5000.00',
                'description': 'Пополнение',
                'branch': self.branch.pk,
            },
        )

        entry = AccountingEntry.objects.get(description='Пополнение')

        self.assertRedirects(
            response,
            reverse('bookkeeping:entry_list', query={'city': self.city.pk}),
            fetch_redirect_response=False,
        )
        self.assertEqual(entry.entry_type, AccountingEntry.ENTRY_TYPE.INCOME)
        self.assertEqual(entry.created_by, self.user.organization_user)
        self.assertEqual(entry.city, self.city)

    def test_creates_expense_entry(self):
        response = self.client.post(
            reverse('bookkeeping:entry_create') + '?mode=expense',
            {
                'entry_type': AccountingEntry.ENTRY_TYPE.EXPENSE,
                'amount': '1500.00',
                'description': 'Закупка материалов',
                'branch': self.branch.pk,
            },
        )

        entry = AccountingEntry.objects.get(description='Закупка материалов')

        self.assertRedirects(
            response,
            reverse('bookkeeping:entry_list', query={'city': self.city.pk}),
            fetch_redirect_response=False,
        )
        self.assertEqual(entry.entry_type, AccountingEntry.ENTRY_TYPE.EXPENSE)
        self.assertEqual(entry.expense_subtype, AccountingEntry.EXPENSE_SUBTYPE.OTHER)
        self.assertEqual(entry.created_by, self.user.organization_user)
        self.assertEqual(entry.city, self.city)
        self.assertIn(
            'Запись в бухгалтерию успешно добавлена!',
            [message.message for message in get_messages(response.wsgi_request)],
        )
