from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City, OrganizationUser
from common_tools.test import BaseTestCase
from identity.models import AuthUser


class BaseAccountsViewTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.manager = create_user_with_role(
            'manager',
            USER_ROLES.MANAGER,
        )
        self.client.force_login(self.manager)

    def get_messages(self, response):
        return [message.message for message in get_messages(response.wsgi_request)]


class TestSelectCityView(BaseAccountsViewTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Москва')
        Branch.objects.create(name='Центральный', city=self.city)

    def test_selects_allowed_city(self):
        response = self.client.post(
            reverse('accounts:set_current_city'),
            {'city_id': self.city.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(
            self.client.session['current_city_id:organization_1'],
            self.city.pk,
        )

    def test_selects_all_cities(self):
        session = self.client.session
        session['current_city_id:organization_1'] = self.city.pk
        session.save()

        response = self.client.post(
            reverse('accounts:set_current_city'),
            {'city_id': 'all'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertNotIn('current_city_id:organization_1', self.client.session)

    def test_rejects_city_without_access(self):
        other_city = City.objects.create(name='Казань')
        Branch.objects.create(name='Центральный', city=other_city)

        response = self.client.post(
            reverse('accounts:set_current_city'),
            {'city_id': other_city.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': False})
        self.assertIn('Недопустимый город', self.get_messages(response))


class TestHomePageView(BaseTestCase):
    def test_redirects_user_with_role_to_requests(self):
        user = create_user_with_role('chief', USER_ROLES.CHIEF)
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:go_home'))

        self.assertRedirects(
            response,
            reverse('service_request:request_main'),
            fetch_redirect_response=False,
        )

    def test_redirects_user_without_role_to_login(self):
        user = create_user_with_role('user', '')
        self.client.force_login(user)

        response = self.client.get(reverse('accounts:go_home'))

        self.assertRedirects(
            response,
            reverse('identity:login'),
            fetch_redirect_response=False,
        )


class TestUserDeleteView(BaseAccountsViewTestCase):
    def test_deletes_user_from_organization(self):
        user = create_user_with_role('target', USER_ROLES.CHIEF)
        user_id = user.pk
        organization_user = user.organization_user
        organization_user_id = organization_user.pk

        response = self.client.get(
            reverse('accounts:delete', args=[organization_user_id]),
        )

        self.assertRedirects(
            response,
            reverse('accounts:list'),
            fetch_redirect_response=False,
        )
        self.assertFalse(AuthUser.objects.filter(pk=user_id).exists())
        self.assertFalse(OrganizationUser.objects.filter(pk=organization_user_id).exists())

    def test_does_not_delete_global_superuser(self):
        user = create_user_with_role(
            'global_admin',
            USER_ROLES.MANAGER,
            is_superuser=True,
        )
        organization_user = user.organization_user

        response = self.client.get(
            reverse('accounts:delete', args=[organization_user.pk]),
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(AuthUser.objects.filter(pk=user.pk).exists())


class TestCrudViews(BaseAccountsViewTestCase):
    def test_creates_city(self):
        response = self.client.post(
            reverse('accounts:city_create'),
            {'name': 'Москва'},
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(City.objects.filter(name='Москва').exists())

    def test_creates_branch(self):
        city = City.objects.create(name='Москва')

        response = self.client.post(
            reverse('accounts:branch_create'),
            {
                'name': 'Центральный',
                'city': city.pk,
            },
        )

        self.assertRedirects(
            response,
            reverse('accounts:branch_list'),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Branch.objects.filter(name='Центральный', city=city).exists()
        )
