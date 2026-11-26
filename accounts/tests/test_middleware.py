from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from common_tools.test import BaseTestCase


class TestAntiBruteForceMiddleware(BaseTestCase):
    @override_settings(CAPTCHA_TEST_MODE=True)
    def test_counts_failed_login_attempts(self):
        response = self.client.post(
            reverse('identity:login'),
            {
                'username': 'test',
                'password': 'wrong-password',
                'captcha_0': 'test',
                'captcha_1': 'passed',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(cache.get('login_attempts:127.0.0.1:test'), 1)

    @override_settings(CAPTCHA_TEST_MODE=True)
    def test_uses_real_ip_header(self):
        self.client.post(
            reverse('identity:login'),
            {
                'username': 'test',
                'password': 'wrong-password',
                'captcha_0': 'test',
                'captcha_1': 'passed',
            },
            HTTP_X_REAL_IP='10.0.0.1',
        )

        self.assertEqual(cache.get('login_attempts:10.0.0.1:test'), 1)
        self.assertIsNone(cache.get('login_attempts:127.0.0.1:test'))

    def test_blocks_login_after_attempt_limit(self):
        cache.set(
            'login_attempts:127.0.0.1:test',
            5,
        )

        response = self.client.post(
            reverse('identity:login'),
            {'username': 'test', 'password': 'password'},
        )

        self.assertRedirects(
            response,
            reverse('identity:login'),
            fetch_redirect_response=False,
        )

        self.assertEqual(response.wsgi_request.user.username, '')
        self.assertEqual(
            cache.get('login_attempts:127.0.0.1:test'),
            5,
        )

    def test_does_not_check_get_requests(self):
        self.client.get(reverse('identity:login'))

        self.assertIsNone(cache.get('login_attempts:127.0.0.1:test'))

    def test_does_not_check_other_paths(self):
        response = self.client.post(
            reverse('accounts:set_current_city'),
            {'city_id': '1'},
        )

        self.assertNotEqual(response.status_code, 404)
        self.assertIsNone(cache.get('login_attempts:127.0.0.1:test'))


class TestSlidingSessionMiddleware(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user_with_role('chief', USER_ROLES.CHIEF)
        self.client.force_login(self.user)

    def test_updates_activity_without_timestamp(self):
        response = self.client.get(reverse('accounts:go_home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('last_activity', self.client.session)

    def test_updates_activity_after_interval(self):
        last_activity = timezone.now() - timedelta(days=2)
        session = self.client.session
        session['last_activity'] = last_activity.isoformat()
        session.save()

        self.client.get(reverse('accounts:go_home'))

        updated_activity = timezone.datetime.fromisoformat(
            self.client.session['last_activity']
        )

        self.assertGreater(updated_activity, last_activity)

    def test_does_not_update_recent_activity(self):
        last_activity = timezone.now() - timedelta(minutes=10)
        session = self.client.session
        session['last_activity'] = last_activity.isoformat()
        session.save()

        self.client.get(reverse('accounts:go_home'))

        self.assertEqual(
            self.client.session['last_activity'],
            last_activity.isoformat(),
        )

    @override_settings(SESSION_UPDATE_INTERVAL_HOURS=2)
    def test_uses_configured_update_interval(self):
        last_activity = timezone.now() - timedelta(hours=1)
        session = self.client.session
        session['last_activity'] = last_activity.isoformat()
        session.save()

        self.client.get(reverse('accounts:go_home'))

        self.assertEqual(
            self.client.session['last_activity'],
            last_activity.isoformat(),
        )
