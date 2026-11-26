import json

import requests

from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.views.generic import TemplateView

from accounts.base import OrganizationRequest
from accounts.consts import USER_ROLES
from accounts.mixins import RoleRequiredMixin
from accounts.models import OrganizationUser
from int.db_context import DatabaseContext
from .enums import NotificationProvider, get_info_bot_token, NotificationEventType
from .forms import NotificationSettingsForm
from .models import (
    NotificationSettings, NotificationMessage, NotificationChannel, get_or_create_connect_code, NotificationConnectCode
)
from .services import notification_sender


class NotificationSettingsView(RoleRequiredMixin, TemplateView):
    roles_required = (USER_ROLES.CHIEF, USER_ROLES.CITY_ADMIN)
    template_name = 'notifications/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization_user = self.request.user.organization_user

        vk_code = get_or_create_connect_code(organization_user, NotificationProvider.VK)
        context['vk_connect_code'] = vk_code.code
        context['vk_bot_url'] = f'https://vk.ru/im?sel=-{settings.VK["INFO_BOT_GROUP_ID"]}'

        try:
            notification_settings = NotificationSettings.objects.get(user=organization_user)
        except NotificationSettings.DoesNotExist:
            notification_settings = None

        vk_channel = None
        if notification_settings:
            context['form'] = NotificationSettingsForm(instance=notification_settings, user=organization_user)
            vk_channel = notification_settings.channels.filter(provider=NotificationProvider.VK, enabled=True).first()

        context['vk_channel'] = vk_channel
        return context

    def post(self, request: OrganizationRequest, *args, **kwargs):
        organization_user = request.user.organization_user

        try:
            notification_settings = NotificationSettings.objects.get(user=organization_user)
        except NotificationSettings.DoesNotExist:
            messages.error(request, 'Настройки не найдены!')
            return redirect('notifications:settings')

        form = NotificationSettingsForm(request.POST, instance=notification_settings, user=organization_user)

        if form.is_valid():
            form.save()
            messages.success(request, 'Настройки успешно сохранены!')
        return redirect('notifications:settings')


@method_decorator(csrf_exempt, name='dispatch')
class VKWebhookView(View):
    def post(self, request: WSGIRequest, *args, **kwargs):
        data = json.loads(request.body)

        if data.get('type') == 'confirmation':
            return HttpResponse('823a8667')

        if data.get('secret') != settings.VK['INFO_BOT_SECRET']:
            return HttpResponse('forbidden', status=403)

        if data.get('type') == 'message_new':
            return self.handle_message(data['object']['message'])

        return HttpResponse('ok')

    def handle_message(self, message):
        connection_code = message.get('text', '').strip()
        vk_user_id = str(message.get('from_id'))

        connect = NotificationConnectCode.objects.filter(
            code=connection_code,
            provider=NotificationProvider.VK,
            is_used=False,
            expires_at__gt=timezone.now()
        ).first()

        if not connect or not connect.database_alias:
            return HttpResponse('ok')

        return self.connect_vk(connect, vk_user_id)

    def connect_vk(self, connect_obj: NotificationConnectCode, vk_user_id: str):
        with DatabaseContext.using(connect_obj.database_alias):
            organization_user: OrganizationUser = OrganizationUser.objects.filter(id=connect_obj.user_id).first()

            if not organization_user:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Юзер не найден'
                })

            settings_obj, _ = NotificationSettings.objects.get_or_create(
                user=organization_user,
                defaults={
                    'enabled': True,
                    'notif_type': NotificationEventType.NEW
                }
            )

            vk_username = self.get_vk_username(vk_user_id)

            NotificationChannel.objects.update_or_create(
                notification_settings=settings_obj,
                provider=NotificationProvider.VK,
                defaults={
                    'recipient_id': str(vk_user_id),
                    'username': vk_username,
                    'enabled': True,
                }
            )

            connect_obj.is_used = True
            connect_obj.save(update_fields=['is_used'])

            self.send_vk_welcome(vk_user_id, organization_user.username)

            return HttpResponse('ok')

    def get_vk_username(self, vk_user_id: str) -> str:
        try:
            url = 'https://api.vk.ru/method/users.get'

            params = {
                'user_ids': vk_user_id,
                'access_token': settings.VK['INFO_BOT_TOKEN'],
                'v': '5.199'
            }

            r = requests.get(url, params=params, timeout=5)
            data = r.json()

            if 'response' in data and len(data['response']) > 0:
                user = data['response'][0]
                return f'{user.get("first_name", "")} {user.get("last_name", "")}'.strip()
        except Exception:
            pass

        return ''

    def send_vk_welcome(self, vk_user_id: str, username: str):
        url = f'https://{settings.SERVER_DOMAIN}{reverse("notifications:settings")}'

        message = f'''👋 Привет, {username}!

        ✅ VK успешно подключен!
        Теперь вы будете получать уведомления.

        📱 Настройки: {url}'''

        provider = NotificationProvider.VK
        notification_sender.send_message(NotificationMessage(
            provider=provider,
            provider_token=get_info_bot_token(provider),
            recipient_id=vk_user_id,
            text=message,
            priority=1,
        ))
