from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.decorators import (
    chief_required,
    city_admin_required,
    manager_required,
    role_required,
)
from common_tools.test import BaseTestCase


class TestRoleRequired(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def get_request(self, user):
        request = self.factory.get('/')
        request.user = user
        return request

    def test_allows_required_role(self):
        user = create_user_with_role('test', USER_ROLES.CHIEF)

        @role_required(USER_ROLES.CHIEF)
        def view(request):
            return 'ok'

        self.assertEqual(view(self.get_request(user)), 'ok')

    def test_allows_manager_for_other_role(self):
        user = create_user_with_role('manager', USER_ROLES.MANAGER)

        @role_required(USER_ROLES.CHIEF)
        def view(request):
            return 'ok'

        self.assertEqual(view(self.get_request(user)), 'ok')

    def test_denies_user_without_required_role(self):
        user = create_user_with_role('test', USER_ROLES.CHIEF)

        @role_required(USER_ROLES.CITY_ADMIN)
        def view(request):
            return 'ok'

        with self.assertRaises(PermissionDenied):
            view(self.get_request(user))

    def test_manager_required(self):
        manager = create_user_with_role('manager', USER_ROLES.MANAGER)
        chief = create_user_with_role('chief', USER_ROLES.CHIEF)

        @manager_required
        def view(request):
            return 'ok'

        self.assertEqual(view(self.get_request(manager)), 'ok')

        with self.assertRaises(PermissionDenied):
            view(self.get_request(chief))

    def test_city_admin_required(self):
        city_admin = create_user_with_role('city_admin', USER_ROLES.CITY_ADMIN)
        chief = create_user_with_role('chief', USER_ROLES.CHIEF)

        @city_admin_required
        def view(request):
            return 'ok'

        self.assertEqual(view(self.get_request(city_admin)), 'ok')

        with self.assertRaises(PermissionDenied):
            view(self.get_request(chief))

    def test_chief_required(self):
        chief = create_user_with_role('chief', USER_ROLES.CHIEF)
        city_admin = create_user_with_role('city_admin', USER_ROLES.CITY_ADMIN)

        @chief_required
        def view(request):
            return 'ok'

        self.assertEqual(view(self.get_request(chief)), 'ok')

        with self.assertRaises(PermissionDenied):
            view(self.get_request(city_admin))
