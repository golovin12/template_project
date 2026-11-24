from typing import AsyncIterator
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.http import StreamingHttpResponse

from common_tools.async_files import generate_zip, storage_client, ZipFileEntry
from .models import DocumentFile, DocumentsUser


async def create_zip_response(user: DocumentsUser, file_ids: list[int]) -> StreamingHttpResponse:
    file_ids = list(file_ids)

    if not file_ids:
        raise ValidationError('Не выбраны файлы для скачивания.')

    if len(file_ids) != len(set(file_ids)):
        raise ValidationError('Некорректный список файлов.')

    queryset = DocumentFile.objects.filter(user=user, pk__in=file_ids)

    documents_count = await queryset.acount()

    if documents_count == 0:
        raise ValidationError('Не выбраны файлы для скачивания.')

    if documents_count != len(file_ids):
        raise ValidationError('Некоторые файлы не найдены.')

    async def files() -> AsyncIterator[ZipFileEntry]:
        used_names = set()

        async for document in queryset.aiterator():
            archive_name = document.original_name
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
