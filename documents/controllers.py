from asgiref.sync import sync_to_async

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction

from common_tools.async_files import bulk_delete_media
from common_tools.images import acompress_image
from .models import DocumentFile, DocumentFolder, DocumentsUser


def _save_folder(folder: DocumentFolder) -> DocumentFolder:
    with transaction.atomic():
        folder.save()

    return folder


async def save_folder(folder: DocumentFolder) -> DocumentFolder:
    return await sync_to_async(_save_folder)(folder)


async def create_folder(user: DocumentsUser, name: str) -> DocumentFolder:
    name = name.strip()

    if not name:
        raise ValidationError('Название папки не может быть пустым.')

    folder = DocumentFolder(user=user, name=name)

    try:
        return await save_folder(folder)
    except IntegrityError:
        raise ValidationError('Папка с таким названием уже существует.')


async def upload_file(user: DocumentsUser, uploaded_file: UploadedFile, folder_id: int | None = None) -> DocumentFile:
    folder = None

    if folder_id:
        folder = await DocumentFolder.objects.filter(pk=folder_id, user=user).afirst()

        if folder is None:
            raise ValidationError('Указанная папка не найдена.')

    original_name = uploaded_file.name.replace('\\', '/').split('/')[-1][:255]

    if not original_name:
        raise ValidationError('Некорректное имя файла.')

    processed_file = await acompress_image(uploaded_file)

    document = DocumentFile(
        user=user, folder=folder, original_name=original_name, size=processed_file.size, file=processed_file
    )
    await document.asave()

    return document


async def delete_file(user: DocumentsUser, file_id: int) -> DocumentFile:
    document = await DocumentFile.objects.filter(pk=file_id, user=user).afirst()

    if document is None:
        raise ValidationError('Файл не найден.')

    await sync_to_async(document.file.delete)(save=False)
    await document.adelete()

    return document


async def delete_folder(user: DocumentsUser, folder_id: int) -> None:
    folder = await DocumentFolder.objects.filter(pk=folder_id, user=user).afirst()

    if folder is None:
        raise ValidationError('Папка не найдена.')

    await bulk_delete_media(
        DocumentFile.objects.filter(folder=folder).values_list('file', flat=True)
    )

    await folder.adelete()
