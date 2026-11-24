from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from accounts.consts import USER_ROLES
from accounts.models import Branch, City, OrganizationUser
from common_tools.test import BaseTestCase
from identity.models import AuthUser, Organization
from .enums import NotificationEventType, NotificationProvider
from .models import (
    CityNotificationPreference,
    NotificationChannel,
    NotificationConnectCode,
    NotificationMessage,
    NotificationSettings,
)
from .providers.base import clean_html
from .providers.telegram import TelegramProvider
from .providers.vk import VKProvider
from .services import NotificationSender, notification_sender
from .tasks import (
    cleanup_old_telegram_messages,
    create_telegram_message,
    push_new_request_message,
    send_messages,
    send_notifications,
)
from .views import VKWebhookView


class TestCleanHtml(BaseTestCase):
    def test_removes_empty_tags(self):
        self.assertEqual(clean_html('<b></b>text'), 'text')

    def test_closes_unclosed_tags(self):
        self.assertEqual(clean_html('<b>text'), '<b>text</b>')

    def test_removes_duplicate_nested_tags(self):
        self.assertEqual(clean_html('<b><b>text</b></b>'), '<b>text</b>')


class TestTelegramProvider(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.provider = TelegramProvider()
        self.message = NotificationMessage.objects.create(
            provider=NotificationProvider.TELEGRAM,
            provider_token='token',
            recipient_id='123',
            text='<b>Hello</b>',
        )

    def test_prepare_text(self):
        self.assertEqual(
            self.provider.prepare_text('x' * 5000, is_html=False),
            'x' * 4096,
        )

    def test_prepare_html(self):
        self.assertEqual(
            self.provider.prepare_text('<b>Hello', is_html=True),
            '<b>Hello</b>',
        )

    @patch('apps.notifications.providers.telegram.requests.post')
    def test_send_success(self, post):
        post.return_value = Mock()

        result = self.provider.send(self.message, is_html=True)

        self.assertTrue(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.SENT)
        self.assertIsNotNone(self.message.sent_dt)

        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['chat_id'], '123')
        self.assertEqual(payload['parse_mode'], 'HTML')
        self.assertEqual(payload['text'], '<b>Hello</b>')

    @patch('apps.notifications.providers.telegram.requests.post')
    def test_send_failure(self, post):
        post.side_effect = Exception('Connection error')

        result = self.provider.send(self.message)

        self.assertFalse(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.FAILED)
        self.assertEqual(self.message.error_message, 'Connection error')
        self.assertEqual(self.message.retry_count, 1)

        self.assertGreater(self.message.scheduled_for, timezone.now())


