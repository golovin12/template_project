from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.exceptions import ValidationError
from django.http import FileResponse

from .models import DocumentFile


def create_zip_response(user, file_ids):
    documents = list(
        DocumentFile.objects.filter(
            user=user,
            pk__in=file_ids,
        )
    )

    if not documents:
        raise ValidationError('Не выбраны файлы для скачивания.')

    if len(documents) != len(set(file_ids)):
        raise ValidationError('Некоторые файлы не найдены.')

    archive_file = SpooledTemporaryFile(max_size=8 * 1024 * 1024)

    try:
        with ZipFile(archive_file, 'w', compression=ZIP_DEFLATED) as archive:
            used_names = set()

            for document in documents:
                archive_name = document.original_name
                candidate = archive_name
                index = 1

                while candidate.lower() in used_names:
                    path = document.original_name.rsplit('.', 1)
                    if len(path) == 2:
                        candidate = f'{path[0]} ({index}).{path[1]}'
                    else:
                        candidate = f'{archive_name} ({index})'

                    index += 1

                used_names.add(candidate.lower())

                with document.file.open('rb') as source:
                    archive.writestr(candidate, source.read())

        archive_file.seek(0)

        return FileResponse(
            archive_file,
            as_attachment=True,
            filename='documents.zip',
            content_type='application/zip',
        )
    except Exception:
        archive_file.close()
        raise
