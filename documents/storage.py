from django.core.exceptions import ValidationError
from django.core.files import File

from .models import DocumentFile, DocumentsUser


def open_document(document: DocumentFile) -> File:
    return document.file.open('rb')


async def get_user_document(user: DocumentsUser, file_id: int) -> DocumentFile:
    document = await DocumentFile.objects.filter(pk=file_id, user=user).afirst()

    if document is None:
        raise ValidationError('Файл не найден.')

    return document
