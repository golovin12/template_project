from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from common_tools.images import acompress_image
from .models import DocumentFile, DocumentFolder


async def create_folder(user, name):
    name = name.strip()

    if not name:
        raise ValidationError('Название папки не может быть пустым.')

    try:
        return await DocumentFolder.objects.acreate(
            user=user,
            name=name,
        )
    except IntegrityError:
        raise ValidationError('Папка с таким названием уже существует.')


async def upload_file(user, uploaded_file, folder_id=None):
    folder = None

    if folder_id:
        folder = await DocumentFolder.objects.filter(
            pk=folder_id,
            user=user,
        ).afirst()

        if folder is None:
            raise ValidationError('Указанная папка не найдена.')

    original_name = uploaded_file.name.replace('\\', '/').split('/')[-1]
    original_name = original_name[:255]

    if not original_name:
        raise ValidationError('Некорректное имя файла.')

    processed_file = await acompress_image(uploaded_file)

    document = DocumentFile(
        user=user,
        folder=folder,
        original_name=original_name,
        size=processed_file.size,
    )

    await sync_to_async(document.file.save)(
        original_name,
        processed_file,
        save=False,
    )

    await document.asave()

    return document


async def delete_file(user, file_id):
    document = await DocumentFile.objects.filter(
        pk=file_id,
        user=user,
    ).afirst()

    if document is None:
        raise ValidationError('Файл не найден.')

    await sync_to_async(document.file.delete)(save=False)
    await document.adelete()

    return document
