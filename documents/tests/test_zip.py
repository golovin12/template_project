from asgiref.sync import async_to_sync
from io import BytesIO
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase

from documents.controllers import upload_file
from documents.models import DocumentsUser
from documents.zip import create_zip_response


async def read_stream(response):
    return b''.join([
        chunk async for chunk in response.streaming_content
    ])


class DocumentZipTests(TransactionTestCase):
    def setUp(self):
        self.user = DocumentsUser.objects.create(username='user')
        self.another_user = DocumentsUser.objects.create(username='another')

    def tearDown(self):
        for document in self.user.files.all():
            document.file.delete(save=False)

        for document in self.another_user.files.all():
            document.file.delete(save=False)

    def test_archive_contains_selected_files(self):
        first = async_to_sync(upload_file)(
            self.user,
            SimpleUploadedFile('first.txt', b'first'),
            folder_id=None,
        )
        second = async_to_sync(upload_file)(
            self.user,
            SimpleUploadedFile('second.txt', b'second'),
            folder_id=None,
        )
        async_to_sync(upload_file)(
            self.another_user,
            SimpleUploadedFile('another.txt', b'another'),
            folder_id=None,
        )

        response = async_to_sync(create_zip_response)(
            self.user,
            [first.pk, second.pk],
        )

        try:
            content = async_to_sync(read_stream)(response)
        finally:
            response.close()

        with ZipFile(BytesIO(content)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {'first.txt', 'second.txt'},
            )
            self.assertEqual(archive.read('first.txt'), b'first')
            self.assertEqual(archive.read('second.txt'), b'second')

    def test_archive_rejects_another_users_file(self):
        document = async_to_sync(upload_file)(
            self.another_user,
            SimpleUploadedFile('another.txt', b'another'),
            folder_id=None,
        )

        with self.assertRaises(ValidationError):
            async_to_sync(create_zip_response)(
                self.user,
                [document.pk],
            )

    def test_archive_rejects_empty_selection(self):
        with self.assertRaises(ValidationError):
            async_to_sync(create_zip_response)(
                self.user,
                [],
            )

    def test_archive_rejects_duplicate_ids(self):
        document = async_to_sync(upload_file)(
            self.user,
            SimpleUploadedFile('test.txt', b'content'),
            folder_id=None,
        )

        with self.assertRaises(ValidationError):
            async_to_sync(create_zip_response)(
                self.user,
                [document.pk, document.pk],
            )
