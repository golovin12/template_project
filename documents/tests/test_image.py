from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from documents.image import compress_image, MAX_IMAGE_SIZE


class CompressImageTests(TestCase):
    def test_small_file_is_not_processed(self):
        uploaded_file = SimpleUploadedFile('test.jpg', b'content')

        result = compress_image(uploaded_file)

        self.assertIs(result, uploaded_file)

    def test_large_jpeg_is_compressed(self):
        image = Image.effect_noise((1600, 1600), 100).convert('RGB')
        output = BytesIO()
        image.save(output, format='JPEG', quality=95)

        uploaded_file = SimpleUploadedFile(
            'photo.jpg',
            output.getvalue(),
            content_type='image/jpeg',
        )

        result = compress_image(uploaded_file)

        self.assertLess(result.size, uploaded_file.size)
        self.assertLessEqual(result.size, MAX_IMAGE_SIZE)

        with Image.open(result) as compressed_image:
            self.assertEqual(compressed_image.format, 'JPEG')

    def test_invalid_image_is_not_processed(self):
        uploaded_file = SimpleUploadedFile(
            'photo.jpg',
            b'x' * (MAX_IMAGE_SIZE * 2),
        )

        result = compress_image(uploaded_file)

        self.assertIs(result, uploaded_file)
