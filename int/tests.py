import logging

from django.contrib.admin import site
from django.test import RequestFactory

from accounts.base import create_user_with_role
from common_tools.test import BaseTestCase

logging.getLogger("django.security.DisallowedHost").setLevel(logging.CRITICAL)
logging.getLogger("django.request").setLevel(logging.CRITICAL)


class TestAdminPages(BaseTestCase):
    """Базовая работа админки - с правами суперюзера"""
    ANSWER_CODE_OK = 200

    def setUp(self) -> None:
        super().setUp()
        name = 'Test'
        self.admin_user = create_user_with_role(username=name, role='manager', is_superuser=True)
        self.client.force_login(self.admin_user)
        request_factory = RequestFactory()
        self.request = request_factory.get('/admin/')
        self.request.user = self.admin_user

    def test_admin_pages(self) -> None:
        self._check_main_page()
        applications_dict = site._build_app_dict(self.request)
        self.assertEqual(bool(applications_dict), True, "Не найдены зарегистрированные приложения")
        for application in applications_dict.values():
            self._check_application_page(application)
            for model in application['models']:
                self._check_model_page_and_search(model)
                self._check_add_page(model)

    def _check_main_page(self) -> None:
        """Проверка основной страницы админки"""
        self.assertEqual(self.client.get('/admin/').status_code, self.ANSWER_CODE_OK, 'Не работает основная страница')

    def _check_application_page(self, application: dict) -> None:
        """Проверка работы страницы отображения моделей приложения"""
        app_url = application['app_url']
        self.assertEqual(self.client.get(app_url).status_code, self.ANSWER_CODE_OK, f'Error get({app_url})')

    def _check_model_page_and_search(self, model: dict) -> None:
        """Проверка работы страницы отображения объектов модели и поиска"""
        model_has_view_perm = model['perms']['view']
        if model_has_view_perm:
            model_url = model['admin_url']
            self.assertEqual(self.client.get(model_url).status_code, self.ANSWER_CODE_OK, f'Error get({model_url})')

            search_url = f"{model_url}?q=test"
            err_msg = "ok"
            try:
                status_code = self.client.get(search_url).status_code
            except Exception as e:
                status_code = 500
                err_msg = e
            self.assertEqual(status_code, self.ANSWER_CODE_OK, f'get({search_url}): {err_msg}')

    def _check_add_page(self, model: dict) -> None:
        """Проверка работы страницы добавления"""
        model_has_add_perm = model['perms']['add']
        if model_has_add_perm:
            add_url = model['add_url']
            self.assertEqual(self.client.get(add_url).status_code, self.ANSWER_CODE_OK, f'Error get({add_url})')
