from django.core.cache import cache

from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import Branch, City
from common_tools.test import BaseTestCase


class TestBranchSignals(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Город')
        self.branch = Branch.objects.create(name='Филиал', city=self.city)
        self.user = create_user_with_role(
            'chief',
            USER_ROLES.CHIEF,
            cities=[self.city],
        )

    def test_branch_change_clears_cache_for_users_with_access_to_city(self):
        organization_user = self.user.organization_user
        cache.set(organization_user._access_cache_key(), {'test': True})

        self.branch.name = 'Новое название'
        self.branch.save()

        self.assertIsNone(cache.get(organization_user._access_cache_key()))

    def test_branch_change_clears_cache_for_users_with_all_cities_access(self):
        user = create_user_with_role('all_cities', USER_ROLES.CHIEF)
        organization_user = user.organization_user
        organization_user.all_cities_access = True
        organization_user.save(update_fields=['all_cities_access'])

        cache.set(organization_user._access_cache_key(), {'test': True})

        self.branch.name = 'Новое название'
        self.branch.save()

        self.assertIsNone(cache.get(organization_user._access_cache_key()))

    def test_branch_change_does_not_clear_unrelated_user_cache(self):
        other_city = City.objects.create(name='Другой город')
        user = create_user_with_role(
            'other',
            USER_ROLES.CHIEF,
            cities=[other_city],
        )
        organization_user = user.organization_user
        cache.set(organization_user._access_cache_key(), {'test': True})

        self.branch.name = 'Новое название'
        self.branch.save()

        self.assertEqual(
            cache.get(organization_user._access_cache_key()),
            {'test': True},
        )


class TestCitySignals(BaseTestCase):
    def test_deactivating_city_deactivates_its_branches(self):
        city = City.objects.create(name='Город')
        branch_1 = Branch.objects.create(name='Филиал 1', city=city)
        branch_2 = Branch.objects.create(name='Филиал 2', city=city)

        city.is_active = False
        city.save(update_fields=['is_active'])

        branch_1.refresh_from_db()
        branch_2.refresh_from_db()

        self.assertFalse(branch_1.is_active)
        self.assertFalse(branch_2.is_active)

    def test_saving_active_city_does_not_deactivate_branches(self):
        city = City.objects.create(name='Город')
        branch = Branch.objects.create(name='Филиал', city=city)

        city.name = 'Новое название'
        city.save(update_fields=['name'])

        branch.refresh_from_db()

        self.assertTrue(branch.is_active)


class TestOrganizationUserCitiesSignal(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Город')
        self.user = create_user_with_role('chief', USER_ROLES.CHIEF)
        self.organization_user = self.user.organization_user

    def test_adding_city_clears_user_cache(self):
        cache.set(self.organization_user._access_cache_key(), {'test': True})

        self.organization_user.cities.add(self.city)

        self.assertEqual(cache.get(self.organization_user._access_cache_key()),
                         {'branch_ids': [], 'city_branch_map': {}})

    def test_removing_city_clears_user_cache(self):
        self.organization_user.cities.add(self.city)
        cache.set(self.organization_user._access_cache_key(), {'test': True})

        self.organization_user.cities.remove(self.city)

        self.assertIsNone(cache.get(self.organization_user._access_cache_key()))

    def test_clearing_cities_clears_user_cache(self):
        self.organization_user.cities.add(self.city)
        cache.set(self.organization_user._access_cache_key(), {'test': True})

        self.organization_user.cities.clear()

        self.assertIsNone(cache.get(self.organization_user._access_cache_key()))
