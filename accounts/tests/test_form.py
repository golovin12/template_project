from types import SimpleNamespace

from django.core.exceptions import ValidationError

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.form import CachedBranchChoiceField, CachedCityChoiceField
from accounts.models import Branch, City
from common_tools.test import BaseTestCase


class TestCachedBranchChoiceField(BaseTestCase):
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
        self.organization_user = self.user.organization_user
        self.request = SimpleNamespace(
            user=self.user,
            current_city_id=None,
            current_branch_ids=[self.branch_1.id],
        )

    def test_choices_contain_only_current_branches(self):
        field = CachedBranchChoiceField(request=self.request)

        self.assertEqual(
            list(field.choices),
            [('', ''), (self.branch_1.id, str(self.branch_1))],
        )

    def test_clean_returns_selected_branch(self):
        field = CachedBranchChoiceField(request=self.request)

        self.assertEqual(field.clean(str(self.branch_1.id)), self.branch_1)

    def test_clean_rejects_branch_outside_user_access(self):
        field = CachedBranchChoiceField(request=self.request)

        with self.assertRaises(ValidationError):
            field.clean(str(self.branch_2.id))

    def test_choices_without_request_contain_active_branches(self):
        field = CachedBranchChoiceField()

        self.assertEqual(
            list(field.choices),
            [
                ('', ''),
                (self.branch_1.id, str(self.branch_1)),
                (self.branch_2.id, str(self.branch_2)),
            ],
        )


class TestCachedCityChoiceField(BaseTestCase):
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

    def test_choices_contain_only_allowed_cities(self):
        field = CachedCityChoiceField(request=self.request)

        self.assertEqual(
            list(field.choices),
            [('', ''), (self.city_1.id, self.city_1.name)],
        )

    def test_clean_returns_selected_city(self):
        field = CachedCityChoiceField(request=self.request)

        self.assertEqual(field.clean(str(self.city_1.id)), self.city_1)

    def test_clean_rejects_city_outside_user_access(self):
        field = CachedCityChoiceField(request=self.request)

        with self.assertRaises(ValidationError):
            field.clean(str(self.city_2.id))

    def test_current_city_sets_initial_and_disables_field(self):
        self.request.current_city_id = self.city_1.id

        field = CachedCityChoiceField(request=self.request)

        self.assertEqual(field.initial, self.city_1.id)
        self.assertTrue(field.disabled)

    def test_choices_without_request_contain_active_cities(self):
        field = CachedCityChoiceField()

        self.assertEqual(
            list(field.choices),
            [
                ('', ''),
                (self.city_1.id, self.city_1.name),
                (self.city_2.id, self.city_2.name),
            ],
        )