class TestVKProvider(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.provider = VKProvider()
        self.message = NotificationMessage.objects.create(
            provider=NotificationProvider.VK,
            provider_token='token',
            recipient_id='123',
            text='Hello',
        )

    @patch('apps.notifications.providers.vk.requests.post')
    def test_send_success(self, post):
        post.return_value.json.return_value = {'response': 123}

        result = self.provider.send(self.message)

        self.assertTrue(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.SENT)
        self.assertIsNotNone(self.message.sent_dt)
        self.assertIsNone(self.message.error_message)

        payload = post.call_args.kwargs['data']
        self.assertEqual(payload['peer_id'], 123)
        self.assertEqual(payload['message'], 'Hello')
        self.assertEqual(payload['access_token'], 'token')

    @patch('apps.notifications.providers.vk.requests.post')
    def test_send_terminal_error(self, post):
        post.return_value.json.return_value = {
            'error': {
                'error_code': 104,
                'error_msg': 'Invalid peer',
            }
        }

        result = self.provider.send(self.message)

        self.assertFalse(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.FAILED)
        self.assertEqual(self.message.retry_count, settings.NOTIFICATIONS_MAX_RETRIES)
        self.assertEqual(self.message.error_message, '[VK 104] Invalid peer')

    @patch('apps.notifications.providers.vk.requests.post')
    def test_send_retryable_error(self, post):
        post.return_value.json.return_value = {
            'error': {
                'error_code': 5,
                'error_msg': 'Auth error',
            }
        }

        result = self.provider.send(self.message)

        self.assertFalse(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.FAILED)
        self.assertEqual(self.message.retry_count, 1)
        self.assertEqual(self.message.error_message, '[VK 5] Auth error')

    @patch('apps.notifications.providers.vk.requests.post')
    def test_send_timeout(self, post):
        from requests.exceptions import Timeout

        post.side_effect = Timeout

        result = self.provider.send(self.message)

        self.assertFalse(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.FAILED)
        self.assertEqual(self.message.error_message, 'VK timeout')
        self.assertEqual(self.message.retry_count, 1)

    @patch('apps.notifications.providers.vk.requests.post')
    def test_send_connection_error(self, post):
        from requests.exceptions import ConnectionError

        post.side_effect = ConnectionError

        result = self.provider.send(self.message)

        self.assertFalse(result)
        self.message.refresh_from_db()

        self.assertEqual(self.message.status, NotificationMessage.Status.FAILED)
        self.assertEqual(self.message.error_message, 'VK connection error')
        self.assertEqual(self.message.retry_count, 1)


class TestNotificationSender(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.sender = NotificationSender()

    def create_message(self, **kwargs):
        defaults = {
            'provider': NotificationProvider.TELEGRAM,
            'provider_token': 'token',
            'recipient_id': '123',
            'text': 'Hello',
        }
        defaults.update(kwargs)
        return NotificationMessage.objects.create(**defaults)

    def test_get_pending_messages(self):
        now = timezone.now()

        high_priority = self.create_message(
            priority=1,
            scheduled_for=now - timedelta(minutes=2),
        )
        low_priority = self.create_message(
            priority=0,
            scheduled_for=now - timedelta(minutes=1),
        )

        messages = self.sender.get_pending_messages(
            limit=10,
            provider=NotificationProvider.TELEGRAM,
        )

        self.assertEqual(
            [message.pk for message in messages],
            [high_priority.pk, low_priority.pk],
        )

    def test_get_pending_messages_respects_limit(self):
        self.create_message(priority=1)
        self.create_message(priority=0)

        messages = self.sender.get_pending_messages(
            limit=1,
            provider=NotificationProvider.TELEGRAM,
        )

        self.assertEqual(len(messages), 1)

    @patch('apps.notifications.services.ProviderRegistry.get')
    def test_send_message(self, get_provider):
        provider = Mock()
        provider.send.return_value = True
        get_provider.return_value = provider

        message = self.create_message(mode=NotificationMessage.ParseMode.HTML)

        result = self.sender.send_message(message)

        self.assertTrue(result)
        provider.send.assert_called_once_with(message, is_html=True)

    @patch('apps.notifications.services.ProviderRegistry.get')
    def test_send_message_uses_text_mode(self, get_provider):
        provider = Mock()
        provider.send.return_value = True
        get_provider.return_value = provider

        message = self.create_message()

        self.sender.send_message(message)

        provider.send.assert_called_once_with(message, is_html=False)

    def test_cleanup_old_messages(self):
        old_sent = self.create_message(
            status=NotificationMessage.Status.SENT,
            sent_dt=timezone.now() - timedelta(days=31),
        )
        recent_sent = self.create_message(
            status=NotificationMessage.Status.SENT,
            sent_dt=timezone.now() - timedelta(days=1),
        )
        max_retries = self.create_message(
            retry_count=settings.NOTIFICATIONS_MAX_RETRIES,
        )
        pending = self.create_message()

        self.sender.cleanup_old_messages()

        self.assertFalse(NotificationMessage.objects.filter(pk=old_sent.pk).exists())
        self.assertFalse(NotificationMessage.objects.filter(pk=max_retries.pk).exists())
        self.assertTrue(NotificationMessage.objects.filter(pk=recent_sent.pk).exists())
        self.assertTrue(NotificationMessage.objects.filter(pk=pending.pk).exists())


class OrganizationNotificationTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()

        self.organization = Organization.objects.using('default').create(
            name='Test organization',
            database_alias='organization_1',
        )

        self.auth_user = AuthUser.objects.db_manager('default').create_user(
            username='notification_test',
            password='password',
        )

        self.organization.users.add(self.auth_user)

        self.organization_user = OrganizationUser.objects.create(
            user_id=self.auth_user.pk,
            username=self.auth_user.username,
            role=USER_ROLES.CHIEF,
        )

        self.client.force_login(self.auth_user)

    def create_city(self, name):
        city = City.objects.create(name=name)
        Branch.objects.create(name=f'{name} branch', city=city)
        return city

    def create_notification_settings(self, **kwargs):
        defaults = {
            'user': self.organization_user,
            'enabled': True,
            'notif_type': NotificationEventType.NEW,
        }
        defaults.update(kwargs)
        return NotificationSettings.objects.create(**defaults)


class TestNotificationSettingsView(OrganizationNotificationTestCase):
    def test_get_creates_vk_connect_code(self):
        response = self.client.get(reverse('notifications:settings'))

        self.assertEqual(response.status_code, 200)

        connect_code = NotificationConnectCode.objects.get(
            user_id=self.organization_user.pk,
            provider=NotificationProvider.VK,
        )

        self.assertEqual(response.context['vk_connect_code'], connect_code.code)
        self.assertEqual(connect_code.database_alias, 'organization_1')

    def test_post_without_settings(self):
        response = self.client.post(
            reverse('notifications:settings'),
            {},
            follow=True,
        )

        self.assertEqual(response.redirect_chain[-1][0], reverse('notifications:settings'))

        self.assertIn(
            'Настройки не найдены!',
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_post_updates_settings(self):
        notification_settings = self.create_notification_settings(enabled=False)

        response = self.client.post(
            reverse('notifications:settings'),
            {'enabled': 'on'},
        )

        self.assertEqual(response.status_code, 302)

        notification_settings.refresh_from_db()
        self.assertTrue(notification_settings.enabled)


class TestVKWebhookView(OrganizationNotificationTestCase):
    def post_webhook(self, data):
        return self.client.post(
            reverse('notifications:vk_webhook'),
            data=data,
            content_type='application/json',
        )

    def test_confirmation(self):
        response = self.post_webhook({'type': 'confirmation'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '823a8667')

    def test_invalid_secret(self):
        response = self.post_webhook({
            'type': 'message_new',
            'secret': 'invalid',
            'object': {'message': {}},
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content.decode(), 'forbidden')

    def test_unknown_event(self):
        response = self.post_webhook({
            'type': 'some_event',
            'secret': settings.VK['INFO_BOT_SECRET'],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'ok')

    def test_message_without_connect_code(self):
        response = self.post_webhook({
            'type': 'message_new',
            'secret': settings.VK['INFO_BOT_SECRET'],
            'object': {
                'message': {
                    'text': 'invalid-code',
                    'from_id': 123,
                }
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'ok')

    @patch.object(VKWebhookView, 'send_vk_welcome')
    @patch.object(VKWebhookView, 'get_vk_username', return_value='VK User')
    def test_connect_user(self, get_vk_username, send_vk_welcome):
        connect_code = NotificationConnectCode.objects.create(
            user_id=self.organization_user.pk,
            code='VK-12345678',
            provider=NotificationProvider.VK,
            database_alias='organization_1',
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        response = self.post_webhook({
            'type': 'message_new',
            'secret': settings.VK['INFO_BOT_SECRET'],
            'object': {
                'message': {
                    'text': connect_code.code,
                    'from_id': 123,
                }
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'ok')

        connect_code.refresh_from_db()
        self.assertTrue(connect_code.is_used)

        channel = NotificationChannel.objects.get(
            notification_settings__user=self.organization_user,
            provider=NotificationProvider.VK,
        )

        self.assertEqual(channel.recipient_id, '123')
        self.assertEqual(channel.username, 'VK User')
        self.assertTrue(channel.enabled)

        get_vk_username.assert_called_once_with('123')
        send_vk_welcome.assert_called_once_with('123', self.organization_user.username)


class TestNotificationSignals(OrganizationNotificationTestCase):
    def test_disables_preferences_for_removed_cities(self):
        allowed_city = self.create_city('Allowed')
        removed_city = self.create_city('Removed')

        notification_settings = self.create_notification_settings()

        allowed_preference = CityNotificationPreference.objects.create(
            notification_settings=notification_settings,
            city=allowed_city,
            enabled=True,
        )
        removed_preference = CityNotificationPreference.objects.create(
            notification_settings=notification_settings,
            city=removed_city,
            enabled=True,
        )

        self.organization_user.cities.add(allowed_city)

        allowed_preference.refresh_from_db()
        removed_preference.refresh_from_db()

        self.assertTrue(allowed_preference.enabled)
        self.assertFalse(removed_preference.enabled)


class TestNotificationTasks(OrganizationNotificationTestCase):
    def test_send_messages(self):
        message_1 = NotificationMessage.objects.create(
            provider=NotificationProvider.VK,
            recipient_id='1',
            text='Message 1',
        )
        message_2 = NotificationMessage.objects.create(
            provider=NotificationProvider.VK,
            recipient_id='2',
            text='Message 2',
        )
        message_3 = NotificationMessage.objects.create(
            provider=NotificationProvider.VK,
            recipient_id='3',
            text='Message 3',
        )

        with patch.object(
                notification_sender,
                'send_message',
                side_effect=[True, False, Exception('Error')],
        ):
            unsent = send_messages([message_1, message_2, message_3])

        self.assertEqual(unsent, [message_2, message_3])

    @patch('apps.notifications.tasks.send_messages')
    @patch.object(notification_sender, 'get_pending_messages')
    def test_send_notifications(self, get_pending_messages, send_messages_mock):
        pending_messages = [Mock(), Mock()]
        get_pending_messages.return_value = pending_messages

        send_notifications.fn()

        get_pending_messages.assert_called_once_with(
            limit=settings.VK_BATCH_SIZE,
            provider=NotificationProvider.VK,
        )
        send_messages_mock.assert_called_once_with(pending_messages)

    @patch.object(notification_sender, 'cleanup_old_messages')
    def test_cleanup_old_telegram_messages(self, cleanup):
        cleanup_old_telegram_messages.fn()

        cleanup.assert_called_once_with(
            days_old=settings.NOTIFICATIONS_CLEANUP_DAYS,
        )

    def test_create_telegram_message(self):
        create_telegram_message.fn(
            bot_token='telegram-token',
            chat_id='123',
            text='Hello',
            priority=1,
            mode=NotificationMessage.ParseMode.HTML,
        )

        message = NotificationMessage.objects.get(
            provider=NotificationProvider.TELEGRAM,
            recipient_id='123',
        )

        self.assertEqual(message.provider_token, 'telegram-token')
        self.assertEqual(message.text, 'Hello')
        self.assertEqual(message.priority, 1)
        self.assertEqual(message.mode, NotificationMessage.ParseMode.HTML)

    def test_push_new_request_message(self):
        city = self.create_city('Moscow')
        self.organization_user.cities.add(city)

        notification_settings = self.create_notification_settings()

        CityNotificationPreference.objects.create(
            notification_settings=notification_settings,
            city=city,
            enabled=True,
        )

        NotificationChannel.objects.create(
            notification_settings=notification_settings,
            provider=NotificationProvider.VK,
            recipient_id='123',
            enabled=True,
        )

        push_new_request_message.fn(
            text='New request',
            city_id=city.pk,
        )

        message = NotificationMessage.objects.get(
            provider=NotificationProvider.VK,
            recipient_id='123',
        )

        self.assertEqual(message.text, 'New request')
        self.assertEqual(message.provider_token, settings.VK['INFO_BOT_TOKEN'])
        self.assertEqual(message.priority, 1)
