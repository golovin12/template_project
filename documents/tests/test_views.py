from asgiref.sync import async_to_sync
from io import BytesIO
from zipfile import ZipFile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from documents.controllers import upload_file
from documents.models import DocumentsUser, DocumentFolder, DocumentFile


async def read_stream(response):
    return b''.join([
        chunk async for chunk in response.streaming_content
    ])


class DocumentViewsTests(TestCase):
    def setUp(self):
        self.user = DocumentsUser.objects.create(username='user')
        self.user.set_password('password123')
        self.user.save()

        self.another_user = DocumentsUser.objects.create(username='another')
        self.another_user.set_password('password123')
        self.another_user.save()

    def tearDown(self):
        for document in DocumentFile.objects.all():
            document.file.delete(save=False)

    def login(self):
        return self.client.post(
            reverse('documents:login'),
            {
                'username': 'user',
                'password': 'password123',
            },
        )

    def test_registration_is_available_without_login(self):
        response = self.client.get(reverse('documents:register'))

        self.assertEqual(response.status_code, 200)

    def test_registration_logs_user_in(self):
        response = self.client.post(
            reverse('documents:register'),
            {
                'username': 'new_user',
                'password': 'password123',
                'password_confirm': 'password123',
            },
        )

        self.assertRedirects(response, reverse('documents:index'))
        self.assertTrue(
            DocumentsUser.objects.filter(username='new_user').exists()
        )
        self.assertIn('documents_user_id', self.client.session)

    def test_registration_rejects_duplicate_username(self):
        response = self.client.post(
            reverse('documents:register'),
            {
                'username': 'USER',
                'password': 'password123',
                'password_confirm': 'password123',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DocumentsUser.objects.count(), 2)
        self.assertNotIn('documents_user_id', self.client.session)

    def test_index_requires_login(self):
        response = self.client.get(reverse('documents:index'))

        self.assertRedirects(
            response,
            reverse('documents:login'),
        )

    def test_login_and_logout(self):
        response = self.login()

        self.assertRedirects(response, reverse('documents:index'))

        response = self.client.post(reverse('documents:logout'))

        self.assertRedirects(response, reverse('documents:login'))

        response = self.client.get(reverse('documents:index'))

        self.assertRedirects(
            response,
            reverse('documents:login'),
        )

    def test_login_rejects_inactive_user(self):
        self.user.is_active = False
        self.user.save()

        response = self.login()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('documents_user_id', self.client.session)

    def test_folder_upload_download_and_delete(self):
        self.login()

        response = self.client.post(
            reverse('documents:folder_create'),
            {'name': 'Photos'},
        )

        self.assertRedirects(response, reverse('documents:index'))

        folder = DocumentFolder.objects.get(
            user=self.user,
            name='Photos',
        )

        response = self.client.post(
            reverse('documents:file_upload'),
            {
                'file': SimpleUploadedFile('test.txt', b'content'),
                'folder': folder.pk,
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("documents:index")}?folder={folder.pk}',
        )

        document = DocumentFile.objects.get(user=self.user)

        response = self.client.get(
            reverse('documents:file_download', args=[document.pk]),
        )

        self.assertEqual(response.status_code, 200)

        try:
            self.assertEqual(
                async_to_sync(read_stream)(response),
                b'content',
            )
        finally:
            response.close()

        response = self.client.post(
            reverse('documents:file_delete', args=[document.pk]),
        )

        self.assertRedirects(response, reverse('documents:index'))
        self.assertFalse(
            DocumentFile.objects.filter(pk=document.pk).exists()
        )

    def test_user_cannot_download_another_users_file(self):
        document = async_to_sync(upload_file)(
            self.another_user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )

        self.login()

        response = self.client.get(
            reverse('documents:file_download', args=[document.pk]),
        )

        self.assertRedirects(response, reverse('documents:index'))

    def test_user_cannot_select_another_users_file_for_zip(self):
        document = async_to_sync(upload_file)(
            self.another_user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )

        self.login()

        response = self.client.post(
            reverse('documents:files_download'),
            {'files': [document.pk]},
        )

        self.assertRedirects(response, reverse('documents:index'))

    def test_download_selected_files(self):
        self.login()

        self.client.post(
            reverse('documents:file_upload'),
            {
                'file': SimpleUploadedFile('test.txt', b'content'),
            },
        )

        document = DocumentFile.objects.get(user=self.user)

        response = self.client.post(
            reverse('documents:files_download'),
            {'files': [document.pk]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

        try:
            content = async_to_sync(read_stream)(response)
        finally:
            response.close()

        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(archive.namelist(), ['test.txt'])
            self.assertEqual(archive.read('test.txt'), b'content')
