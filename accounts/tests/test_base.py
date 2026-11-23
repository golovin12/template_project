from types import SimpleNamespace

from django.contrib.admin import AdminSite
from django.test import SimpleTestCase

from accounts.base import (
    ManagerAdmin,
    MyAdminSite,
    OrganizationRequest,
    create_user_with_role,
)
from accounts.consts import USER_ROLES
from common_tools.test import BaseTestCase


class TestOrganizationRequest(SimpleTestCase):
    def test_current_branch_ids_without_current_city(self):
        request = SimpleNamespace(
            current_city_id=None,
            user=SimpleNamespace(
                organization_user=SimpleNamespace(allowed_branch_ids=[1, 2])
            ),
        )

        self.assertEqual(OrganizationRequest.current_branch_ids.fget(request), [1, 2])

    def test_current_branch_ids_for_current_city(self):
        request = SimpleNamespace(
            current_city_id=10,
            user=SimpleNamespace(
                organization_user=SimpleNamespace(
                    city_branch_map={10: [1, 2], 20: [3]}
                )
            ),
        )

        self.assertEqual(OrganizationRequest.current_branch_ids.fget(request), [1, 2])

    def test_current_branch_ids_for_city_without_branches(self):
        request = SimpleNamespace(
            current_city_id=30,
            user=SimpleNamespace(
                organization_user=SimpleNamespace(city_branch_map={10: [1]})
            ),
        )

        self.assertEqual(OrganizationRequest.current_branch_ids.fget(request), [])


class TestAdminPermissions(SimpleTestCase):
    def setUp(self):
        self.site = MyAdminSite()
        self.model_admin = ManagerAdmin(None, AdminSite())

    def test_admin_site_allows_active_superuser(self):
        request = SimpleNamespace(
            user=SimpleNamespace(is_active=True, is_superuser=True)
        )

        self.assertTrue(self.site.has_permission(request))

    def test_admin_site_allows_active_manager(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_active=True,
                is_superuser=False,
                organization_user=SimpleNamespace(is_manager=True),
            )
        )

        self.assertTrue(self.site.has_permission(request))

    def test_admin_site_denies_non_manager(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_active=True,
                is_superuser=False,
                organization_user=SimpleNamespace(is_manager=False),
            )
        )

        self.assertFalse(self.site.has_permission(request))

    def test_model_admin_allows_superuser(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_superuser=True,
                organization_user=SimpleNamespace(is_manager=False),
            )
        )

        self.assertTrue(self.model_admin.has_module_permission(request))
        self.assertTrue(self.model_admin.has_view_permission(request))
        self.assertTrue(self.model_admin.has_add_permission(request))
        self.assertTrue(self.model_admin.has_change_permission(request))
        self.assertTrue(self.model_admin.has_delete_permission(request))

    def test_model_admin_allows_manager(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_superuser=False,
                organization_user=SimpleNamespace(is_manager=True),
            )
        )

        self.assertTrue(self.model_admin.has_module_permission(request))


class TestCreateUserWithRole(BaseTestCase):
    def test_create_user_with_role(self):
        user = create_user_with_role(
            username='test',
            role=USER_ROLES.CHIEF,
            first_name='Иван',
            last_name='Иванов',
            second_name='Иванович',
        )

        organization_user = user.organization_user

        self.assertEqual(user.username, 'test')
        self.assertEqual(organization_user.role, USER_ROLES.CHIEF)
        self.assertEqual(organization_user.username, 'test')
        self.assertEqual(organization_user.first_name, 'Иван')
        self.assertEqual(organization_user.last_name, 'Иванов')
        self.assertEqual(organization_user.second_name, 'Иванович')
        self.assertTrue(user.organizations.filter(database_alias='organization_1').exists())

    def test_create_user_with_role_and_cities(self):
        from accounts.models import City

        city = City.objects.create(name='Москва')

        user = create_user_with_role(
            username='test',
            role=USER_ROLES.CITY_ADMIN,
            cities=[city],
        )

        self.assertEqual(
            list(user.organization_user.cities.all()),
            [city],
        )
