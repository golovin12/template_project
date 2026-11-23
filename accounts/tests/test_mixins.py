from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.mixins import (
    BranchControlHelperMixin, CityControlHelperMixin, ForSuperUserMixin, RoleRequiredMixin, UserBranchControlMixin,
    UserCityControlMixin,
)
from accounts.models import Branch, City
from apps.service_requests.models import DeviceType
from common_tools.test import BaseTestCase


class TestRoleRequiredMixin(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def get_request(self, user, ajax=False):
        request = self.factory.get(
            '/',
            {'ajax': 'true'} if ajax else {},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest' if ajax else '',
        )
        request.user = user
        return request

    def test_allows_user_with_required_role(self):
        user = create_user_with_role('chief', USER_ROLES.CHIEF)

        mixin = RoleRequiredMixin()
        mixin.roles_required = (USER_ROLES.CHIEF,)

        self.assertIsNone(mixin.check_permissions(self.get_request(user)))

    def test_allows_manager(self):
        user = create_user_with_role('manager', USER_ROLES.MANAGER)

        mixin = RoleRequiredMixin()
        mixin.roles_required = (USER_ROLES.CHIEF,)

        self.assertIsNone(mixin.check_permissions(self.get_request(user)))

    def test_returns_unauthorized_for_anonymous_ajax_request(self):
        mixin = RoleRequiredMixin()

        response = mixin.check_permissions(
            self.get_request(SimpleNamespace(is_authenticated=False), ajax=True)
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'AUTH_REQUIRED')

    def test_returns_forbidden_for_user_without_role_ajax_request(self):
        user = create_user_with_role('chief', USER_ROLES.CHIEF)

        mixin = RoleRequiredMixin()
        mixin.roles_required = (USER_ROLES.CITY_ADMIN,)

        response = mixin.check_permissions(self.get_request(user, ajax=True))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'NO_PERMISSION')
        self.assertEqual(
            response.json()['required_roles'],
            [USER_ROLES.CITY_ADMIN],
        )

    def test_raises_permission_denied_for_user_without_role(self):
        user = create_user_with_role('chief', USER_ROLES.CHIEF)

        mixin = RoleRequiredMixin()
        mixin.roles_required = (USER_ROLES.CITY_ADMIN,)

        with self.assertRaises(PermissionDenied):
            mixin.check_permissions(self.get_request(user))


class TestForSuperUserMixin(BaseTestCase):
    def test_allows_superuser(self):
        user = create_user_with_role(
            'admin',
            USER_ROLES.MANAGER,
            is_superuser=True,
        )
        mixin = ForSuperUserMixin()
        mixin.request = SimpleNamespace(user=user)

        self.assertTrue(mixin.test_func())

    def test_denies_regular_user(self):
        user = create_user_with_role('user', USER_ROLES.MANAGER)
        mixin = ForSuperUserMixin()
        mixin.request = SimpleNamespace(user=user)

        self.assertFalse(mixin.test_func())


