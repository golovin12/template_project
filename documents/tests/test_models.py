from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from documents.models import DocumentsUser, DocumentFolder, DocumentFile


class DocumentsUserTests(TestCase):
    def test_password_is_hashed(self):
        user = DocumentsUser(username='user')
        user.set_password('password123')
        user.save()

        self.assertNotEqual(user.password, 'password123')
        self.assertTrue(check_password('password123', user.password))
        self.assertTrue(user.check_password('password123'))

    def test_username_is_case_insensitive_unique(self):
        DocumentsUser.objects.create(username='User')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentsUser.objects.create(username='user')


class DocumentFolderTests(TestCase):
    def test_folder_name_is_unique_per_user_case_insensitively(self):
        user = DocumentsUser.objects.create(username='user')
        DocumentFolder.objects.create(user=user, name='Photos')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentFolder.objects.create(user=user, name='photos')

    def test_different_users_can_have_folders_with_same_name(self):
        first_user = DocumentsUser.objects.create(username='first')
        second_user = DocumentsUser.objects.create(username='second')

        DocumentFolder.objects.create(user=first_user, name='Photos')
        DocumentFolder.objects.create(user=second_user, name='Photos')

        self.assertEqual(DocumentFolder.objects.count(), 2)


class DocumentFileTests(TestCase):
    def test_file_cannot_belong_to_another_users_folder(self):
        user = DocumentsUser.objects.create(username='user')
        another_user = DocumentsUser.objects.create(username='another')
        folder = DocumentFolder.objects.create(user=another_user, name='Photos')

        document = DocumentFile(
            user=user,
            folder=folder,
            file='documents/test.txt',
            original_name='test.txt',
            size=4,
        )

        with self.assertRaises(ValidationError):
            document.full_clean()

    def test_file_can_be_stored_without_folder(self):
        user = DocumentsUser.objects.create(username='user')

        document = DocumentFile.objects.create(
            user=user,
            original_name='test.txt',
            file='documents/test.txt',
            size=4,
        )

        self.assertIsNone(document.folder_id)

    def test_deleting_folder_cascades_to_files(self):
        user = DocumentsUser.objects.create(username='user')
        folder = DocumentFolder.objects.create(user=user, name='Photos')
        document = DocumentFile.objects.create(
            user=user,
            folder=folder,
            file='documents/test.txt',
            original_name='test.txt',
            size=4,
        )

        folder.delete()

        self.assertFalse(DocumentFile.objects.filter(pk=document.pk).exists())
