from django.test import RequestFactory

from common_tools.test import BaseTestCase
from .base import create_user_with_role
from .consts import USER_ROLES
from .forms import UserEditForm
from .models import Branch, City


class UserEditFormTest(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        # Создаем тестовые данные
        cls.city = City.objects.create(name='City')
        cls.city2 = City.objects.create(name='City2')
        cls.branch = Branch.objects.create(name='Main Branch', city=cls.city)
        cls.branch2 = Branch.objects.create(name='Main Branch2', city=cls.city2)
        cls.manager = create_user_with_role(
            username='manager',
            role=USER_ROLES.MANAGER,
        )
        cls.factory = RequestFactory()

    def setUp(self):
        super().setUp()
        self.request = self.factory.get('/')
        self.request.user = self.manager

    def test_form_fields(self):
        """Проверка наличия полей в форме"""
        form = UserEditForm(instance=self.manager)
        self.assertIn('username', form.fields)
        self.assertIn('cities', form.fields)
        self.assertIn('role', form.fields)
        self.assertNotIn('password', form.fields)

    def test_branch_queryset(self):
        """Проверка, что user edit form содержит активные города"""
        City.objects.create(name='Active Branch')
        City.objects.create(name='Inactive Branch', is_active=False)

        form = UserEditForm(instance=self.manager)
        self.assertNotEqual(
            len(form.fields['cities'].choices),
            len(City.objects.all())
        )

    def test_role_choices_for_manager(self):
        """Проверка выбора ролей для менеджера"""
        form = UserEditForm(instance=self.manager)
        self.assertEqual(
            form.fields['role'].choices,
            list(USER_ROLES.choices)
        )

    def test_branch_validation_for_regular_roles(self):
        """Проверка валидации branch для мастера"""
        test_cases = [
            ('master', [], True),
            ('master', [self.branch, self.branch2], True),
            ('master', [self.branch], True),
        ]

        for role, cities, should_be_valid in test_cases:
            with self.subTest(role=role, cities=cities):
                form_data = {
                    'username': 'testuser',
                    'role': role,
                    'cities': cities
                }
                form = UserEditForm(instance=self.manager, data=form_data)
                self.assertEqual(form.is_valid(), should_be_valid, msg=str(form.errors))
                if not should_be_valid:
                    self.assertIn('cities', form.errors)

    def test_form_save(self):
        """Проверка сохранения формы"""
        form_data = {
            'username': 'newuser',
            'role': USER_ROLES.CITY_ADMIN,
            'cities': [self.city.id, self.city2.id],
            'last_name': 'Last',
            'first_name': 'First',
            'second_name': 'Middle',
        }
        form = UserEditForm(instance=self.manager, data=form_data)
        self.assertTrue(form.is_valid(), msg=str(form.errors))
        user = form.save()
        self.assertEqual(user.organization_user.role, USER_ROLES.CITY_ADMIN)
        self.assertEqual(user.organization_user.cities.count(), City.active_objects.count())
