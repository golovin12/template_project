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
        folder = create_folder(self.user, '  Photos  ')

        self.assertEqual(folder.name, 'Photos')
        self.assertEqual(folder.user, self.user)

    def test_create_folder_rejects_duplicate_name(self):
        create_folder(self.user, 'Photos')

        with self.assertRaises(ValidationError):
            create_folder(self.user, 'photos')

    def test_upload_file(self):
        folder = create_folder(self.user, 'Photos')
        uploaded_file = SimpleUploadedFile('photo.txt', b'content')

        document = upload_file(self.user, uploaded_file, folder.pk)

        self.assertEqual(document.user, self.user)
        self.assertEqual(document.folder, folder)
        self.assertEqual(document.original_name, 'photo.txt')
        self.assertEqual(document.size, len(b'content'))

        with document.file.open('rb') as file:
            self.assertEqual(file.read(), b'content')

    def test_upload_file_rejects_another_users_folder(self):
        folder = DocumentFolder.objects.create(
            user=self.another_user,
            name='Photos',
        )

        with self.assertRaises(ValidationError):
            upload_file(
                self.user,
                SimpleUploadedFile('test.txt', b'content'),
                folder.pk,
            )

    def test_delete_file(self):
        document = upload_file(
            self.user,
            SimpleUploadedFile('test.txt', b'content'),
        )
        file_name = document.file.name

        delete_file(self.user, document.pk)

        self.assertFalse(DocumentFile.objects.filter(pk=document.pk).exists())
        self.assertFalse(document.file.storage.exists(file_name))
