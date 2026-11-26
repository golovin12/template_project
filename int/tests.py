import logging
from types import SimpleNamespace

from django.contrib.admin import site
from django.test import RequestFactory, SimpleTestCase

from accounts.base import create_user_with_role
from common_tools.test import BaseTestCase
from int.db_context import (
    DatabaseContext, cache_key, get_current_database, reset_current_database, set_current_database, using_database
)
from int.db_router import OrganizationRouter

logging.getLogger('django.security.DisallowedHost').setLevel(logging.CRITICAL)
logging.getLogger('django.request').setLevel(logging.CRITICAL)


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
        self.assertTrue(bool(applications_dict), 'Не найдены зарегистрированные приложения')
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

            search_url = f'{model_url}?q=test'
            err_msg = 'ok'
            try:
                status_code = self.client.get(search_url).status_code
            except Exception as e:
                status_code = 500
                err_msg = e
            self.assertEqual(status_code, self.ANSWER_CODE_OK, f'get({search_url}): {err_msg}')

    def _check_add_page(self, model: dict) -> None:
        """Проверка работы страницы добавления"""
        if not model['perms']['add']:
            return

        add_url = model['add_url']

        try:
            response = self.client.get(add_url)
        except Exception as error:
            self.fail(f'Ошибка открытия страницы добавления {add_url}: {error}')

        self.assertEqual(response.status_code, self.ANSWER_CODE_OK, f'Error get({add_url})')


class TestDatabaseContext(SimpleTestCase):
    def test_default_database(self):
        self.assertEqual(get_current_database(), 'default')
        self.assertEqual(DatabaseContext.get(), 'default')

    def test_set_and_reset_database(self):
        token = set_current_database('organization_1')

        self.assertEqual(get_current_database(), 'organization_1')
        self.assertEqual(DatabaseContext.get(), 'organization_1')

        reset_current_database(token)

        self.assertEqual(get_current_database(), 'default')

    def test_database_context_set_and_reset(self):
        token = DatabaseContext.set('organization_1')

        self.assertEqual(DatabaseContext.get(), 'organization_1')

        DatabaseContext.reset(token)

        self.assertEqual(DatabaseContext.get(), 'default')

    def test_using_database(self):
        with using_database('organization_1'):
            self.assertEqual(get_current_database(), 'organization_1')

        self.assertEqual(get_current_database(), 'default')

    def test_database_context_using(self):
        with DatabaseContext.using('organization_1'):
            self.assertEqual(DatabaseContext.get(), 'organization_1')

        self.assertEqual(DatabaseContext.get(), 'default')

    def test_nested_database_contexts(self):
        with DatabaseContext.using('organization_1'):
            self.assertEqual(DatabaseContext.get(), 'organization_1')

            with DatabaseContext.using('organization_2'):
                self.assertEqual(DatabaseContext.get(), 'organization_2')

            self.assertEqual(DatabaseContext.get(), 'organization_1')

        self.assertEqual(DatabaseContext.get(), 'default')

    def test_context_restored_after_exception(self):
        with self.assertRaises(RuntimeError):
            with DatabaseContext.using('organization_1'):
                self.assertEqual(DatabaseContext.get(), 'organization_1')
                raise RuntimeError

        self.assertEqual(DatabaseContext.get(), 'default')

    def test_cache_key_uses_current_database(self):
        self.assertEqual(cache_key('test'), 'default:test')

        with DatabaseContext.using('organization_1'):
            self.assertEqual(cache_key('test'), 'organization_1:test')

        self.assertEqual(cache_key('test'), 'default:test')


class TestOrganizationRouter(SimpleTestCase):
    def setUp(self):
        self.router = OrganizationRouter()

    def create_model(self, app_label, model_name='TestModel'):
        return type(model_name, (), {
            '_meta': SimpleNamespace(app_label=app_label),
        })

    def create_object(self, db_alias):
        return SimpleNamespace(_state=SimpleNamespace(db=db_alias))

    def test_auth_apps_read_from_default(self):
        for app_label in self.router.AUTH_APPS:
            with self.subTest(app_label=app_label):
                model = self.create_model(app_label)

                self.assertEqual(self.router.db_for_read(model), 'default')

    def test_auth_apps_write_to_default(self):
        for app_label in self.router.AUTH_APPS:
            with self.subTest(app_label=app_label):
                model = self.create_model(app_label)

                self.assertEqual(self.router.db_for_write(model), 'default')

    def test_default_models_read_from_default(self):
        for model_path in self.router.DEFAULT_MODELS:
            with self.subTest(model_path=model_path):
                app_label, model_name = model_path.split('.')
                model = self.create_model(app_label, model_name.title())

                self.assertEqual(self.router.db_for_read(model), 'default')

    def test_default_models_write_to_default(self):
        for model_path in self.router.DEFAULT_MODELS:
            with self.subTest(model_path=model_path):
                app_label, model_name = model_path.split('.')
                model = self.create_model(app_label, model_name.title())

                self.assertEqual(self.router.db_for_write(model), 'default')

    def test_other_models_read_from_current_database(self):
        model = self.create_model('service_requests')

        with DatabaseContext.using('organization_1'):
            self.assertEqual(self.router.db_for_read(model), 'organization_1')

    def test_other_models_write_to_current_database(self):
        model = self.create_model('service_requests')

        with DatabaseContext.using('organization_2'):
            self.assertEqual(self.router.db_for_write(model), 'organization_2')

    def test_other_models_use_default_database_by_default(self):
        model = self.create_model('service_requests')

        self.assertEqual(self.router.db_for_read(model), 'default')
        self.assertEqual(self.router.db_for_write(model), 'default')

    def test_allow_relation_for_same_database(self):
        obj1 = self.create_object('organization_1')
        obj2 = self.create_object('organization_1')

        self.assertIs(self.router.allow_relation(obj1, obj2), True)

    def test_allow_relation_for_different_databases(self):
        obj1 = self.create_object('default')
        obj2 = self.create_object('organization_1')

        self.assertIs(self.router.allow_relation(obj1, obj2), False)

    def test_auth_apps_migrate_only_on_default(self):
        for app_label in self.router.AUTH_APPS:
            with self.subTest(app_label=app_label):
                self.assertIs(self.router.allow_migrate('default', app_label), True)
                self.assertIs(self.router.allow_migrate('organization_1', app_label), False)

    def test_default_models_migrate_only_on_default(self):
        for model_path in self.router.DEFAULT_MODELS:
            with self.subTest(model_path=model_path):
                app_label, model_name = model_path.split('.')

                self.assertIs(
                    self.router.allow_migrate('default', app_label, model_name),
                    True,
                )
                self.assertIs(
                    self.router.allow_migrate('organization_1', app_label, model_name),
                    False,
                )

    def test_other_models_migrate_only_on_organization_databases(self):
        self.assertIs(self.router.allow_migrate('default', 'service_requests'), False)
        self.assertIs(self.router.allow_migrate('organization_1', 'service_requests'), True)