class TestBranchControlHelperMixin(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city_1 = City.objects.create(name='Город 1')
        self.city_2 = City.objects.create(name='Город 2')
        self.branch_1 = Branch.objects.create(name='Филиал 1', city=self.city_1)
        self.branch_2 = Branch.objects.create(name='Филиал 2', city=self.city_2)

        self.user = create_user_with_role(
            'chief',
            USER_ROLES.CHIEF,
            cities=[self.city_1],
        )
        self.request = SimpleNamespace(
            user=self.user,
            current_city_id=None,
            current_branch_ids=[self.branch_1.id],
        )
        self.helper = BranchControlHelperMixin()
        self.helper.request = self.request

    def test_filters_by_current_branch_ids(self):
        self.assertEqual(
            self.helper.get_filter_by_branch(),
            {'branch__in': [self.branch_1.id]},
        )

    def test_does_not_filter_when_all_cities_access_and_no_current_city(self):
        organization_user = self.user.organization_user
        organization_user.all_cities_access = True
        organization_user.save(update_fields=['all_cities_access'])

        self.assertEqual(self.helper.get_filter_by_branch(), {})

    def test_filters_by_current_city_even_with_all_cities_access(self):
        organization_user = self.user.organization_user
        organization_user.all_cities_access = True
        organization_user.save(update_fields=['all_cities_access'])
        self.request.current_city_id = self.city_1.id

        self.assertEqual(
            self.helper.get_filter_by_branch(),
            {'branch__in': [self.branch_1.id]},
        )

    def test_apply_branch_restriction(self):
        device_type_1 = DeviceType.objects.create(name='Тип 1', is_available_for_all=False)
        device_type_1.branches.add(self.branch_1)

        device_type_2 = DeviceType.objects.create(name='Тип 2', is_available_for_all=False)
        device_type_2.branches.add(self.branch_2)

        queryset = self.helper.apply_branch_restriction(
            DeviceType.objects.all(),
            field='branches',
        )

        self.assertEqual(list(queryset), [device_type_1])


class TestCityControlHelperMixin(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city_1 = City.objects.create(name='Город 1')
        self.city_2 = City.objects.create(name='Город 2')
        self.user = create_user_with_role(
            'chief',
            USER_ROLES.CHIEF,
            cities=[self.city_1],
        )
        self.request = SimpleNamespace(
            user=self.user,
            current_city_id=None,
        )
        self.helper = CityControlHelperMixin()
        self.helper.request = self.request

    def test_filters_by_allowed_cities(self):
        self.assertEqual(
            self.helper.get_city_filter_kwargs(),
            {'city__in': [self.city_1.id]},
        )

    def test_filters_by_current_city(self):
        self.request.current_city_id = self.city_2.id

        self.assertEqual(
            self.helper.get_city_filter_kwargs(),
            {'city': self.city_2.id},
        )

    def test_does_not_filter_for_all_cities_access(self):
        organization_user = self.user.organization_user
        organization_user.all_cities_access = True
        organization_user.save(update_fields=['all_cities_access'])

        self.assertEqual(self.helper.get_city_filter_kwargs(), {})

    def test_does_not_filter_for_manager(self):
        manager = create_user_with_role('manager', USER_ROLES.MANAGER)
        self.helper.request = SimpleNamespace(
            user=manager,
            current_city_id=None,
        )

        self.assertEqual(self.helper.get_city_filter_kwargs(), {})

    def test_apply_city_restriction(self):
        branch_1 = Branch.objects.create(name='Филиал 1', city=self.city_1)
        branch_2 = Branch.objects.create(name='Филиал 2', city=self.city_2)

        queryset = self.helper.apply_city_restriction(
            Branch.objects.all(),
            field='city',
        )

        self.assertEqual(list(queryset), [branch_1])


class TestUserQuerysetMixins(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city_1 = City.objects.create(name='Город 1')
        self.city_2 = City.objects.create(name='Город 2')
        self.branch_1 = Branch.objects.create(name='Филиал 1', city=self.city_1)
        self.branch_2 = Branch.objects.create(name='Филиал 2', city=self.city_2)
        self.user = create_user_with_role(
            'chief',
            USER_ROLES.CHIEF,
            cities=[self.city_1],
        )

    def test_user_branch_control_mixin(self):
        device_type_1 = DeviceType.objects.create(name='Тип 1', is_available_for_all=False)
        device_type_1.branches.add(self.branch_1)

        device_type_2 = DeviceType.objects.create(name='Тип 2', is_available_for_all=False)
        device_type_2.branches.add(self.branch_2)

        class View(UserBranchControlMixin):
            request = SimpleNamespace(
                user=self.user,
                current_city_id=None,
                current_branch_ids=[self.branch_1.id],
            )

            def get_queryset(self):
                return DeviceType.objects.all()

        self.assertEqual(list(View().get_queryset()), [device_type_1])

    def test_user_city_control_mixin(self):
        class View(UserCityControlMixin):
            request = SimpleNamespace(
                user=self.user,
                current_city_id=None,
            )

            def get_queryset(self):
                return Branch.objects.all()

        self.assertEqual(list(View().get_queryset()), [self.branch_1])
