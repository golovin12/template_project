from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from documents.controllers import create_folder, upload_file, delete_file
from documents.models import DocumentsUser, DocumentFolder, DocumentFile


class DocumentControllersTests(TestCase):
    def setUp(self):
        self.user = DocumentsUser.objects.create(username='user')
        self.another_user = DocumentsUser.objects.create(username='another')

    def tearDown(self):
        for document in DocumentFile.objects.all():
            document.file.delete(save=False)

    def test_create_folder(self):
        folder = async_to_sync(create_folder)(
            self.user,
            '  Photos  ',
        )

        self.assertEqual(folder.name, 'Photos')
        self.assertEqual(folder.user, self.user)

    def test_create_folder_rejects_duplicate_name(self):
        async_to_sync(create_folder)(self.user, 'Photos')

        with self.assertRaises(ValidationError):
            async_to_sync(create_folder)(self.user, 'photos')

    def test_upload_file_to_folder(self):
        folder = async_to_sync(create_folder)(
            self.user,
            'Photos',
        )
        uploaded_file = SimpleUploadedFile(
            'photo.txt',
            b'content',
        )

        document = async_to_sync(upload_file)(
            self.user,
            uploaded_file,
            folder_id=folder.pk,
        )

        self.assertEqual(document.user, self.user)
        self.assertEqual(document.folder, folder)
        self.assertEqual(document.original_name, 'photo.txt')
        self.assertEqual(document.size, len(b'content'))

        with document.file.open('rb') as file:
            self.assertEqual(file.read(), b'content')

    def test_upload_file_without_folder(self):
        document = async_to_sync(upload_file)(
            self.user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )

        self.assertIsNone(document.folder)
        self.assertEqual(document.original_name, 'test.txt')

    def test_upload_file_rejects_another_users_folder(self):
        folder = DocumentFolder.objects.create(
            user=self.another_user,
            name='Photos',
        )

        with self.assertRaises(ValidationError):
            async_to_sync(upload_file)(
                self.user,
                SimpleUploadedFile('test.txt', b'content'),
                folder_id=folder.pk,
            )

    def test_delete_file(self):
        document = async_to_sync(upload_file)(
            self.user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )
        file_name = document.file.name

        async_to_sync(delete_file)(
            self.user,
            document.pk,
        )

        self.assertFalse(
            DocumentFile.objects.filter(pk=document.pk).exists()
        )
        self.assertFalse(document.file.storage.exists(file_name))

    def test_delete_file_rejects_another_users_file(self):
        document = async_to_sync(upload_file)(
            self.another_user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )

        with self.assertRaises(ValidationError):
            async_to_sync(delete_file)(
                self.user,
                document.pk,
            )
