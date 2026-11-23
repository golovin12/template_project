from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile

MAX_IMAGE_SIZE = 300 * 1024
MIN_IMAGE_SIZE = 400 * 1024
MAX_IMAGE_DIMENSION = 2560
MIN_IMAGE_DIMENSION = 320
SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def compress_image(uploaded_file):
    if uploaded_file.size < MIN_IMAGE_SIZE:
        return uploaded_file

    try:
        image = Image.open(uploaded_file)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        uploaded_file.seek(0)
        return uploaded_file

    if image.format not in SUPPORTED_FORMATS:
        uploaded_file.seek(0)
        return uploaded_file

    if getattr(image, 'is_animated', False):
        uploaded_file.seek(0)
        return uploaded_file

    image_format = image.format
    image = ImageOps.exif_transpose(image)

    if image_format == 'JPEG':
        image = image.convert('RGB')

    image.thumbnail(
        (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
        Image.Resampling.LANCZOS,
    )

    while True:
        output = BytesIO()

        if image_format in {'JPEG', 'WEBP'}:
            for quality in range(70, 39, -10):
                output.seek(0)
                output.truncate(0)

                image.save(
                    output,
                    format=image_format,
                    quality=quality,
                    optimize=True,
                )

                if output.tell() <= MAX_IMAGE_SIZE:
                    break

        else:
            image.save(
                output,
                format=image_format,
                optimize=True,
            )

        if output.tell() <= MAX_IMAGE_SIZE:
            break

        width, height = image.size
        if max(width, height) <= MIN_IMAGE_DIMENSION:
            break

        image = image.resize(
            (
                max(1, int(width * 0.8)),
                max(1, int(height * 0.8)),
            ),
            Image.Resampling.LANCZOS,
        )

    return ContentFile(
        output.getvalue(),
        name=uploaded_file.name,
    )
