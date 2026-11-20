import os
from typing import AsyncGenerator
from urllib.parse import quote

import aiofiles
import aioboto3
import asynczipstream
from botocore.client import BaseClient as BotocoreClient
from django.views import View
from storages.backends.s3boto3 import S3Boto3Storage

from django.conf import settings
from django.core.files.storage import storages
from django.http import StreamingHttpResponse, Http404

from accounts.consts import USER_ROLES
from accounts.mixins import RoleRequiredMixin
from int.db_context import DatabaseContext
from .models import PromoterAssignment

S3_CHUNK_SIZE = 256 * 1024


async def get_assignment(assignment_id: int):
    try:
        assignment = await PromoterAssignment.objects.select_related('promoter', 'route_zone').aget(pk=assignment_id)
    except PromoterAssignment.DoesNotExist:
        raise Http404('Назначение не найдено')
    return assignment


async def get_photos_by_assignment(assignment: PromoterAssignment, db_alias: str):
    async for photo in assignment.photos.using(db_alias).all().aiterator():
        yield {
            'name': photo.image.name,
            'created_at': photo.created_at,
        }


async def s3_file_iterator(s3: BotocoreClient, filename: str):
    """Чтение файла из S3 кусками."""
    default_storage = storages['default']

    key = filename

    if default_storage.location:
        key = f'{default_storage.location}/{filename}'

    response = await s3.get_object(Bucket=default_storage.bucket_name, Key=key)
    body = response['Body']

    try:
        while True:
            chunk = await body.read(S3_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        body.close()


async def local_file_iterator(filename: str):
    """Чтение локального файла."""
    default_storage = storages['default']
    full_path = default_storage.path(filename)

    async with aiofiles.open(full_path, 'rb') as file:
        while True:
            chunk = await file.read(S3_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk


async def photo_iterator(photo: dict, s3: BotocoreClient = None):
    """Унифицированный источник байт."""
    if s3 is not None:
        async for chunk in s3_file_iterator(s3, photo['name']):
            yield chunk
    else:
        async for chunk in local_file_iterator(photo['name']):
            yield chunk


async def generate_zip(photos: AsyncGenerator, s3: BotocoreClient = None):
    """Генератор ZIP архива."""
    archive = asynczipstream.ZipFile(compression=asynczipstream.ZIP_DEFLATED)

    async for photo in photos:
        filename = f'{photo["created_at"]:%d.%m.%Y_%H:%M:%S}_{os.path.basename(photo["name"])}'

        archive.write_iter(filename, photo_iterator(photo, s3))

    async for chunk in archive:
        yield chunk


class DownloadAssignmentPhotosView(RoleRequiredMixin, View):
    """Скачивание фотографий назначения архивом."""
    roles_required = (USER_ROLES.CITY_ADMIN, USER_ROLES.CHIEF)

    async def get(self, request, pk: int, *args, **kwargs):
        db_alias = DatabaseContext.get()
        assignment = await get_assignment(pk)
        photos = get_photos_by_assignment(assignment, db_alias)

        async def stream():
            default_storage = storages['default']
            if isinstance(default_storage, S3Boto3Storage):
                session = aioboto3.Session()
                async with session.client(
                        's3',
                        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        region_name=getattr(settings, 'AWS_S3_REGION_NAME', None),
                ) as s3:
                    async for chunk in generate_zip(photos, s3):
                        yield chunk
            else:
                async for chunk in generate_zip(photos):
                    yield chunk

        response = StreamingHttpResponse(stream(), content_type='application/zip')
        filename = f'{assignment.promoter.nickname}_{assignment.route_zone.name}_photos.zip'
        response['Content-Disposition'] = f'attachment; filename="{quote(filename)}"'
        return response
