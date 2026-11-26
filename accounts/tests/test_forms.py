from accounts.base import create_user_with_role
from accounts.consts import USER_ROLES
from accounts.forms import (
    BranchCreateForm, BranchUpdateForm, CityCreateForm, CityUpdateForm, UserCreateForm, UserEditForm, UserAssociateForm
)
from accounts.models import Branch, City, OrganizationUser
from common_tools.test import BaseTestCase
from identity.models import AuthUser, Organization


class TestUserForms(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Город')
        self.user = create_user_with_role(
            'existing',
            USER_ROLES.CHIEF,
            cities=[self.city],
        )

    def test_user_create_form_saves_user_and_organization_data(self):
        form = UserCreateForm(data={
            'username': 'new_user',
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'second_name': 'Иванович',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'role': USER_ROLES.CITY_ADMIN,
            'cities': [self.city.pk],
            'all_cities_access': '',
        })

        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()
        organization_user = user.organization_user

        self.assertTrue(Organization.objects.get(database_alias='organization_1').users.filter(pk=user.pk).exists())
        self.assertEqual(organization_user.role, USER_ROLES.CITY_ADMIN)
        self.assertEqual(list(organization_user.cities.all()), [self.city])

    def test_user_edit_form_updates_user_and_organization_data(self):
        form = UserEditForm(
            data={
                'username': self.user.username,
                'first_name': 'Пётр',
                'last_name': 'Петров',
                'second_name': 'Петрович',
                'role': USER_ROLES.CITY_ADMIN,
                'cities': [self.city.pk],
                'all_cities_access': 'on',
                'is_act_creation_access': 'on',
            },
            instance=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)

        user = form.save()
        organization_user = user.organization_user

        self.assertEqual(user.first_name, 'Пётр')
        self.assertEqual(user.last_name, 'Петров')
        self.assertEqual(organization_user.role, USER_ROLES.CITY_ADMIN)
        self.assertTrue(organization_user.all_cities_access)

    def test_user_associate_form_adds_existing_user_to_organization(self):
        user = AuthUser.objects.create_user(
            username='associated',
            password='password',
        )

        form = UserAssociateForm(data={
            'role': USER_ROLES.CHIEF,
            'cities': [self.city.pk],
            'all_cities_access': '',
            'is_act_creation_access': '',
        }, instance=user)

        self.assertTrue(form.is_valid(), form.errors)

        form.save()

        organization = Organization.objects.get(database_alias='organization_1')

        self.assertTrue(organization.users.filter(pk=user.pk).exists())
        organization_user = OrganizationUser.objects.get(user_id=user.pk)
        self.assertEqual(organization_user.role, USER_ROLES.CHIEF)
        self.assertEqual(list(organization_user.cities.all()), [self.city])


class TestBranchForms(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.city = City.objects.create(name='Город')
        self.inactive_city = City.objects.create(name='Неактивный город', is_active=False)

    def test_branch_create_form_rejects_inactive_city(self):
        form = BranchCreateForm(data={
            'name': 'Филиал',
            'city': self.inactive_city.pk,
        })

        self.assertFalse(form.is_valid())
        self.assertIn('Выбранный город не активен.', form.errors['city'])

    def test_branch_update_form_saves_changes(self):
        branch = Branch.objects.create(name='Старое название', city=self.city)

        form = BranchUpdateForm(
            data={
                'name': 'Новое название',
                'city': self.city.pk,
                'is_active': 'on',
            },
            instance=branch,
        )

        self.assertTrue(form.is_valid(), form.errors)

        branch = form.save()

        self.assertEqual(branch.name, 'Новое название')


class TestCityForms(BaseTestCase):
    def test_city_create_form_saves_city(self):
        form = CityCreateForm(data={'name': 'Город'})

        self.assertTrue(form.is_valid(), form.errors)

        city = form.save()

        self.assertEqual(city.name, 'Город')

    def test_city_update_form_saves_changes(self):
        city = City.objects.create(name='Старое название')

        form = CityUpdateForm(
            data={
                'name': 'Новое название',
                'is_active': '',
            },
            instance=city,
        )

        self.assertTrue(form.is_valid(), form.errors)

        city = form.save()

        self.assertEqual(city.name, 'Новое название')
        self.assertFalse(city.is_active)
