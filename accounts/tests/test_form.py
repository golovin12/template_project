from accounts.form import CachedBranchChoiceField, CachedCityChoiceField
from accounts.models import Branch, City
from common_tools.test import BaseTestCase


class TestCachedBranchChoiceField(BaseTestCase):
    def test_choices_contain_active_branches(self):
        city = City.objects.create(name='Город')
        branch = Branch.objects.create(name='Филиал', city=city)

        field = CachedBranchChoiceField()

        self.assertEqual(
            list(field.choices),
            [('', ''), (branch.pk, str(branch))],
        )


class TestCachedCityChoiceField(BaseTestCase):
    def test_choices_contain_active_cities(self):
        city = City.objects.create(name='Город')

        field = CachedCityChoiceField()

        self.assertEqual(
            list(field.choices),
            [('', ''), (city.pk, city.name)],
        )
