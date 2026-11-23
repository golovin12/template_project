from django.core.exceptions import ValidationError

from .models import DocumentFile


def get_user_document(user, file_id):
    document = DocumentFile.objects.filter(
        pk=file_id,
        user=user,
    ).first()

    if document is None:
        raise ValidationError('Файл не найден.')

    return document


def open_document(document):
    return document.file.open('rb')
