import uuid
from pathlib import Path

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


def document_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    folder = instance.folder_id or 'root'
    return f'documents/{instance.user_id}/{folder}/{uuid.uuid4().hex}{extension}'


class DocumentsUser(models.Model):
    username = models.CharField(max_length=150, verbose_name='Логин')
    password = models.CharField(max_length=128, verbose_name='Пароль')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата регистрации')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Пользователь документов'
        verbose_name_plural = 'Пользователи документов'
        constraints = [
            models.UniqueConstraint(Lower('username'), name='documents_user_username_unique'),
        ]

    def __str__(self):
        return self.username

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class DocumentFolder(models.Model):
    user = models.ForeignKey(
        DocumentsUser, on_delete=models.CASCADE, related_name='folders', verbose_name='Пользователь'
    )
    name = models.CharField(max_length=255, verbose_name='Название')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Папка'
        verbose_name_plural = 'Папки'
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint('user', Lower('name'), name='documents_folder_user_name_unique'),
        ]

    def __str__(self):
        return self.name


class DocumentFile(models.Model):
    user = models.ForeignKey(DocumentsUser, on_delete=models.CASCADE, related_name='files', verbose_name='Пользователь')
    folder = models.ForeignKey(
        DocumentFolder, on_delete=models.CASCADE, null=True, blank=True, related_name='files', verbose_name='Папка'
    )
    file = models.FileField(upload_to=document_upload_to, max_length=500, verbose_name='Файл')
    original_name = models.CharField(max_length=255, verbose_name='Название файла')
    size = models.PositiveBigIntegerField(verbose_name='Размер')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'Документ'
        verbose_name_plural = 'Документы'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', 'created_at')),
            models.Index(fields=('folder', 'created_at')),
        ]

    def __str__(self):
        return self.original_name

    def clean(self):
        super().clean()

        if self.folder_id and self.folder.user_id != self.user_id:
            raise ValidationError({'folder': 'Папка не принадлежит пользователю.'})
