from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView

from accounts.views import media_file

urlpatterns = [
    path('admin/login/', RedirectView.as_view(url='/identity/login/'), name='admin-login'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('identity/', include('identity.urls')),
    path('promoter_app/', include('promoter_app.urls')),
    path('bookkeeping/', include('apps.bookkeeping.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('promoters/', include('apps.promoters.urls')),
    path('requests/', include('apps.service_requests.urls')),
    path('statistics/', include('apps.statistics.urls')),
    path('captcha/', include('captcha.urls')),
    path('', RedirectView.as_view(permanent=False, url='/accounts/go_home/'), name='home'),

    path('select2/', include('django_select2.urls')),

    re_path(r'^media/(?P<file_path>(?P<app_name>\w+)/models\.(?P<model_name>\w+)\.(?P<field_name>\w+)/.*)', media_file),
]

if settings.DEBUG and settings.ENV == 'STAGE':
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
