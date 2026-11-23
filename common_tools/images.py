from io import BytesIO

from asgiref.sync import sync_to_async
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_SIZE = 300 * 1024
MIN_IMAGE_SIZE = 400 * 1024
SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def compress_image(uploaded_file, max_size=MAX_IMAGE_SIZE):
    if uploaded_file.size < max_size + 100 * 1024:
        return uploaded_file

    try:
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        uploaded_file.seek(0)
        return uploaded_file

    if image.format not in SUPPORTED_FORMATS or getattr(image, 'is_animated', False):
        uploaded_file.seek(0)
        return uploaded_file

    image = ImageOps.exif_transpose(image)

    if image.mode != 'RGB':
        image = image.convert('RGB')

    max_dimension = 1920
    quality = 70

    while True:
        image.thumbnail(
            (max_dimension, max_dimension),
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()
        image.save(
            output,
            format='JPEG',
            quality=quality,
            optimize=True,
            progressive=True,
        )

        size = output.tell()

        if size <= max_size:
            output.seek(0)
            return InMemoryUploadedFile(
                output,
                field_name='file',
                name=f'{uploaded_file.name.rsplit(".", 1)[0]}.jpg',
                content_type='image/jpeg',
                size=size,
                charset=None,
            )

        if quality > 40:
            quality -= 10
        else:
            max_dimension = int(max_dimension * 0.8)
            quality = 70


acompress_image = sync_to_async(compress_image)
