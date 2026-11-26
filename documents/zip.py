from typing import AsyncIterator
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import StreamingHttpResponse

from common_tools.async_files import generate_zip, storage_client, ZipFileEntry
from .models import DocumentFile, DocumentFolder, DocumentsUser


async def create_zip_response(user: DocumentsUser, file_ids: list[int], folder_ids: list[int]) -> StreamingHttpResponse:
    file_ids = list(dict.fromkeys(file_ids))
    folder_ids = list(dict.fromkeys(folder_ids))

    if not file_ids and not folder_ids:
        raise ValidationError('Не выбраны файлы для скачивания.')

    if file_ids:
        selected_files_count = await DocumentFile.objects.filter(user=user, pk__in=file_ids).acount()

        if selected_files_count != len(file_ids):
            raise ValidationError('Некоторые файлы не найдены.')

    folder_names = {}

    if folder_ids:
        async for folder in DocumentFolder.objects.filter(user=user, pk__in=folder_ids).aiterator():
            folder_names[folder.pk] = folder.name

        if len(folder_names) != len(folder_ids):
            raise ValidationError('Некоторые папки не найдены.')

    queryset = DocumentFile.objects.filter(user=user).filter(
        Q(pk__in=file_ids) | Q(folder_id__in=folder_ids)).select_related('folder')

    if not await queryset.aexists():
        raise ValidationError('Выбранные папки не содержат файлов.')

    async def files() -> AsyncIterator[ZipFileEntry]:
        used_names = set()

        async for document in queryset.aiterator():
            archive_name = document.original_name

            if document.folder_id in folder_names:
                archive_name = f'{folder_names[document.folder_id]}/{archive_name}'

            candidate = archive_name
            index = 1

            while candidate.lower() in used_names:
                path = archive_name.rsplit('.', 1)

                if len(path) == 2:
                    candidate = f'{path[0]} ({index}).{path[1]}'
                else:
                    candidate = f'{archive_name} ({index})'

                index += 1

            used_names.add(candidate.lower())

            yield ZipFileEntry(name=document.file.name, archive_name=candidate)

    async def stream() -> AsyncIterator[bytes]:
        async with storage_client() as s3:
            async for chunk in generate_zip(files(), s3):
                yield chunk

    response = StreamingHttpResponse(stream(), content_type='application/zip')
    response['Content-Disposition'] = (
        'attachment; filename="documents.zip"; '
        f"filename*=UTF-8''{quote('documents.zip')}"
    )

    return response
