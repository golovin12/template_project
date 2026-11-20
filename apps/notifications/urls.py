from django.urls import path

from .views import NotificationSettingsView, VKWebhookView

app_name = 'notifications'

urlpatterns = [
    path('settings/', NotificationSettingsView.as_view(), name='settings'),
    path('vk/webhook/', VKWebhookView.as_view(), name='vk_webhook'),
]
