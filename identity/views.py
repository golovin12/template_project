from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy, reverse
from django.views import View

from accounts.base import OrganizationRequest
from accounts.middleware import AntiBruteForceMiddleware
from accounts.mixins import ForSuperUserMixin, RoleRequiredMixin
from .forms import LoginForm
from .models import AuthUser


class LoginView(auth_views.LoginView):
    """Страница входа в аккаунт"""
    template_name = 'identity/login.html'
    extra_context = {'title': 'Вход в систему'}
    form_class = LoginForm
    next_page = reverse_lazy('home')

    def form_valid(self, form):
        result = super().form_valid(form)
        key = getattr(self.request, 'login_attempts_cache_key', None)
        if key:
            cache.delete(key)
        return result

    def form_invalid(self, form):
        result = super().form_invalid(form)
        key = getattr(self.request, 'login_attempts_cache_key', None)
        if key:
            attempts = cache.get(key, 0)
            cache.set(key, attempts + 1, timeout=AntiBruteForceMiddleware.BLOCK_TIME)

        return result


class LogoutView(auth_views.LogoutView):
    """Страница выхода"""
    template_name = 'identity/logged_out.html'


class SelectOrganizationView(RoleRequiredMixin, View):
    """Переключение текущей зоны."""

    def post(self, request: OrganizationRequest, *args, **kwargs):
        organization_alias = request.POST.get('organization_alias')

        if not organization_alias:
            messages.error(request, 'Не выбрана организация.')
            return JsonResponse({'ok': False})

        organization_name = request.available_organizations.get(organization_alias)

        if organization_name is None:
            messages.error(request, 'Недопустимая организация.')
            return JsonResponse({'ok': False})

        request.session['current_db_alias'] = organization_alias

        messages.success(request, f'Используется организация: {organization_name}.')

        return JsonResponse({'ok': True})


class AuthorizeAsView(ForSuperUserMixin, View):
    """Авторизация под любым пользователем для суперпользователей"""

    def get(self, request: WSGIRequest, *args, **kwargs) -> HttpResponseRedirect:
        profile_redirect = HttpResponseRedirect(reverse('home'))
        username = request.GET.get('username')
        if not username:
            messages.error(request, 'Не задан параметр: username')
            return profile_redirect

        user_obj = AuthUser.objects.filter(username=username).first()
        if not user_obj:
            messages.error(request, f'Пользователь {username} не найден')
            return profile_redirect

        if not user_obj.is_active:
            messages.error(request, f'{username} неактивен')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        user_obj.backend = 'django.contrib.auth.backends.ModelBackend'
        auth_views.auth_login(request, user_obj)
        request.session.set_expiry(60 * 60)
        messages.info(request, f'Вы вошли на сайт как {user_obj.username}')
        return profile_redirect
