from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .image import compress_image
from .models import DocumentFile, DocumentFolder


def create_folder(user, name):
    name = name.strip()

    if not name:
        raise ValidationError('Название папки не может быть пустым.')

    try:
        with transaction.atomic():
            return DocumentFolder.objects.create(
                user=user,
                name=name,
            )
    except IntegrityError:
        raise ValidationError('Папка с таким названием уже существует.')


def upload_file(user, uploaded_file, folder_id=None):
    folder = None

    if folder_id:
        folder = DocumentFolder.objects.filter(
            pk=folder_id,
            user=user,
        ).first()

        if folder is None:
            raise ValidationError('Указанная папка не найдена.')

    original_name = uploaded_file.name.replace('\\', '/').split('/')[-1]
    original_name = original_name[:255]

    if not original_name:
        raise ValidationError('Некорректное имя файла.')

    processed_file = compress_image(uploaded_file)

    document = DocumentFile(
        user=user,
        folder=folder,
        original_name=original_name,
        size=processed_file.size,
    )

    document.file.save(
        Path(original_name).name,
        processed_file,
        save=False,
    )
    document.save()

    return document


def delete_file(user, file_id):
    document = DocumentFile.objects.filter(
        pk=file_id,
        user=user,
    ).first()

    if document is None:
        raise ValidationError('Файл не найден.')

    document.file.delete(save=False)
    document.delete()

    return document
