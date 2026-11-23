from datetime import timedelta
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.http import HttpResponse
from django.utils import timezone

from accounts.middleware import AntiBruteForceMiddleware, SlidingSessionMiddleware


class TestAntiBruteForceMiddleware(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.response = HttpResponse('ok')
        self.middleware = AntiBruteForceMiddleware(lambda request: self.response)

    def get_request(self, username='test', ip='127.0.0.1', path='/identity/login/'):
        request = self.factory.post(path, {'username': username})
        request.META['REMOTE_ADDR'] = ip
        SessionMiddleware(lambda req: None).process_request(request)
        request._messages = FallbackStorage(request)
        return request

    def test_get_client_ip_uses_real_ip_header(self):
        request = self.get_request()
        request.META['HTTP_X_REAL_IP'] = '10.0.0.1'

        self.assertEqual(
            self.middleware.get_client_ip(request),
            '10.0.0.1',
        )

    def test_get_client_ip_uses_remote_addr(self):
        request = self.get_request()

        self.assertEqual(
            self.middleware.get_client_ip(request),
            '127.0.0.1',
        )

    def test_get_client_ip_returns_unknown_without_ip(self):
        request = self.factory.get('/')

        self.assertEqual(
            self.middleware.get_client_ip(request),
            'unknown',
        )

    def test_allows_request_below_attempt_limit(self):
        request = self.get_request(username=' Test ')
        response = self.middleware(request)

        self.assertIs(response, self.response)
        self.assertEqual(
            request.login_attempts_cache_key,
            'login_attempts:127.0.0.1:test',
        )

    def test_blocks_request_at_attempt_limit(self):
        request = self.get_request(username='Test')
        cache.set(
            'login_attempts:127.0.0.1:test',
            self.middleware.MAX_ATTEMPTS,
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('identity:login'))
        self.assertEqual(
            [message.message for message in messages.get_messages(request)],
            ['Превышено число неудачных попыток входа. Попробуйте через 5 минут.'],
        )

    def test_does_not_check_other_paths(self):
        request = self.get_request(path='/')

        response = self.middleware(request)

        self.assertIs(response, self.response)
        self.assertFalse(hasattr(request, 'login_attempts_cache_key'))

    def test_does_not_check_get_requests(self):
        request = self.factory.get('/identity/login/')

        response = self.middleware(request)

        self.assertIs(response, self.response)
        self.assertFalse(hasattr(request, 'login_attempts_cache_key'))


class TestSlidingSessionMiddleware(SimpleTestCase):
    def setUp(self):
        self.response = HttpResponse('ok')
        self.middleware = SlidingSessionMiddleware(lambda request: self.response)

    def get_request(self, user, session=None):
        return SimpleNamespace(
            user=user,
            session=session if session is not None else SessionStore(),
        )

    def test_updates_activity_for_authenticated_user_without_timestamp(self):
        request = self.get_request(
            SimpleNamespace(is_authenticated=True),
        )

        response = self.middleware(request)

        self.assertIs(response, self.response)
        self.assertIn('last_activity', request.session)
        self.assertTrue(request.session.modified)

    def test_updates_activity_after_interval(self):
        last_activity = timezone.now() - timedelta(hours=2)
        session = SessionStore()
        session['last_activity'] = last_activity.isoformat()
        request = self.get_request(
            SimpleNamespace(is_authenticated=True),
            session,
        )

        self.middleware(request)

        self.assertGreater(
            timezone.datetime.fromisoformat(request.session['last_activity']),
            last_activity,
        )
        self.assertTrue(request.session.modified)

    def test_does_not_update_recent_activity(self):
        last_activity = timezone.now() - timedelta(minutes=10)
        session = SessionStore()
        session['last_activity'] = last_activity.isoformat()
        request = self.get_request(
            SimpleNamespace(is_authenticated=True),
            session,
        )

        self.middleware(request)

        self.assertEqual(request.session['last_activity'], last_activity.isoformat())
        self.assertFalse(getattr(request.session, 'modified', False))

    def test_does_not_update_anonymous_session(self):
        request = self.get_request(AnonymousUser())

        self.middleware(request)

        self.assertNotIn('last_activity', request.session)

    @override_settings(SESSION_UPDATE_INTERVAL_HOURS=2)
    def test_uses_configured_update_interval(self):
        middleware = SlidingSessionMiddleware(lambda request: self.response)
        last_activity = timezone.now() - timedelta(hours=1)
        session = SessionStore()
        session['last_activity'] = last_activity.isoformat()
        request = self.get_request(
            SimpleNamespace(is_authenticated=True),
            session,
        )

        middleware(request)

        self.assertEqual(request.session['last_activity'], last_activity.isoformat())
