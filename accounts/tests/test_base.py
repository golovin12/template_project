from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.models import City
from common_tools.test import BaseTestCase


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
        self.assertTrue(
            user.organizations.filter(database_alias='organization_1').exists()
        )

    def test_create_user_with_role_and_cities(self):
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
