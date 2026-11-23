from django.core.exceptions import ValidationError

from .models import DocumentFile


async def get_user_document(user, file_id):
    document = await DocumentFile.objects.filter(
        pk=file_id,
        user=user,
    ).afirst()

    if document is None:
        raise ValidationError('Файл не найден.')

    return document
