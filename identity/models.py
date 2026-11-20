from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models


class AuthUser(AbstractUser):
    """Глобальный пользователь, имеющий доступ к одной или нескольким организациям."""
    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        'Логин',
        max_length=150,
        unique=True,
        validators=[username_validator],
        help_text='Обязательное поле. Не более 150 символов. Только буквы, цифры и @/./+/-/_.',
        error_messages={'unique': 'Пользователь с таким логином уже существует.'},
    )

    second_name = models.CharField('Отчество', max_length=150, blank=True)

    class Meta:
        ordering = ('-is_active', '-is_superuser', 'username')
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    @property
    def full_name(self):
        return f'{self.last_name} {self.first_name} {self.second_name}'.strip()

    @property
    def organization_user(self):
        from accounts.models import OrganizationUser
        if not hasattr(self, '_organization_user'):
            organization_user = OrganizationUser.objects.filter(user_id=self.id).first()
            if organization_user is None:
                organization_user = OrganizationUser(user_id=self.id, is_superuser=self.is_superuser)
            self._organization_user = organization_user
            self._organization_user._auth_user = self
        return self._organization_user

    def __str__(self):
        return self.full_name or self.username


class Organization(models.Model):
    """Описание зоны и связанной с ней базы данных."""
    name = models.CharField('Название', max_length=100, unique=True)
    database_alias = models.CharField('Алиас базы данных', max_length=50, unique=True)

    users = models.ManyToManyField(AuthUser, related_name='organizations', verbose_name='Пользователи', blank=True)

    class Meta:
        ordering = ('database_alias',)
        verbose_name = 'Организация'
        verbose_name_plural = 'Организации'

    def __str__(self):
        return self.name
