from captcha.conf import settings as captcha_settings

from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import OrganizationUser
from common_tools.test import BaseTestCase
from identity.models import AuthUser, Organization
from int.db_context import DatabaseContext


class TestAuthUser(BaseTestCase):
    def test_full_name(self):
        user = AuthUser(username='test', last_name='Иванов', first_name='Иван', second_name='Иванович')
        self.assertEqual(user.full_name, 'Иванов Иван Иванович')

    def test_full_name_without_optional_parts(self):
        user = AuthUser(username='test', first_name='Иван')
        self.assertEqual(user.full_name, 'Иван')

    def test_str_returns_username_without_full_name(self):
        user = AuthUser(username='test')
        self.assertEqual(str(user), 'test')

    def test_organization_user_is_created_lazily(self):
        user = AuthUser.objects.create_user(username='test', password='password')
        organization_user = user.organization_user

        self.assertIsNone(organization_user.pk)
        self.assertEqual(organization_user.user_id, user.pk)
        self.assertFalse(organization_user.is_superuser)
        self.assertIs(organization_user._auth_user, user)

    def test_organization_user_is_cached(self):
        user = AuthUser.objects.create_user(username='test', password='password')
        first = user.organization_user
        second = user.organization_user

        self.assertIs(first, second)

    def test_organization_user_uses_existing_record(self):
        user = AuthUser.objects.create_user(username='test', password='password')
        organization_user = OrganizationUser.objects.create(user_id=user.pk, username=user.username, )
        result = user.organization_user

        self.assertEqual(result.pk, organization_user.pk)
        self.assertIs(result._auth_user, user)

    def test_organization_user_inherits_superuser_status(self):
        user = AuthUser.objects.create_superuser(username='superuser', password='password',
                                                 email='superuser@example.com')

        organization_user = user.organization_user

        self.assertTrue(organization_user.is_superuser)


class BaseIdentityViewTestCase(TestCase):
    databases = {'default', 'organization_1'}

    def setUp(self):
        cache.clear()

        self.organization = Organization.objects.create(name='Организация 1', database_alias='organization_1')

    def create_user(self, username, password='password', **kwargs):
        return AuthUser.objects.create_user(username=username, password=password, **kwargs)

    def get_messages(self, response):
        return [message.message for message in get_messages(response.wsgi_request)]


@override_settings(IS_WEB=False)
class TestOrganizationMiddleware(BaseIdentityViewTestCase):
    def test_anonymous_user_uses_default_database(self):
        response = self.client.get(reverse('identity:login'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DatabaseContext.get(), 'default')

    def test_authenticated_user_selects_session_organization(self):
        user = self.create_user('test')
        user.organizations.add(self.organization)
        self.client.force_login(user)

        session = self.client.session
        session['current_db_alias'] = 'organization_1'
        session.save()

        response = self.client.post(
            reverse('identity:select_organization'),
            {'organization_alias': 'organization_1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True})
        self.assertTrue(
            OrganizationUser.objects.using('organization_1').filter(
                user_id=user.pk,
            ).exists()
        )
        self.assertEqual(DatabaseContext.get(), 'default')

    def test_selects_first_available_organization(self):
        user = self.create_user('test')
        user.organizations.add(self.organization)
        self.client.force_login(user)

        response = self.client.post(
            reverse('identity:select_organization'),
            {'organization_alias': 'organization_1'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True})
        self.assertEqual(
            self.client.session['current_db_alias'],
            'organization_1',
        )

    def test_logs_out_user_without_organizations(self):
        user = self.create_user('test')
        self.client.force_login(user)

        response = self.client.get(reverse('identity:select_organization'))

        self.assertRedirects(
            response,
            reverse('identity:login'),
            fetch_redirect_response=False,
        )
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(DatabaseContext.get(), 'default')


class TestLoginView(BaseIdentityViewTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user('test')

        previous_test_mode = captcha_settings.CAPTCHA_TEST_MODE
        captcha_settings.CAPTCHA_TEST_MODE = True
        self.addCleanup(
            setattr, captcha_settings, 'CAPTCHA_TEST_MODE', previous_test_mode
        )

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            reverse('identity:login'),
            {
                'username': 'test',
                'password': 'password',
                'captcha_0': 'PASSED',
                'captcha_1': 'PASSED',
            },
        )

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertIsNone(cache.get('login_attempts:127.0.0.1:test'))

    def test_login_with_invalid_password_increments_attempts(self):
        response = self.client.post(
            reverse('identity:login'),
            {
                'username': 'test',
                'password': 'wrong-password',
                'captcha_0': 'PASSED',
                'captcha_1': 'PASSED',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(cache.get('login_attempts:127.0.0.1:test'), 1)

    def test_successful_login_resets_attempts(self):
        cache.set('login_attempts:127.0.0.1:test', 2)

        response = self.client.post(
            reverse('identity:login'),
            {
                'username': 'test',
                'password': 'password',
                'captcha_0': 'PASSED',
                'captcha_1': 'PASSED',
            },
        )

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertIsNone(cache.get('login_attempts:127.0.0.1:test'))


class TestSelectOrganizationView(BaseIdentityViewTestCase):
    def setUp(self):
        super().setUp()

        self.user = self.create_user('test')
        self.user.organizations.add(self.organization)

        self.client.force_login(self.user)

    def test_post_without_organization_alias(self):
        response = self.client.post(reverse('identity:select_organization'))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': False})
        self.assertEqual(self.client.session['current_db_alias'], 'organization_1')
        self.assertIn('Не выбрана организация.', self.get_messages(response))

    def test_post_with_invalid_organization_alias(self):
        response = self.client.post(reverse('identity:select_organization'), {'organization_alias': 'organization_2'})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': False})
        self.assertEqual(self.client.session['current_db_alias'], 'organization_1')
        self.assertIn('Недопустимая организация.', self.get_messages(response))

    def test_post_with_valid_organization_alias(self):
        response = self.client.post(reverse('identity:select_organization'), {'organization_alias': 'organization_1'})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'ok': True})
        self.assertEqual(self.client.session['current_db_alias'], 'organization_1')
        self.assertIn('Используется организация: Организация 1.', self.get_messages(response))


class TestAuthorizeAsView(BaseIdentityViewTestCase):
    def setUp(self):
        super().setUp()

        self.superuser = self.create_user('superuser', is_staff=True, is_superuser=True)
        self.user = self.create_user('test')
        self.inactive_user = self.create_user('inactive', is_active=False)

        self.client.force_login(self.superuser)

    def test_get_without_username(self):
        response = self.client.get(reverse('identity:authorize'))

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertIn('Не задан параметр: username', self.get_messages(response))

    def test_get_with_unknown_username(self):
        response = self.client.get(reverse('identity:authorize'), {'username': 'unknown'})

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertIn('Пользователь unknown не найден', self.get_messages(response))

    def test_get_with_inactive_user(self):
        response = self.client.get(reverse('identity:authorize'), {'username': 'inactive'}, HTTP_REFERER='/previous/')

        self.assertRedirects(response, '/previous/', fetch_redirect_response=False)
        self.assertIn('inactive неактивен', self.get_messages(response))

    def test_get_with_active_user(self):
        response = self.client.get(reverse('identity:authorize'), {'username': 'test'})

        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60)
        self.assertIn('Вы вошли на сайт как test', self.get_messages(response))
