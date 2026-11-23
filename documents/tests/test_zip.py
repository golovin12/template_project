from io import BytesIO
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from documents.controllers import upload_file
from documents.models import DocumentsUser
from documents.zip import create_zip_response


class DocumentZipTests(TestCase):
    def setUp(self):
        self.user = DocumentsUser.objects.create(username='user')
        self.another_user = DocumentsUser.objects.create(username='another')

    def tearDown(self):
        for document in self.user.files.all():
            document.file.delete(save=False)

        for document in self.another_user.files.all():
            document.file.delete(save=False)

    def test_archive_contains_selected_files(self):
        first = upload_file(
            self.user,
            SimpleUploadedFile('first.txt', b'first'),
        )
        second = upload_file(
            self.user,
            SimpleUploadedFile('second.txt', b'second'),
        )
        upload_file(
            self.another_user,
            SimpleUploadedFile('another.txt', b'another'),
        )

        response = create_zip_response(
            self.user,
            [first.pk, second.pk],
        )

        try:
            content = b''.join(response.streaming_content)
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
        document = upload_file(
            self.another_user,
            SimpleUploadedFile('another.txt', b'another'),
        )

        with self.assertRaises(ValidationError):
            create_zip_response(self.user, [document.pk])
